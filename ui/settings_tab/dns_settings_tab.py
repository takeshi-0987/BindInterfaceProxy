# -*- coding: utf-8 -*-
"""
Module: dns_settings_tab.py
Author: Takeshi
Date: 2025-12-08
完整版本：DNS设置标签页 - 使用dataclass形式
"""

import logging
import threading
import time
import socket
from typing import Dict, Any, List, Tuple, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QGroupBox, QSpinBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox,
    QComboBox, QScrollArea,  QInputDialog, QDialog,
    QProgressBar, QStackedWidget
)
from PySide6.QtCore import Signal, QThread, QTimer
from PySide6.QtGui import QColor

# 导入DNS配置dataclass
from defaults.dns_default import DNSConfig
from defaults.proxy_default import OutboundInterface
from defaults.config_manager import get_config_manager

logger = logging.getLogger(__name__)


class DNSHealthChecker(QThread):
    """DNS服务器健康检查线程"""

    check_completed = Signal(dict)

    def __init__(self, dns_servers: List[str], bind_ip: Optional[str] = None,
                 test_domain: str = "baidu.com", timeout: int = 3):
        super().__init__()
        self.dns_servers = [self._extract_ip(server) for server in dns_servers]
        self.bind_ip = bind_ip
        self.test_domain = test_domain
        self.timeout = timeout
        self._stop_event = threading.Event()

    def _extract_ip(self, server_str: str) -> str:
        if ":" in server_str:
            return server_str.split(":")[0]
        return server_str


    def _test_single_dns_server(self, server_ip: str) -> Dict[str, Any]:
        try:
            import dns.message
            import dns.query
            import dns.rdatatype
            from dns.exception import DNSException, Timeout
        except ImportError:
            return {
                'server': server_ip,
                'status': 'error',
                'error': "缺少dnspython库",
                'timestamp': time.time()
            }

        result = {
            'server': server_ip,
            'status': 'unknown',
            'response_time': None,
            'error': None,
            'timestamp': time.time(),
            'bind_ip': self.bind_ip
        }

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(self.timeout)

                if self.bind_ip:
                    try:
                        sock.bind((self.bind_ip, 0))
                        logger.debug(f"DNS检查绑定到出口IP: {self.bind_ip}")
                    except Exception as bind_error:
                        logger.warning(f"绑定出口IP {self.bind_ip} 失败: {bind_error}")

                query = dns.message.make_query(self.test_domain, dns.rdatatype.A)

                start_time = time.time()

                response = dns.query.udp(
                    q=query,
                    where=server_ip,
                    timeout=self.timeout,
                    sock=sock
                )

                response_time = time.time() - start_time

                if response.rcode() == 0:
                    for answer in response.answer:
                        if answer.rdtype == dns.rdatatype.A:
                            result['status'] = 'healthy'
                            result['response_time'] = round(response_time * 1000, 2)
                            return result

                    result['status'] = 'error'
                    result['error'] = "未找到A记录"
                else:
                    result['status'] = 'error'
                    result['error'] = f"DNS错误码: {response.rcode()}"

        except (socket.timeout, Timeout):
            result['status'] = 'timeout'
            result['error'] = f"查询超时 ({self.timeout}s)"
        except DNSException as e:
            result['status'] = 'error'
            result['error'] = f"DNS协议错误: {e}"
        except OSError as e:
            result['status'] = 'error'
            result['error'] = f"网络错误: {e}"
        except Exception as e:
            result['status'] = 'error'
            result['error'] = f"未知错误: {e}"

        return result

    def stop(self):
        self._stop_event.set()


class BlacklistItemDialog(QDialog):
    """黑名单项编辑对话框"""

    def __init__(self, item_text: str = "", is_pattern: bool = False, parent=None):
        super().__init__(parent)
        self.item_text = item_text
        self.is_pattern = is_pattern
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("编辑黑名单项")
        self.setMinimumSize(400, 200)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("类型:"))

        self.type_combo = QComboBox()
        self.type_combo.addItems(["精确域名", "通配符模式"])
        self.type_combo.setCurrentIndex(1 if self.is_pattern else 0)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()

        layout.addLayout(type_layout)

        layout.addWidget(QLabel("内容:"))
        self.content_edit = QLineEdit()
        self.content_edit.setText(self.item_text)
        self.content_edit.setPlaceholderText("输入域名或通配符模式")
        layout.addWidget(self.content_edit)

        example_label = QLabel("示例:\n• 精确域名: evil.com\n• 通配符模式: *.evil.com")
        example_label.setWordWrap(True)
        example_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(example_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setDefault(True)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def on_type_changed(self):
        is_pattern = self.type_combo.currentIndex() == 1
        if is_pattern:
            self.content_edit.setPlaceholderText("输入通配符模式，如: *.example.com")
        else:
            self.content_edit.setPlaceholderText("输入精确域名，如: example.com")

    def get_data(self) -> Tuple[str, bool]:
        content = self.content_edit.text().strip()
        is_pattern = self.type_combo.currentIndex() == 1
        return content, is_pattern


class BlacklistManager(QWidget):
    """黑名单管理器"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.blacklist_items = []
        self._modified = False
        self._suppress_signals = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("新增")
        self.add_btn.clicked.connect(self.add_item)

        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_item)
        self.edit_btn.setEnabled(False)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_item)
        self.delete_btn.setEnabled(False)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.setMaximumHeight(150)
        layout.addWidget(self.list_widget)

        self.stats_label = QLabel("共 0 项 (精确域名: 0, 通配符模式: 0)")
        self.stats_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.stats_label)

        self.setLayout(layout)

    def add_item(self):
        dialog = BlacklistItemDialog()
        if dialog.exec() == QDialog.Accepted:
            content, is_pattern = dialog.get_data()
            if content:
                self.blacklist_items.append((content, is_pattern))
                self._update_list()
                self.mark_modified()

    def edit_item(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0 and current_row < len(self.blacklist_items):
            content, is_pattern = self.blacklist_items[current_row]
            dialog = BlacklistItemDialog(content, is_pattern)
            if dialog.exec() == QDialog.Accepted:
                new_content, new_is_pattern = dialog.get_data()
                if new_content:
                    self.blacklist_items[current_row] = (new_content, new_is_pattern)
                    self._update_list()
                    self.mark_modified()

    def delete_item(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "确认删除",
                "确定要删除这个黑名单项吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.blacklist_items.pop(current_row)
                self._update_list()
                self.mark_modified()

    def _update_list(self):
        self.list_widget.clear()

        exact_count = 0
        pattern_count = 0

        for content, is_pattern in self.blacklist_items:
            if is_pattern:
                icon = "🔵"
                pattern_count += 1
            else:
                icon = "⚫"
                exact_count += 1

            item = QListWidgetItem(f"{icon} {content}")
            self.list_widget.addItem(item)

        self.stats_label.setText(f"共 {len(self.blacklist_items)} 项 (精确域名: {exact_count}, 通配符模式: {pattern_count})")

    def on_selection_changed(self):
        current_row = self.list_widget.currentRow()
        has_selection = current_row >= 0

        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def on_item_double_clicked(self, item):
        self.edit_item()

    def mark_modified(self):
        if not self._suppress_signals:
            self._modified = True
            self.config_modified.emit()

    def get_blacklist(self) -> Tuple[List[str], List[str]]:
        exact_domains = []
        patterns = []

        for content, is_pattern in self.blacklist_items:
            if is_pattern:
                patterns.append(content)
            else:
                exact_domains.append(content)

        return exact_domains, patterns

    def set_blacklist(self, exact_domains: List[str], patterns: List[str]):
        old_suppress = self._suppress_signals
        self._suppress_signals = True

        try:
            self.blacklist_items.clear()

            for domain in exact_domains:
                if domain.strip():
                    self.blacklist_items.append((domain.strip(), False))

            for pattern in patterns:
                if pattern.strip():
                    self.blacklist_items.append((pattern.strip(), True))

            self._update_list()
            self._modified = False
        finally:
            self._suppress_signals = old_suppress

    def is_modified(self) -> bool:
        return self._modified

    def clear_modified(self):
        self._modified = False


class DNSServerListWidget(QWidget):
    """DNS服务器列表部件，带健康检查"""

    config_modified = Signal()

    def __init__(self, parent=None, bind_interface_config: Optional[OutboundInterface] = None):
        super().__init__(parent)
        self.health_status = {}
        self.health_checker = None
        self._modified = False
        self._is_loading = False
        self._suppress_signals = True
        self.bind_interface_config = bind_interface_config or OutboundInterface()

        self.dns_servers = self._get_default_servers()

        self.init_ui()
        self._update_bind_display()

        self._suppress_signals = False

    def _get_default_servers(self) -> List[str]:
        default_config = get_config_manager().get_default_config('DNS_CONFIG')
        servers = default_config.dns_servers.copy()
        logger.debug(f"加载默认DNS服务器: {servers}")
        return servers

    def set_bind_interface_config(self, config: OutboundInterface):
        """设置绑定接口配置"""
        self.bind_interface_config = config
        self._update_bind_display()
        logger.debug(f"DNS服务器管理器已更新出口配置: {config}")

    def _get_egress_ip_from_config(self) -> Optional[str]:
        try:
            from utils.interface_utils import NetworkInterface

            name = self.bind_interface_config.iface_name
            ip = self.bind_interface_config.ip

            if ip:
                return ip
            elif name:
                try:
                    iface = NetworkInterface(iface_name=name)
                    return iface.ip
                except Exception:
                    return None
            else:
                return None

        except ImportError:
            return self.bind_interface_config.ip

    def _update_bind_display(self):
        if hasattr(self, 'bind_display_label'):
            ip = self._get_egress_ip_from_config()
            if ip:
                self.bind_display_label.setText(f"出口IP: {ip}")
                self.bind_display_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            else:
                self.bind_display_label.setText("出口IP: 未配置 (将使用默认出口)")
                self.bind_display_label.setStyleSheet("color: #FF9800; font-size: 11px;")

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        top_layout = QHBoxLayout()

        self.add_btn = QPushButton("新增")
        self.add_btn.clicked.connect(self.add_server)

        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_server)
        self.edit_btn.setEnabled(False)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_server)
        self.delete_btn.setEnabled(False)

        self.restore_default_btn = QPushButton("恢复默认")
        self.restore_default_btn.clicked.connect(self.restore_default_servers)

        self.check_btn = QPushButton("检查DNS服务器")
        self.check_btn.clicked.connect(self.check_all_servers)
        self.check_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")

        top_layout.addWidget(self.add_btn)
        top_layout.addWidget(self.edit_btn)
        top_layout.addWidget(self.delete_btn)
        top_layout.addWidget(self.restore_default_btn)
        top_layout.addStretch()
        top_layout.addWidget(self.check_btn)

        layout.addLayout(top_layout)

        self.bind_display_label = QLabel("出口IP: 加载中...")
        self.bind_display_label.setStyleSheet("color: #666; font-size: 11px; background-color: #f0f0f0; padding: 3px;")
        layout.addWidget(self.bind_display_label)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.setMaximumHeight(150)
        layout.addWidget(self.list_widget)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)

        self._update_list()

        self.setLayout(layout)

    def add_server(self):
        server, ok = QInputDialog.getText(self, "新增DNS服务器",
                                         "输入DNS服务器地址:",
                                         text="8.8.8.8")
        if ok and server:
            server = server.strip()
            if server not in self.dns_servers:
                self.dns_servers.append(server)
                self._update_list()
                self.mark_modified()

    def edit_server(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0 and current_row < len(self.dns_servers):
            old_server = self.dns_servers[current_row]

            new_server, ok = QInputDialog.getText(self, "编辑DNS服务器",
                                                 "输入DNS服务器地址:",
                                                 text=old_server)
            if ok and new_server:
                new_server = new_server.strip()
                if new_server != old_server:
                    self.dns_servers[current_row] = new_server
                    self._update_list()
                    self.mark_modified()

    def delete_server(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "确认删除",
                "确定要删除这个DNS服务器吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.dns_servers.pop(current_row)
                self._update_list()
                self.mark_modified()

    def restore_default_servers(self):
        reply = QMessageBox.question(
            self, "恢复默认",
            "确定要恢复默认DNS服务器列表吗？当前列表将被替换。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.dns_servers = self._get_default_servers()
            self.health_status.clear()
            self._update_list()
            self.mark_modified()
            self.status_label.setText("已恢复默认DNS服务器列表")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")

    def check_all_servers(self):
        if not self.dns_servers:
            self.status_label.setText("没有可检查的DNS服务器")
            self.status_label.setStyleSheet("color: #FF9800; font-size: 11px;")
            return

        bind_ip = self._get_egress_ip_from_config()

        self.status_label.setText("正在检查DNS服务器...")
        if bind_ip:
            self.status_label.setText(f"正在检查DNS服务器 (出口IP: {bind_ip})...")
        self.status_label.setStyleSheet("color: #2196F3; font-size: 11px;")

        self.add_btn.setEnabled(False)
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.restore_default_btn.setEnabled(False)
        self.check_btn.setEnabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.dns_servers))
        self.progress_bar.setValue(0)

        self.health_checker = DNSHealthChecker(
            self.dns_servers,
            bind_ip,
            timeout=3
        )
        self.health_checker.check_completed.connect(self.on_check_completed)
        self.health_checker.start()

    def on_check_completed(self, results: Dict[str, Dict]):
        self.health_status = results

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if i < len(self.dns_servers):
                server = self.dns_servers[i]

                if server in results:
                    result = results[server]
                    status_icon = self._get_status_icon(result['status'])
                    response_time = result.get('response_time', 'N/A')

                    display_text = f"{status_icon} {server}"

                    if response_time and response_time != 'N/A':
                        display_text += f" ({response_time}ms)"

                    if result['status'] != 'healthy' and result.get('error'):
                        error_msg = result['error']
                        if len(error_msg) > 30:
                            error_msg = error_msg[:27] + "..."
                        display_text += f" - {error_msg}"

                    item.setText(display_text)

                    if result['status'] == 'healthy':
                        item.setForeground(QColor("#4CAF50"))
                    elif result['status'] == 'timeout':
                        item.setForeground(QColor("#FF9800"))
                    else:
                        item.setForeground(QColor("#F44336"))

        healthy_count = sum(1 for r in results.values() if r['status'] == 'healthy')
        total_count = len(results)

        status_text = f"检查完成: {healthy_count}/{total_count} 个服务器正常"
        bind_ip = self._get_egress_ip_from_config()
        if bind_ip:
            status_text += f" (出口IP: {bind_ip})"

        self.status_label.setText(status_text)

        if healthy_count == total_count:
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        elif healthy_count > 0:
            self.status_label.setStyleSheet("color: #FF9800; font-size: 11px;")
        else:
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px;")

        self.add_btn.setEnabled(True)
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.restore_default_btn.setEnabled(True)
        self.check_btn.setEnabled(True)

        self.progress_bar.setVisible(False)

    def _get_status_icon(self, status: str) -> str:
        icons = {
            'healthy': '✅',
            'timeout': '⚠️',
            'error': '❌',
            'unknown': '❓'
        }
        return icons.get(status, '❓')

    def _update_list(self):
        self.list_widget.clear()

        for i, server in enumerate(self.dns_servers):
            status_icon = "⚪"
            if server in self.health_status:
                result = self.health_status[server]
                status_icon = self._get_status_icon(result['status'])
                response_time = result.get('response_time', 'N/A')

                display_text = f"{status_icon} {server}"

                if response_time and response_time != 'N/A':
                    display_text += f" ({response_time}ms)"
            else:
                display_text = f"{status_icon} {server}"

            item = QListWidgetItem(display_text)
            self.list_widget.addItem(item)

    def on_selection_changed(self):
        current_row = self.list_widget.currentRow()
        has_selection = current_row >= 0

        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def on_item_double_clicked(self, item):
        self.edit_server()

    def mark_modified(self):
        if not self._suppress_signals:
            self._modified = True
            self.config_modified.emit()

    def get_servers(self) -> List[str]:
        return self.dns_servers.copy()

    def set_servers(self, servers: List[str]):
        old_suppress = self._suppress_signals
        self._suppress_signals = True

        try:
            self.dns_servers = []
            for server in servers:
                if ":" in server:
                    ip = server.split(":")[0]
                    self.dns_servers.append(ip)
                else:
                    self.dns_servers.append(server)

            self.health_status.clear()
            self._update_list()
            self._modified = False
            self._is_loading = False
        finally:
            self._suppress_signals = old_suppress

    def is_modified(self) -> bool:
        return self._modified

    def clear_modified(self):
        self._modified = False


class DNSSettingsTab(QWidget):
    """DNS设置标签页"""

    config_modified = Signal()

    def __init__(self, parent=None, bind_interface_config: Optional[OutboundInterface] = None):
        super().__init__(parent)
        self._modified = False
        self._is_loading_config = False
        self._is_initializing = True
        self.bind_interface_config = bind_interface_config or OutboundInterface()
        self.init_ui()
        self._is_initializing = False

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        description = QLabel(
            "DNS解析器设置：\n"
            "• 配置远端DNS服务器，避免使用系统默认DNS\n"
            "• 支持缓存、域名黑名单等高级功能\n"
            "• 可绑定到特定出口网络接口"
        )
        description.setWordWrap(True)
        description.setStyleSheet("""
            QLabel {
                padding: 10px;
                margin-bottom: 0px;
                font-size: 11px;
                color: #666;
                background-color: #f9f9f9;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(description)

        self.enable_group = self.create_enable_settings_group()
        main_layout.addWidget(self.enable_group)

        self.basic_group = self.create_basic_settings_group()
        self.basic_group.setEnabled(False)
        main_layout.addWidget(self.basic_group)

        self.dns_server_group = self.create_dns_server_group()
        self.dns_server_group.setEnabled(False)
        main_layout.addWidget(self.dns_server_group)

        self.cache_group = self.create_cache_settings_group()
        self.cache_group.setEnabled(False)
        main_layout.addWidget(self.cache_group)

        self.blacklist_group = self.create_blacklist_group()
        self.blacklist_group.setEnabled(False)
        main_layout.addWidget(self.blacklist_group)

        main_layout.addStretch()

        scroll_area.setWidget(main_widget)
        layout.addWidget(scroll_area)
        self.setLayout(layout)

    def create_enable_settings_group(self) -> QGroupBox:
        group = QGroupBox("DNS解析设置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QVBoxLayout()
        layout.setSpacing(10)

        self.enable_dns_check = QCheckBox("启用远端DNS解析")
        self.enable_dns_check.setChecked(True)
        QTimer.singleShot(0, lambda: self.enable_dns_check.stateChanged.connect(self.on_enable_dns_changed))
        QTimer.singleShot(0, lambda: self.enable_dns_check.stateChanged.connect(self.mark_modified))

        layout.addWidget(self.enable_dns_check)

        desc_label = QLabel(
            "启用后，代理服务器将使用下方配置的DNS服务器进行域名解析。\n"
            "禁用时，将使用操作系统默认DNS设置。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        group.setLayout(layout)
        return group

    def create_basic_settings_group(self) -> QGroupBox:
        group = QGroupBox("基本设置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setColumnMinimumWidth(0, 40)
        layout.setColumnStretch(1, 1)

        desc_label = QLabel("配置DNS解析器的基本行为参数。")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label, 0, 0, 1, 2)

        # 名称设置
        name_layout = QHBoxLayout()
        name_layout.setSpacing(10)
        name_layout.addWidget(QLabel("名称:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入DNS解析器名称")
        QTimer.singleShot(0, lambda: self.name_edit.textChanged.connect(self.mark_modified))
        self.name_edit.setFixedWidth(100)
        name_layout.addWidget(self.name_edit)
        name_layout.addStretch()
        layout.addLayout(name_layout, 1, 0, 1, 2)

        # 策略选择
        strategy_layout = QHBoxLayout()
        strategy_layout.setSpacing(10)
        strategy_layout.addWidget(QLabel("策略:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["串行", "并行"])
        QTimer.singleShot(0, lambda: self.strategy_combo.currentIndexChanged.connect(self.on_strategy_changed))
        QTimer.singleShot(0, lambda: self.strategy_combo.currentIndexChanged.connect(self.mark_modified))
        self.strategy_combo.setFixedWidth(100)
        strategy_layout.addWidget(self.strategy_combo)
        strategy_layout.addStretch()
        layout.addLayout(strategy_layout, 2, 0, 1, 2)

        # 使用堆叠布局来管理串行和并行设置
        self.settings_stack = QStackedWidget()

        # 串行设置页面
        serial_widget = QWidget()
        serial_layout = QGridLayout(serial_widget)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.setSpacing(10)

        # 串行超时设置
        serial_timeout_label = QLabel("超时:")
        serial_layout.addWidget(serial_timeout_label, 0, 0)

        self.serial_timeout_spin = QSpinBox()
        self.serial_timeout_spin.setRange(1, 30)
        self.serial_timeout_spin.setSuffix(" 秒")
        self.serial_timeout_spin.setValue(3)
        QTimer.singleShot(0, lambda: self.serial_timeout_spin.valueChanged.connect(self.mark_modified))
        self.serial_timeout_spin.setFixedWidth(100)
        serial_layout.addWidget(self.serial_timeout_spin, 0, 1)

        # 添加占位符以保持布局平衡
        serial_layout.addWidget(QWidget(), 0, 2)  # 占位控件
        serial_layout.setColumnStretch(2, 1)      # 右侧拉伸

        # 并行设置页面
        parallel_widget = QWidget()
        parallel_layout = QGridLayout(parallel_widget)
        parallel_layout.setContentsMargins(0, 0, 0, 0)
        parallel_layout.setSpacing(10)

        # 并行超时设置
        parallel_timeout_label = QLabel("超时:")
        parallel_layout.addWidget(parallel_timeout_label, 0, 0)

        self.parallel_timeout_spin = QSpinBox()
        self.parallel_timeout_spin.setRange(1, 30)
        self.parallel_timeout_spin.setSuffix(" 秒")
        self.parallel_timeout_spin.setValue(3)
        QTimer.singleShot(0, lambda: self.parallel_timeout_spin.valueChanged.connect(self.mark_modified))
        self.parallel_timeout_spin.setFixedWidth(100)
        parallel_layout.addWidget(self.parallel_timeout_spin, 0, 1)

        # 并行线程数设置
        parallel_workers_label = QLabel("线程数:")
        parallel_layout.addWidget(parallel_workers_label, 0, 2)

        self.parallel_workers_spin = QSpinBox()
        self.parallel_workers_spin.setRange(1, 10)
        self.parallel_workers_spin.setValue(5)
        QTimer.singleShot(0, lambda: self.parallel_workers_spin.valueChanged.connect(self.mark_modified))
        self.parallel_workers_spin.setFixedWidth(100)
        parallel_layout.addWidget(self.parallel_workers_spin, 0, 3)

        parallel_layout.setColumnStretch(4, 1)  # 右侧拉伸

        # 将两个页面添加到堆叠布局
        self.settings_stack.addWidget(serial_widget)
        self.settings_stack.addWidget(parallel_widget)

        layout.addWidget(self.settings_stack, 3, 0, 1, 2)

        # 系统DNS设置
        self.system_dns_check = QCheckBox("启用系统DNS (当所有DNS服务器失败时使用)")
        QTimer.singleShot(0, lambda: self.system_dns_check.stateChanged.connect(self.mark_modified))
        layout.addWidget(self.system_dns_check, 4, 0, 1, 2)

        # 添加占位拉伸
        layout.addWidget(QWidget(), 5, 0, 1, 2)
        layout.setRowStretch(5, 1)

        group.setLayout(layout)
        return group

    def create_dns_server_group(self) -> QGroupBox:
        group = QGroupBox("DNS服务器配置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout = QVBoxLayout()

        desc_label = QLabel(
            "配置DNS服务器列表，支持健康检查和出口网络绑定。\n"
            "建议添加多个DNS服务器以提高可靠性。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        self.dns_server_manager = DNSServerListWidget(self, self.bind_interface_config)
        QTimer.singleShot(0, lambda: self.dns_server_manager.config_modified.connect(self.mark_modified))

        layout.addWidget(self.dns_server_manager)

        group.setLayout(layout)
        return group

    def create_cache_settings_group(self) -> QGroupBox:
        group = QGroupBox("DNS缓存设置")
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setColumnMinimumWidth(0, 40)
        layout.setColumnStretch(1, 1)

        desc_label = QLabel(
            "缓存DNS查询结果以提高解析速度，减少网络请求。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label, 0, 0, 1, 2)

        self.enable_cache_check = QCheckBox("启用DNS缓存")
        QTimer.singleShot(0, lambda: self.enable_cache_check.stateChanged.connect(self.on_cache_enabled_changed))
        QTimer.singleShot(0, lambda: self.enable_cache_check.stateChanged.connect(self.mark_modified))
        layout.addWidget(self.enable_cache_check, 1, 0, 1, 2)

        ttl_layout = QHBoxLayout()
        ttl_layout.setSpacing(5)
        ttl_layout.addWidget(QLabel("缓存TTL:"))
        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(1, 86400)
        self.cache_ttl_spin.setSuffix(" 秒")
        self.cache_ttl_spin.setValue(300)
        QTimer.singleShot(0, lambda: self.cache_ttl_spin.valueChanged.connect(self.mark_modified))
        self.cache_ttl_spin.setMinimumWidth(100)
        ttl_layout.addWidget(self.cache_ttl_spin)
        ttl_layout.addStretch()
        layout.addLayout(ttl_layout, 2, 0, 1, 2)

        cleanup_layout = QHBoxLayout()
        cleanup_layout.setSpacing(5)
        cleanup_layout.addWidget(QLabel("清理间隔:"))
        self.cleanup_interval_spin = QSpinBox()
        self.cleanup_interval_spin.setRange(60, 86400)
        self.cleanup_interval_spin.setSuffix(" 秒")
        self.cleanup_interval_spin.setValue(600)
        self.cleanup_interval_spin.setSpecialValueText("禁用自动清理")
        QTimer.singleShot(0, lambda: self.cleanup_interval_spin.valueChanged.connect(self.mark_modified))
        self.cleanup_interval_spin.setMinimumWidth(100)
        cleanup_layout.addWidget(self.cleanup_interval_spin)
        cleanup_layout.addStretch()
        layout.addLayout(cleanup_layout, 3, 0, 1, 2)

        max_cache_layout = QHBoxLayout()
        max_cache_layout.setSpacing(5)
        max_cache_layout.addWidget(QLabel("最大缓存数:"))
        self.max_cache_spin = QSpinBox()
        self.max_cache_spin.setRange(0, 100000)
        self.max_cache_spin.setSpecialValueText("无限制")
        self.max_cache_spin.setValue(1000)
        QTimer.singleShot(0, lambda: self.max_cache_spin.valueChanged.connect(self.mark_modified))
        self.max_cache_spin.setMinimumWidth(100)
        max_cache_layout.addWidget(self.max_cache_spin)
        max_cache_layout.addStretch()
        layout.addLayout(max_cache_layout, 4, 0, 1, 2)

        group.setLayout(layout)
        return group

    def create_blacklist_group(self) -> QGroupBox:
        group = QGroupBox("域名黑名单")
        layout = QVBoxLayout()

        desc_label = QLabel(
            "配置需要拦截的域名，支持精确匹配和通配符模式。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        self.blacklist_manager = BlacklistManager()
        QTimer.singleShot(0, lambda: self.blacklist_manager.config_modified.connect(self.mark_modified))
        layout.addWidget(self.blacklist_manager)

        group.setLayout(layout)
        return group

    def on_enable_dns_changed(self):
        enabled = self.enable_dns_check.isChecked()

        self.basic_group.setEnabled(enabled)
        self.dns_server_group.setEnabled(enabled)
        self.cache_group.setEnabled(enabled)
        self.blacklist_group.setEnabled(enabled)

        if enabled and hasattr(self, 'dns_server_manager') and self.dns_server_manager:
            self.dns_server_manager.set_bind_interface_config(self.bind_interface_config)

    def on_strategy_changed(self):
        """策略切换时的处理"""

        index = self.strategy_combo.currentIndex()
        # 切换堆叠布局的当前页面
        self.settings_stack.setCurrentIndex(index)

    def on_cache_enabled_changed(self):
        enabled = self.enable_cache_check.isChecked()
        self.cache_ttl_spin.setEnabled(enabled)
        self.cleanup_interval_spin.setEnabled(enabled)
        self.max_cache_spin.setEnabled(enabled)

    def update_bind_interface_config(self, config: OutboundInterface):
        """更新绑定接口配置"""
        self.bind_interface_config = config

        if hasattr(self, 'dns_server_manager') and self.dns_server_manager:
            self.dns_server_manager.set_bind_interface_config(config)

    def mark_modified(self):
        """标记配置已修改"""
        if self._is_loading_config or self._is_initializing:
            return
        self._modified = True
        self.config_modified.emit()

    def clear_modified(self):
        self._modified = False
        if hasattr(self, 'dns_server_manager'):
            self.dns_server_manager.clear_modified()
        if hasattr(self, 'blacklist_manager'):
            self.blacklist_manager.clear_modified()

    def is_modified(self) -> bool:
        modified = self._modified
        if hasattr(self, 'dns_server_manager'):
            modified = modified or self.dns_server_manager.is_modified()
        if hasattr(self, 'blacklist_manager'):
            modified = modified or self.blacklist_manager.is_modified()
        return modified

    def get_config(self) -> DNSConfig:
        """从UI获取DNSConfig对象"""
        try:
            # 创建DNSConfig对象
            dns_config = DNSConfig(
                enable_remote_dns_resolve=self.enable_dns_check.isChecked(),
                name=self.name_edit.text().strip() or "DNS解析器",
                dns_servers=self.dns_server_manager.get_servers() if hasattr(self, 'dns_server_manager') else [],
                enable_cache=self.enable_cache_check.isChecked(),
                default_cache_ttl=self.cache_ttl_spin.value(),
                cleanup_interval=self.cleanup_interval_spin.value() if self.cleanup_interval_spin.value() > 60 else None,
                max_cache_size=self.max_cache_spin.value(),
                enable_system_dns=self.system_dns_check.isChecked(),
                resolve_strategy="parallel" if self.strategy_combo.currentIndex() == 1 else "serial",
                serial_timeout=self.serial_timeout_spin.value(),
                parallel_timeout=self.parallel_timeout_spin.value(),
                parallel_workers=self.parallel_workers_spin.value(),
            )

            # 黑名单
            if hasattr(self, 'blacklist_manager'):
                exact_domains, patterns = self.blacklist_manager.get_blacklist()
                dns_config.blacklist_domains = exact_domains
                dns_config.blacklist_patterns = patterns

            return dns_config

        except Exception as e:
            logger.error(f"获取DNS配置失败: {e}")
            # 出错时返回默认配置
            return DNSConfig()

    def set_config(self, config: DNSConfig):
        """给UI设置DNSConfig对象"""
        try:
            # 标记开始加载配置，避免触发修改信号
            self._is_loading_config = True

            # 确保传入的是DNSConfig对象
            if not isinstance(config, DNSConfig):
                if isinstance(config, dict):
                    # 如果是字典，转换为DNSConfig对象
                    config = DNSConfig.from_dict(config)
                else:
                    # 其他类型，使用默认配置
                    config = DNSConfig.get_default_config()

            # 1. 基础设置
            self.enable_dns_check.setChecked(config.enable_remote_dns_resolve)
            self.name_edit.setText(config.name)

            # 2. 解析策略
            if config.resolve_strategy == 'parallel':
                self.strategy_combo.setCurrentIndex(1)
                self.parallel_timeout_spin.setValue(config.parallel_timeout)
                self.parallel_workers_spin.setValue(config.parallel_workers)
            else:
                self.strategy_combo.setCurrentIndex(0)
                self.serial_timeout_spin.setValue(config.serial_timeout)

            # 3. 系统DNS和缓存
            self.system_dns_check.setChecked(config.enable_system_dns)
            self.enable_cache_check.setChecked(config.enable_cache)
            self.cache_ttl_spin.setValue(config.default_cache_ttl)

            # 清理间隔（None表示禁用）
            cleanup_interval = config.cleanup_interval
            if cleanup_interval is None:
                self.cleanup_interval_spin.setValue(60)  # 显示为"禁用"
            else:
                self.cleanup_interval_spin.setValue(cleanup_interval)

            self.max_cache_spin.setValue(config.max_cache_size)

            # 4. DNS服务器列表
            if hasattr(self, 'dns_server_manager'):
                dns_servers = config.dns_servers
                self.dns_server_manager.set_servers(dns_servers)

            # 5. 黑名单
            if hasattr(self, 'blacklist_manager'):
                exact_domains = config.blacklist_domains
                patterns = config.blacklist_patterns
                self.blacklist_manager.set_blacklist(exact_domains, patterns)

            # 6. 更新UI状态
            self.on_enable_dns_changed()
            self.on_strategy_changed()
            self.on_cache_enabled_changed()

            # 7. 重置修改标记
            self.clear_modified()

        except Exception as e:
            logger.error(f"设置DNS配置失败: {e}")
            # 出错时使用默认配置
            try:
                self.set_config(DNSConfig.get_default_config())
            except Exception as inner_e:
                logger.error(f"回退到默认配置也失败: {inner_e}")
                # 最终回退：禁用DNS功能
                self.enable_dns_check.setChecked(False)
                self.on_enable_dns_changed()
        finally:
            self._is_loading_config = False

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        if not self.enable_dns_check.isChecked():
            return True, "使用系统默认DNS解析"

        dns_servers = []
        if hasattr(self, 'dns_server_manager'):
            dns_servers = self.dns_server_manager.get_servers()

        if not dns_servers:
            return False, "请至少配置一个DNS服务器"

        name = self.name_edit.text().strip()
        if not name:
            return False, "请填写解析器名称"

        return True, "DNS配置验证通过"
