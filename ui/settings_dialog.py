# -*- coding: utf-8 -*-
"""
Module: settings_dialog.py
Author: Takeshi
Date: 2025-12-26

Description:
    设置对话框
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QMessageBox, QFileDialog,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon

from defaults.user_default import USER_CONFIG_FILE
from defaults.ui_default import SETTINGS_DIALOG_MIN_SIZE, DIALOG_ICOINS

from defaults.config_manager import get_config_manager

# 导入所有配置dataclass
from defaults.proxy_default import Socks5Proxy, HttpProxy

# 导入标签页
from .settings_tab.proxy_settings_tab import OutboundInterfaceTab, Socks5SettingsTab, HttpSettingsTab
from .settings_tab.dns_settings_tab import DNSSettingsTab
from .settings_tab.ip_geo_settings_tab import IPGeoSettingsTab
from .settings_tab.security_settings_tab import SecuritySettingsTab
from .settings_tab.other_settings_tab import OtherSettingsTab
from .settings_tab.log_settings_tab import LogSettingsTab
from .settings_tab.about_tab import AboutTab

from managers.user_manager import UserManager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self,
                user_manager: UserManager,
                current_config: Optional[Dict[str, Any]] = None,
                parent=None):
        super().__init__(parent)

        self.user_manager = user_manager
        self.config_manager = get_config_manager()

        # 使用dataclass对象存储当前配置
        self.current_config_objects = {
            'BIND_INTERFACE_CONFIG': None,
            'SOCKS5_PROXY_CONFIG': [],
            'HTTP_PROXY_CONFIG': [],
            'DNS_CONFIG': None,
            'IP_GEO_CONFIG': None,
            'SECURITY_CONFIG': None,
            'STATS_CONFIG': None,
            'HEALTH_CHECK_CONFIG': None,
            'LOG_CONFIG': None
        }

        # 如果传入了配置，更新到ConfigManager中
        if current_config:
            self.config_manager.set_all_from_dicts(current_config)

        # 从ConfigManager获取所有dataclass对象
        self._load_config_objects()

        self.modified = False
        self.setWindowTitle("BindInterfaceProxy - 设置")
        self.setMinimumSize(*SETTINGS_DIALOG_MIN_SIZE)
        # 启用对话框的最小化和最大化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        self.setModal(False)

        self.modified_tabs = set()  # 存储有修改的标签页名称

        self.init_ui()
        self.load_current_config()

    def _load_config_objects(self):
        """从ConfigManager加载所有配置对象"""
        for config_name in self.current_config_objects.keys():
            try:
                config_obj = self.config_manager.get_config(config_name)
                self.current_config_objects[config_name] = config_obj
            except Exception as e:
                logger.error(f"加载配置 {config_name} 失败: {e}")
                # 使用默认配置
                default_obj = self.config_manager.get_default_config(config_name)
                self.current_config_objects[config_name] = default_obj

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 标签页
        self.tab_widget = QTabWidget()

        # 创建标签页
        self.outbound = OutboundInterfaceTab()
        self.socks5_tab = Socks5SettingsTab()
        self.http_tab = HttpSettingsTab()

        # 获取绑定接口配置对象
        bind_config = self.current_config_objects['BIND_INTERFACE_CONFIG']
        self.dns_tab = DNSSettingsTab(bind_interface_config=bind_config)

        self.ip_geo_tab = IPGeoSettingsTab()
        self.security_tab = SecuritySettingsTab()
        self.other_tab = OtherSettingsTab()
        self.log_tab = LogSettingsTab()
        self.about_tab = AboutTab()

        # 连接信号
        self.outbound.config_modified.connect(self.update_dns_bind_config)

        # 为所有标签页连接修改信号
        tabs = [
            (self.outbound, "出口网络设置"),
            (self.socks5_tab, "SOCKS5代理"),
            (self.http_tab, "HTTP/HTTPS代理"),
            (self.dns_tab, "DNS解析设置"),
            (self.ip_geo_tab, "IP地理位置"),
            (self.security_tab, "安全管理"),
            (self.other_tab, "其他配置"),
            (self.log_tab, "日志设置"),
            (self.about_tab, "关于")
        ]

        for tab, tab_name in tabs:
            if hasattr(tab, 'config_modified'):
                # 使用lambda捕获标签页名称
                tab.config_modified.connect(
                    lambda checked=False, name=tab_name: self.mark_modified(name)
                )

        # 添加标签页
        for tab, tab_name in tabs:
            self.tab_widget.addTab(tab, tab_name)

        layout.addWidget(self.tab_widget)

        # 状态标签
        self.status_label = QLabel()
        self.status_label.setMinimumHeight(50)
        layout.addWidget(self.status_label)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.export_btn = QPushButton("导出")
        self.export_btn.clicked.connect(self.export_settings)

        self.import_btn = QPushButton("导入")
        self.import_btn.clicked.connect(self.import_settings)

        self.open_folder_btn = QPushButton("打开配置文件夹")
        self.open_folder_btn.clicked.connect(self.open_config_folder)
        self.open_folder_btn.setToolTip(f"打开配置文件所在的文件夹\n配置文件: {USER_CONFIG_FILE}")

        self.open_usrmgr_btn = QPushButton("打开用户管理")
        self.open_usrmgr_btn.clicked.connect(self.open_usrmgr_dialog)
        self.open_usrmgr_btn.setToolTip(f"打开用户管理界面")

        self.restore_default_btn = QPushButton("恢复本页默认值")
        self.restore_default_btn.clicked.connect(self.restore_defaults)
        self.restore_default_btn.setEnabled(False)  # 默认禁用

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_all)
        self.save_btn.setEnabled(False)

        self.restart_btn = QPushButton("重启")
        self.restart_btn.clicked.connect(self.restart)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(self.open_usrmgr_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.restore_default_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.restart_btn)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 标签页切换时更新按钮状态
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        """标签页切换事件"""
        self.restore_default_btn.setEnabled(3 <= index <= 7)

    def update_dns_bind_config(self):
        """更新DNS标签页的绑定接口配置"""
        try:
            # 获取出口网络配置对象
            bind_config = self.outbound.get_config()
            # 更新DNS标签页的绑定配置
            if hasattr(self.dns_tab, 'update_bind_interface_config'):
                self.dns_tab.update_bind_interface_config(bind_config)
            logger.debug(f"DNS标签页绑定配置已更新: {bind_config}")
        except Exception as e:
            logger.error(f"更新DNS绑定配置失败: {e}")

    def open_config_folder(self):
        """打开配置文件所在的文件夹"""
        try:
            import platform
            import subprocess

            # 获取配置文件路径
            config_file = USER_CONFIG_FILE
            config_dir = os.path.dirname(config_file)

            # 如果目录不存在，尝试创建
            if not os.path.exists(config_dir):
                try:
                    os.makedirs(config_dir, exist_ok=True)
                    logger.info(f"创建配置目录: {config_dir}")
                except Exception as e:
                    logger.error(f"创建配置目录失败: {e}")
                    QMessageBox.warning(self, "错误", f"无法创建配置目录:\n{str(e)}")
                    return

            # 打开文件夹
            system = platform.system()

            if system == "Windows":
                # Windows: 使用explorer打开
                subprocess.run(['explorer', config_dir])
            elif system == "Darwin":  # macOS
                # macOS: 使用open打开
                subprocess.run(['open', config_dir])
            else:  # Linux
                # Linux: 使用xdg-open或nautilus
                try:
                    subprocess.run(['xdg-open', config_dir])
                except FileNotFoundError:
                    try:
                        subprocess.run(['nautilus', config_dir])
                    except FileNotFoundError:
                        try:
                            subprocess.run(['dolphin', config_dir])
                        except FileNotFoundError:
                            QMessageBox.warning(self, "错误",
                                            "无法找到文件管理器，请手动打开:\n" + config_dir)

            self.show_status(f"已打开配置文件夹: {config_dir}", "info")

        except Exception as e:
            logger.error(f"打开配置文件夹失败: {e}")
            QMessageBox.warning(self, "错误", f"打开配置文件夹失败:\n{str(e)}")

    def open_usrmgr_dialog(self):
        from .user_manager_dialog import UserManagerDialog
        dialog = UserManagerDialog(self.user_manager)
        dialog.exec()

    def restore_defaults(self):
        """恢复当前标签页的默认值"""
        current_index = self.tab_widget.currentIndex()

        # 确认对话框
        reply = QMessageBox.question(
            self, "恢复默认值",
            "确定要恢复当前标签页的默认值吗？\n当前配置将被覆盖。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 获取默认配置对象
            default_config = self.get_default_config_for_tab(current_index)

            # 获取当前标签页
            current_tab = self.tab_widget.widget(current_index)
            if current_tab and hasattr(current_tab, 'set_config'):
                # 设置默认配置对象
                current_tab.set_config(default_config)
                # 标记为已修改
                self.mark_modified()
                # 显示状态
                tab_name = self.tab_widget.tabText(current_index)
                self.show_status(f"已恢复 {tab_name} 的默认值，请保存应用", "info")

    def get_default_config_for_tab(self, tab_index: int) -> Any:
        """获取标签页的默认配置对象"""
        if tab_index == 3:  # DNS配置
            return self.config_manager.get_default_config('DNS_CONFIG')
        elif tab_index == 4:  # IP地理位置配置
            return self.config_manager.get_default_config('IP_GEO_CONFIG')
        elif tab_index == 5:  # 安全管理配置
            return self.config_manager.get_default_config('SECURITY_CONFIG')
        elif tab_index == 6:  # 其他配置
            return {
                'STATS_CONFIG': self.config_manager.get_default_config('STATS_CONFIG'),
                'HEALTH_CHECK_CONFIG': self.config_manager.get_default_config('HEALTH_CHECK_CONFIG')
            }
        elif tab_index == 7:  # 日志配置
            return self.config_manager.get_default_config('LOG_CONFIG')

        # 前三个标签页
        if tab_index == 0:  # 出口网络
            return self.config_manager.get_default_config('BIND_INTERFACE_CONFIG')
        elif tab_index == 1:  # SOCKS5
            return []
        elif tab_index == 2:  # HTTP
            return []

        return None

    def load_current_config(self):
        """加载当前配置对象到标签页"""
        try:
            # 设置各个标签页的配置对象
            self.outbound.set_config(self.current_config_objects['BIND_INTERFACE_CONFIG'])
            self.socks5_tab.set_config(self.current_config_objects['SOCKS5_PROXY_CONFIG'])
            self.http_tab.set_config(self.current_config_objects['HTTP_PROXY_CONFIG'])
            self.dns_tab.set_config(self.current_config_objects['DNS_CONFIG'])
            self.ip_geo_tab.set_config(self.current_config_objects['IP_GEO_CONFIG'])
            self.security_tab.set_config(self.current_config_objects['SECURITY_CONFIG'])

            # 其他配置需要特殊处理
            other_config = {
                'STATS_CONFIG': self.current_config_objects['STATS_CONFIG'],
                'HEALTH_CHECK_CONFIG': self.current_config_objects['HEALTH_CHECK_CONFIG']
            }
            self.other_tab.set_config(other_config)

            self.log_tab.set_config(self.current_config_objects['LOG_CONFIG'])

            logger.debug("配置已加载到UI标签页")

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.show_status(f"加载失败: {e}", "error")

    def mark_modified(self, tab_name=None):
        """标记配置已修改，并记录哪个标签页"""
        self.modified = True
        self.save_btn.setEnabled(True)

        if tab_name:
            self.modified_tabs.add(tab_name)

    def collect_all_configs(self) -> Dict[str, Any]:
        """收集所有标签页的配置对象"""
        try:
            config_objects = {
                'BIND_INTERFACE_CONFIG': self.outbound.get_config(),
                'SOCKS5_PROXY_CONFIG': self.socks5_tab.get_config(),
                'HTTP_PROXY_CONFIG': self.http_tab.get_config(),
                'DNS_CONFIG': self.dns_tab.get_config(),
                'IP_GEO_CONFIG': self.ip_geo_tab.get_config(),
                'SECURITY_CONFIG': self.security_tab.get_config()
            }

            # 其他配置
            other_config = self.other_tab.get_config()
            config_objects['STATS_CONFIG'] = other_config.get('STATS_CONFIG')
            config_objects['HEALTH_CHECK_CONFIG'] = other_config.get('HEALTH_CHECK_CONFIG')

            config_objects['LOG_CONFIG'] = self.log_tab.get_config()

            # 验证所有配置对象都不是None
            for name, config in config_objects.items():
                if config is None:
                    logger.warning(f"配置 {name} 为None，使用默认配置")
                    default_config = self.config_manager.get_default_config(name)
                    config_objects[name] = default_config

            return config_objects

        except Exception as e:
            logger.error(f"收集配置失败: {e}")
            # 返回当前配置对象作为回退
            return self.current_config_objects.copy()

    def validate_proxy_confict(self) -> Tuple[bool, str]:
        """验证所有代理ip和端口是否有冲突"""
        try:
            socks5_configs: List[Socks5Proxy] = self.socks5_tab.get_config()
            http_configs: List[HttpProxy] = self.http_tab.get_config()

            # 使用字典存储已出现的IP+端口组合
            port_ip_map = {}  # key: f"{ip}:{port}" -> dict of proxy_info
            conflicts = []

            def get_actual_ip(proxy_config) -> Tuple[str, bool]:
                """获取配置的实际IP地址"""
                if isinstance(proxy_config, (Socks5Proxy, HttpProxy)):
                    ip = proxy_config.ip
                    if not ip and proxy_config.iface_name:
                        try:
                            from utils.interface_utils import NetworkInterface
                            iface = NetworkInterface(iface_name=proxy_config.iface_name)
                            ip = iface.ip
                            return ip, True  # 返回IP和是否来自接口
                        except Exception:
                            return f"接口:{proxy_config.iface_name}", False
                    return ip, True if ip else False
                return "", False

            # 检查SOCKS5代理
            for i, proxy in enumerate(socks5_configs):
                port = proxy.port
                if not port:  # 跳过无端口的（如自动分配端口）
                    continue

                ip, is_real_ip = get_actual_ip(proxy)
                if not ip:
                    continue  # 无法确定IP，跳过

                key = f"{ip}:{port}"
                if key in port_ip_map:
                    # 找到冲突
                    existing_proxy = port_ip_map[key]

                    # 判断冲突类型
                    conflict_type = "确定冲突" if is_real_ip and existing_proxy.get('is_real_ip') else "可能冲突"

                    conflicts.append({
                        'type': conflict_type,
                        'message': f"{conflict_type}: IP {ip}:端口 {port} - "
                                f"{existing_proxy['type']}代理 [{existing_proxy['name']}] "
                                f"与 SOCKS5代理 [{proxy.proxy_name or f'SOCKS5-{i+1}'}]",
                        'is_certain': is_real_ip and existing_proxy.get('is_real_ip')
                    })
                else:
                    port_ip_map[key] = {
                        'type': 'SOCKS5',
                        'name': proxy.proxy_name or f'SOCKS5-{i+1}',
                        'config': proxy,
                        'is_real_ip': is_real_ip
                    }

            # 检查HTTP代理
            for i, proxy in enumerate(http_configs):
                port = proxy.port
                if not port:  # 跳过无端口的
                    continue

                ip, is_real_ip = get_actual_ip(proxy)
                if not ip:
                    continue

                proxy_type = 'HTTP' + ('S' if proxy.use_https else '')
                key = f"{ip}:{port}"

                if key in port_ip_map:
                    # 找到冲突
                    existing_proxy = port_ip_map[key]

                    # 判断冲突类型
                    conflict_type = "确定冲突" if is_real_ip and existing_proxy.get('is_real_ip') else "可能冲突"

                    conflicts.append({
                        'type': conflict_type,
                        'message': f"{conflict_type}: IP {ip}:端口 {port} - "
                                f"{existing_proxy['type']}代理 [{existing_proxy['name']}] "
                                f"与 {proxy_type}代理 [{proxy.proxy_name or f'HTTP-{i+1}'}]",
                        'is_certain': is_real_ip and existing_proxy.get('is_real_ip')
                    })
                else:
                    port_ip_map[key] = {
                        'type': proxy_type,
                        'name': proxy.proxy_name or f'HTTP-{i+1}',
                        'config': proxy,
                        'is_real_ip': is_real_ip
                    }

            if conflicts:
                # 分离确定冲突和可能冲突
                certain_conflicts = [c['message'] for c in conflicts if c['is_certain']]
                possible_conflicts = [c['message'] for c in conflicts if not c['is_certain']]

                error_parts = []

                if certain_conflicts:
                    error_parts.append("❌ 确定冲突:")
                    error_parts.extend(certain_conflicts)

                if possible_conflicts:
                    if error_parts:
                        error_parts.append("")  # 空行
                    error_parts.append("⚠️ 可能冲突（基于接口检测，运行时需要检查）:")
                    error_parts.extend(possible_conflicts)

                error_msg = "发现代理配置冲突:\n\n" + "\n".join(error_parts)

                # 如果有确定的冲突，直接返回失败
                if certain_conflicts:
                    return False, error_msg
                else:
                    # 只有可能的冲突，询问用户
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("可能的配置冲突")
                    msg_box.setText(error_msg + "\n\n是否继续保存？")
                    msg_box.setIcon(QMessageBox.Warning)

                    yes_btn = msg_box.addButton("继续保存", QMessageBox.YesRole)
                    no_btn = msg_box.addButton("取消", QMessageBox.NoRole)

                    msg_box.setDefaultButton(no_btn)
                    msg_box.exec()

                    if msg_box.clickedButton() == no_btn:
                        return False, "用户取消保存"
                    else:
                        # 用户选择继续，记录警告
                        logger.warning("用户忽略可能的配置冲突继续保存")
                        return True, "用户确认忽略可能的冲突"

            return True, "代理端口校验通过"

        except Exception as e:
            logger.error(f"验证代理配置失败: {e}")
            return False, f"验证失败: {e}"

    def has_auth_config(self) -> Tuple[bool, str]:
        """检查是否有认证配置"""
        try:
            socks5_configs: List[Socks5Proxy] = self.socks5_tab.get_config()
            http_configs: List[HttpProxy] = self.http_tab.get_config()
            for proxy in socks5_configs or []:
                if hasattr(proxy, 'auth_enabled') and proxy.auth_enabled:
                    return True, 'SOCKS5-有代理启用认证'

            for proxy in http_configs or []:
                if hasattr(proxy, 'auth_enabled') and proxy.auth_enabled:
                    return True, 'HTTP-有代理启用认证'
        except Exception:
            pass

        return False, ""

    def validate_user_config(self) -> Tuple[bool, str]:
        """检查用户配置，如果没有用户则弹出管理窗口"""
        user_count = self.user_manager.get_user_count()
        logger.info(f"当前用户数量: {user_count}")

        if user_count == 0:
            logger.info("未找到用户配置，需要先添加用户")
            from .user_manager_dialog import UserManagerDialog
            # 使用UserManagerDialog，并设置require_first_user=True
            dialog = UserManagerDialog(self.user_manager, require_first_user=True)
            result = dialog.exec()

            user_count = self.user_manager.get_user_count()
            if user_count == 0:
                logger.info("用户取消配置，程序退出")
                return False, "未添加任何用户"
            else:
                logger.info(f"用户配置完成，当前用户数量: {user_count}")

        return True, """已添加用户"""


    def validate_all_tabs(self) -> Tuple[bool, str]:
        """验证所有标签页"""
        tabs = [
            self.outbound, self.socks5_tab, self.http_tab,
            self.dns_tab, self.ip_geo_tab, self.security_tab,
            self.other_tab, self.log_tab, self.about_tab
        ]

        for i, tab in enumerate(tabs):
            if hasattr(tab, 'validate_config'):
                is_valid, msg = tab.validate_config()
                if not is_valid:
                    self.tab_widget.setCurrentIndex(i)
                    return False, f"标签页{i+1}: {msg}"

        # 验证所有代理ip和端口是否有冲突
        is_valid, error_msg = self.validate_proxy_confict()
        if not is_valid:
            # 跳转到SOCKS5或HTTP标签页
            # 简单判断：如果有SOCKS5冲突先跳SOCKS5，否则跳HTTP
            has_socks5_conflict = any('SOCKS5' in line for line in error_msg.split('\n'))
            has_http_conflict = any('HTTP' in line for line in error_msg.split('\n'))

            if has_socks5_conflict:
                self.tab_widget.setCurrentIndex(1)  # SOCKS5在索引1
            elif has_http_conflict:
                self.tab_widget.setCurrentIndex(2)  # HTTP在索引2
            else:
                # 默认跳第一个代理标签页
                self.tab_widget.setCurrentIndex(1)

            return False, error_msg

        # 验证是否启用认证和用户配置
        has_auth, auth_msg = self.has_auth_config()
        if has_auth:
            is_valid, error_msg = self.validate_user_config()
            if not is_valid:
                if auth_msg.startswith("SOCKS5"):
                    self.tab_widget.setCurrentIndex(1)  # SOCKS5在索引1
                elif auth_msg.startswith("HTTP"):
                    self.tab_widget.setCurrentIndex(2)  # HTTP在索引2
                else:
                    # 默认跳第一个代理标签页
                    self.tab_widget.setCurrentIndex(1)
                return False, auth_msg + ',' + error_msg
        return True, ""

    def save_all(self) -> bool:
        """保存所有配置"""
        try:
            # 验证所有标签页
            is_valid, error_msg = self.validate_all_tabs()
            if not is_valid:
                self.show_status(f"配置错误: {error_msg}", "error")
                return False

            # 收集配置对象
            config_objects = self.collect_all_configs()

            # 更新当前配置对象
            for config_name, config_obj in config_objects.items():
                if config_obj is not None:
                    self.current_config_objects[config_name] = config_obj

            # 使用ConfigManager设置所有配置对象
            self.config_manager.set_all_configs(config_objects)

            # 保存到文件
            success = self.config_manager.save()

            if success:
                self.modified = False
                self.modified_tabs.clear()
                self.save_btn.setEnabled(False)
                self.show_status("配置已保存", "success")

                # 保存成功后询问是否重启
                self.prompt_restart_after_save()
                return True
            else:
                self.show_status("保存失败", "error")
                return False

        except Exception as e:
            logger.error(f"保存失败: {e}")
            self.show_status(f"保存失败: {e}", "error")
            return False

    def prompt_restart_after_save(self):
        """保存成功后询问是否重启"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("配置已保存")
        msg_box.setText(
            "✅ 配置已保存成功！\n\n"
            "部分配置需要重启程序才能生效。\n"
            "是否立即重启程序？"
        )
        msg_box.setIcon(QMessageBox.Question)

        # 创建中文按钮
        yes_btn = msg_box.addButton("是，立即重启", QMessageBox.YesRole)
        no_btn = msg_box.addButton("否，稍后重启", QMessageBox.NoRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)

        # 设置默认按钮
        msg_box.setDefaultButton(yes_btn)

        msg_box.exec()

        clicked_btn = msg_box.clickedButton()

        if clicked_btn == yes_btn:
            # 立即重启
            self.restart()
        elif clicked_btn == cancel_btn:
            # 取消操作，重新启用保存按钮
            self.modified = True
            self.save_btn.setEnabled(True)
            # 可以添加一个提示
            self.show_status("已取消，配置可能需要重启后生效", "warning")

    def restart(self):
        """重启应用"""
        # 检查是否有未保存的修改
        if self.modified:
            # 生成更详细的提示信息
            modified_tabs_text = "\n".join([f"  • {tab}" for tab in self.modified_tabs])
            if not modified_tabs_text:
                modified_tabs_text = "  未知标签页"

            # 创建自定义的QMessageBox，使用中文按钮
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("未保存的修改")
            msg_box.setText(f"以下标签页有未保存的修改：\n{modified_tabs_text}\n\n是否保存？\n点击'放弃'将放弃修改。")
            msg_box.setIcon(QMessageBox.Question)

            # 创建中文按钮
            save_btn = msg_box.addButton("保存", QMessageBox.AcceptRole)
            discard_btn = msg_box.addButton("放弃", QMessageBox.DestructiveRole)
            cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)

            # 设置默认按钮
            msg_box.setDefaultButton(save_btn)

            msg_box.exec()

            clicked_btn = msg_box.clickedButton()

            if clicked_btn == save_btn:
                if not self.save_all():
                    return  # 保存失败，不重启
            elif clicked_btn == cancel_btn:
                return  # 取消重启
            # 如果选择"不保存"，则继续但不保存
        else:
            # 没有未保存的修改，添加确认对话框
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("确认重启")
            msg_box.setText("确定要重启程序吗？")
            msg_box.setIcon(QMessageBox.Question)

            # 创建中文按钮
            yes_btn = msg_box.addButton("是，重启", QMessageBox.YesRole)
            no_btn = msg_box.addButton("否，取消", QMessageBox.NoRole)

            # 设置默认按钮
            msg_box.setDefaultButton(no_btn)  # 默认选择"否"更安全

            msg_box.exec()

            clicked_btn = msg_box.clickedButton()

            if clicked_btn == no_btn:
                return  # 用户取消重启

        try:
            from utils.lifecycle_manager import get_applifecycle_manager
            get_applifecycle_manager().restart()
        except Exception as e:
            logger.error(f"重启失败: {e}")
            QMessageBox.warning(
                self,
                "重启失败",
                f"重启程序失败: {str(e)}\n请手动重启程序。"
            )
            self.accept()

    def export_settings(self):
        """导出配置"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出配置", f"proxy_config_{timestamp}.json",
                "JSON文件 (*.json)"
            )

            if file_path:
                # 收集当前配置对象
                config_objects = self.collect_all_configs()

                # 转换为字典用于导出
                export_data = {}
                for config_name, config_obj in config_objects.items():
                    if config_obj is not None:
                        if hasattr(config_obj, 'to_dict'):
                            export_data[config_name] = config_obj.to_dict()
                        else:
                            # 回退到asdict
                            from dataclasses import asdict
                            export_data[config_name] = asdict(config_obj)

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)

                self.show_status(f"配置已导出到: {file_path}", "success")

        except Exception as e:
            logger.error(f"导出失败: {e}")
            self.show_status(f"导出失败: {e}", "error")

    def import_settings(self):
        """导入配置"""
        try:
            reply = QMessageBox.question(
                self, "导入确认",
                "导入将覆盖当前配置，是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入配置", "", "JSON文件 (*.json)"
            )

            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_dict = json.load(f)

                # 验证导入的配置结构
                if not isinstance(imported_dict, dict):
                    QMessageBox.warning(self, "导入错误", "配置文件格式不正确")
                    return

                # 使用ConfigManager从字典更新配置
                self.config_manager.set_all_from_dicts(imported_dict)

                # 重新加载配置对象
                self._load_config_objects()

                # 更新UI
                self.load_current_config()
                self.mark_modified()
                self.show_status("配置已导入", "success")

        except Exception as e:
            logger.error(f"导入失败: {e}")
            self.show_status(f"导入失败: {e}", "error")

    def show_status(self, message: str, msg_type: str = "info"):
        """显示状态消息"""
        colors = {"info": "blue", "success": "green", "warning": "orange", "error": "red"}
        color = colors.get(msg_type, "black")
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; padding: 5px;")

        # 5秒后清除
        QTimer.singleShot(5000, lambda: self.clear_status(message))

    def clear_status(self, message: str):
        """清除状态消息"""
        if self.status_label.text() == message:
            self.status_label.clear()

    def closeEvent(self, event):
        """关闭事件处理"""
        if self.modified:
            # 生成更详细的提示信息
            modified_tabs_text = "\n".join([f"  • {tab}" for tab in self.modified_tabs])
            if not modified_tabs_text:
                modified_tabs_text = "  未知标签页"

            # 创建自定义的QMessageBox，使用中文按钮
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("未保存的修改")
            msg_box.setText(f"以下标签页有未保存的修改：\n{modified_tabs_text}\n\n是否保存？\n点击'放弃'将放弃修改。")
            msg_box.setIcon(QMessageBox.Question)

            # 创建中文按钮
            save_btn = msg_box.addButton("保存", QMessageBox.AcceptRole)
            discard_btn = msg_box.addButton("放弃", QMessageBox.DestructiveRole)
            cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)

            # 设置默认按钮
            msg_box.setDefaultButton(save_btn)

            msg_box.exec()

            clicked_btn = msg_box.clickedButton()

            if clicked_btn == save_btn:
                # 尝试保存
                try:
                    if self.save_all():
                        # 保存成功后，prompt_restart_after_save() 会处理重启询问
                        pass
                    else:
                        QMessageBox.warning(
                            self, "保存失败",
                            "保存失败，将放弃修改。"
                        )
                except Exception as e:
                    logger.error(f"保存失败: {e}")
                    QMessageBox.warning(
                        self, "保存失败",
                        f"保存失败: {str(e)}\n将放弃修改。"
                    )

            elif clicked_btn == cancel_btn:
                event.ignore()
                return

        # 首次配置
        elif not os.path.exists(USER_CONFIG_FILE):
            # 创建自定义的QMessageBox，使用中文按钮
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("首次配置")
            msg_box.setText("这是首次配置，是否保存？\n点击'否'将不会创建配置文件。")
            msg_box.setIcon(QMessageBox.Question)

            # 创建中文按钮
            save_btn = msg_box.addButton("保存", QMessageBox.AcceptRole)
            no_btn = msg_box.addButton("否", QMessageBox.NoRole)
            cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)

            # 设置默认按钮
            msg_box.setDefaultButton(save_btn)

            msg_box.exec()

            clicked_btn = msg_box.clickedButton()

            if clicked_btn == save_btn:
                try:
                    if self.save_all():
                        # 首次保存成功后，prompt_restart_after_save() 会处理重启询问
                        pass
                    else:
                        QMessageBox.warning(
                            self, "保存失败",
                            "保存失败，将不会创建配置文件。"
                        )
                except Exception as e:
                    logger.error(f"保存失败: {e}")
                    QMessageBox.warning(
                        self, "保存失败",
                        f"保存失败: {str(e)}\n将不会创建配置文件。"
                    )
            elif clicked_btn == cancel_btn:
                event.ignore()
                return

        event.accept()
