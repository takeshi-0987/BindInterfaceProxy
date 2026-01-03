# -*- coding: utf-8 -*-
"""
Module: proxy_settings_tab.py
Author: Takeshi
Date: 2025-12-26

Description:
    代理设置页
"""



import os
import logging
from typing import Dict, Any, Tuple, Optional, List, Literal

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QMessageBox, QGridLayout, QSizePolicy,
    QCheckBox, QLineEdit, QComboBox, QFileDialog, QListWidget,
    QAbstractItemView, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator

# 导入配置dataclass
from defaults.proxy_default import OutboundInterface, Socks5Proxy, HttpProxy
from utils import NetworkInterface

logger = logging.getLogger(__name__)


class NetworkInterfaceSelector(QWidget):
    """网络接口选择器"""

    # 定义信号
    config_modified = Signal()

    def __init__(self, iface_kind: Literal['outbound', 'listen'], parent=None):
        super().__init__(parent)
        self.iface_kind = iface_kind
        self.network_interfaces = []
        self.modified = False  # 修改状态
        self.interface_load_failed = False  # 接口加载失败标志
        self.init_ui()
        self.load_interfaces()

    def init_ui(self):
        # 主布局
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 网络接口选择区域
        self.interface_combo = QComboBox()
        self.interface_combo.setMinimumHeight(30)
        self.interface_combo.currentIndexChanged.connect(self.on_iface_selection)
        self.interface_combo.currentIndexChanged.connect(self.mark_modified)

        layout.addWidget(QLabel("网络接口:"))
        layout.addWidget(self.interface_combo)

        # 自定义配置选项
        self.self_config = QCheckBox("列表里没有，我自己配置IP")
        self.self_config.stateChanged.connect(self.self_configure_ip)
        self.self_config.stateChanged.connect(self.mark_modified)
        layout.addWidget(self.self_config)

        # IP地址和端口配置
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)

        # IP地址
        self.ip_edit = QLineEdit()
        ip_regex = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        ip_validator = QRegularExpressionValidator(QRegularExpression(ip_regex))
        self.ip_edit.setValidator(ip_validator)
        self.ip_edit.setPlaceholderText("请输入 IPv4 地址，如 192.168.1.1")
        self.ip_edit.setEnabled(False)
        self.ip_edit.setMinimumHeight(30)
        self.ip_edit.textChanged.connect(self.mark_modified)

        # 端口配置
        self.port_edit = QLineEdit()
        self.port_edit.setMinimumHeight(30)
        port_validator = QIntValidator(1, 65535)
        self.port_edit.setValidator(port_validator)
        self.port_edit.setPlaceholderText("1-65535")
        self.port_edit.textChanged.connect(self.mark_modified)

        # 自动分配端口复选框
        self.auto_port_checkbox = QCheckBox("自动分配端口")
        self.auto_port_checkbox.stateChanged.connect(self.on_auto_port_changed)
        self.auto_port_checkbox.stateChanged.connect(self.mark_modified)

        # 调整布局
        grid_layout.addWidget(QLabel("IP地址:"), 0, 0)
        grid_layout.addWidget(self.ip_edit, 0, 1)

        grid_layout.addWidget(QLabel("端口:"), 1, 0)

        # 创建水平布局用于端口输入框和复选框
        port_layout = QHBoxLayout()
        port_layout.addWidget(self.port_edit)
        port_layout.addWidget(self.auto_port_checkbox)
        port_layout.addStretch()

        grid_layout.addLayout(port_layout, 1, 1)

        layout.addLayout(grid_layout)
        layout.addSpacing(10)

        self.setLayout(layout)
        self.on_auto_port_changed()

    def on_auto_port_changed(self):
        """自动端口复选框状态改变"""
        if self.auto_port_checkbox.isChecked():
            self.port_edit.setEnabled(False)
            self.port_edit.clear()
        else:
            self.port_edit.setEnabled(True)

    def load_interfaces(self):
        """加载网络接口列表"""
        try:
            interfaces = []
            if self.iface_kind == 'outbound':
                from utils.interface_utils import get_outbound_interfaces
                interfaces = get_outbound_interfaces()
            elif self.iface_kind == 'listen':
                from utils.interface_utils import get_listening_interfaces
                interfaces = get_listening_interfaces()

            self.interface_combo.clear()
            self.interface_load_failed = False

            self.interface_combo.addItem("请选择网络接口", None)

            for interface in interfaces:
                display_text = interface.get('display_name', '未查到接口 - 请手动配置')
                iface_name = interface.get('iface_name', None)
                self.interface_combo.addItem(display_text, iface_name)

            self.interface_combo.setCurrentIndex(0)

        except Exception as e:
            logger.error(f"加载网络接口失败: {e}")
            self.interface_combo.clear()
            self.interface_combo.addItem("加载失败 - 请手动配置", None)
            self.interface_combo.setCurrentIndex(0)
            self.interface_load_failed = True

    def get_config(self) -> OutboundInterface:
        """获取配置，返回OutboundInterface对象"""
        try:
            port_text = self.port_edit.text()
            port = int(port_text) if port_text else 0
        except ValueError:
            port = 0

        # 如果自动分配端口，使用0
        if self.auto_port_checkbox.isChecked():
            port = 0

        if self.self_config.isChecked():
            return OutboundInterface(
                iface_name="",
                ip=self.ip_edit.text(),
                port=port
            )
        else:
            if self.interface_combo.currentIndex() > 0:
                iface_name = self.interface_combo.currentData()
                return OutboundInterface(
                    iface_name=iface_name if iface_name else "",
                    ip="",  # 未选择自定义IP时，ip为空
                    port=port
                )
            else:
                return OutboundInterface(
                    iface_name="",
                    ip="",
                    port=port
                )

    def set_config(self, config: OutboundInterface):
        """设置配置，传入OutboundInterface对象"""
        if not isinstance(config, OutboundInterface):
            # 如果是字典，转换为OutboundInterface
            if isinstance(config, dict):
                config = OutboundInterface.from_dict(config)
            else:
                config = OutboundInterface()  # 使用默认配置

        # 保存当前信号阻塞状态
        was_blocked = self.signalsBlocked()

        # 阻塞所有信号
        self.blockSignals(True)
        self.interface_combo.blockSignals(True)
        self.self_config.blockSignals(True)
        self.ip_edit.blockSignals(True)
        self.port_edit.blockSignals(True)
        self.auto_port_checkbox.blockSignals(True)

        try:
            # 清除修改标记
            self.modified = False

            # 设置自动端口
            if config.port == 0:
                self.auto_port_checkbox.setChecked(True)
                self.port_edit.clear()
                self.port_edit.setEnabled(False)
            else:
                self.auto_port_checkbox.setChecked(False)
                self.port_edit.setEnabled(True)
                self.port_edit.setText(str(config.port))

            # 关键：判断是否手动配置模式
            if config.ip:  # 如果有IP，说明是手动配置模式
                self.self_config.setChecked(True)
                self.interface_combo.setCurrentIndex(0)  # 清空接口选择
                self.ip_edit.setText(config.ip)
                self.ip_edit.setEnabled(True)
                self.interface_combo.setEnabled(False)
            else:  # 接口选择模式
                self.self_config.setChecked(False)
                self.ip_edit.clear()
                self.ip_edit.setEnabled(False)
                self.interface_combo.setEnabled(True)

                # 查找匹配的接口
                if config.iface_name:
                    for idx in range(1, self.interface_combo.count()):
                        if self.interface_combo.itemData(idx) == config.iface_name:
                            self.interface_combo.setCurrentIndex(idx)
                            try:
                                ip = NetworkInterface(iface_name=config.iface_name).ip
                                self.ip_edit.setText(ip)
                            except Exception as e:
                                logger.error(f"获取接口IP失败: {e}")
                                self.ip_edit.clear()
                            break
                    else:
                        # 没找到对应接口，设为第一个（请选择网络接口）
                        self.interface_combo.setCurrentIndex(0)
                else:
                    self.interface_combo.setCurrentIndex(0)

        finally:
            # 恢复信号状态
            self.auto_port_checkbox.blockSignals(False)
            self.port_edit.blockSignals(False)
            self.ip_edit.blockSignals(False)
            self.self_config.blockSignals(False)
            self.interface_combo.blockSignals(False)
            self.blockSignals(False)

            if not was_blocked:
                self.blockSignals(False)

    def validate_interface(self) -> Tuple[bool, str]:
        """验证配置并检查接口"""
        # 检查接口是否加载失败
        if self.interface_load_failed and not self.self_config.isChecked():
            return False, "网络接口加载失败，请手动配置IP或重启程序"

        # 基本验证
        if self.auto_port_checkbox.isChecked():
            port = 0
        else:
            port_text = self.port_edit.text()
            if not port_text:
                return False, "请填写端口号"

            try:
                port = int(port_text)
                if port < 1 or port > 65535:
                    return False, "端口号必须在1-65535范围内"
            except ValueError:
                return False, "端口号必须是数字"

        # 实际的接口验证
        try:
            from utils.interface_utils import NetworkInterface

            if self.self_config.isChecked():
                ip = self.ip_edit.text()
                if not ip:
                    return False, "请填写IP地址"

                # 验证IP格式
                if not self.ip_edit.hasAcceptableInput():
                    return False, "IP地址格式不正确"

                # 尝试创建接口对象验证
                iface = NetworkInterface(ip=ip, port=port)

                return True, f"手动配置验证通过: {iface.iface_name}"
            else:
                if self.interface_combo.currentIndex() <= 0:
                    return False, "请选择网络接口"
                iface_name = self.interface_combo.currentData()
                iface = NetworkInterface(iface_name=iface_name, port=port)
                return True, f"接口验证通过: {iface.iface_name}"

        except Exception as e:
            logger.error(f"验证接口信息失败: {e}")
            return False, f"接口验证失败: {str(e)}"

    def self_configure_ip(self):
        """自己设置IP复选框"""
        if self.self_config.isChecked():
            self.interface_combo.setEnabled(False)
            self.ip_edit.setEnabled(True)
            self.ip_edit.clear()
        else:
            if self.interface_load_failed:
                self.load_interfaces()
            self.interface_combo.setEnabled(True)
            self.ip_edit.clear()
            idx = self.interface_combo.currentIndex()
            self.on_iface_selection(idx)
            self.ip_edit.setEnabled(False)

    def on_iface_selection(self, index):
        """选择接口"""
        if index <= 0:
            self.ip_edit.clear()
            self.mark_modified()
            return

        iface_name = self.interface_combo.currentData()
        if not iface_name:
            self.ip_edit.clear()
            self.mark_modified()
            return

        try:
            from utils.interface_utils import NetworkInterface
            iface = NetworkInterface(iface_name=iface_name)
            self.ip_edit.setText(iface.ip)
            self.mark_modified()
        except Exception as e:
            logger.error(f"获取接口信息失败: {e}")
            self.ip_edit.clear()
            self.mark_modified()

    def mark_modified(self):
        """标记配置已修改"""
        self.modified = True
        self.config_modified.emit()

    def clear_modified(self):
        """清除修改标记"""
        self.modified = False

    def is_modified(self) -> bool:
        """检查配置是否已修改"""
        return self.modified


class OutboundInterfaceTab(QWidget):
    """出口网卡标签页"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 页面说明标签
        self.description_label = QLabel(
            "出口网络设置：\n"
            "• 选择或配置代理服务器的出口网络接口\n"
            "• 可自动检测可用网络接口或手动配置IP\n"
            "• 端口设置为1-65535，或勾选'自动分配端口'由系统自动选择"
        )
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                margin-bottom: 10px;
                font-size: 11px;
                color: #666;
            }
        """)
        layout.addWidget(self.description_label)

        # 出口配置
        self.outbound_selector = NetworkInterfaceSelector(iface_kind='outbound')
        self.outbound_selector.config_modified.connect(self.config_modified.emit)
        layout.addWidget(self.outbound_selector)

        layout.addStretch()
        self.setLayout(layout)

    def get_config(self) -> OutboundInterface:
        """获取配置"""
        return self.outbound_selector.get_config()

    def set_config(self, config: OutboundInterface):
        """设置配置"""
        self.outbound_selector.set_config(config)

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        return self.outbound_selector.validate_interface()

    def is_modified(self) -> bool:
        """检查配置是否已修改"""
        return self.outbound_selector.is_modified()

    def clear_modified(self):
        """清除修改标记"""
        self.outbound_selector.clear_modified()


class ProxyConfigDialog(QDialog):
    """代理配置对话框（新建/编辑）"""

    def __init__(self, proxy_type="socks5", default_name="", config=None, parent=None):
        super().__init__(parent)
        self.proxy_type = proxy_type
        self.default_name = default_name
        self.config = config or {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        self.setWindowTitle(f"配置{self.proxy_type.upper()}代理")

        if self.proxy_type == "socks5":
            self.setMinimumSize(500, 420)
        else:
            self.setMinimumSize(500, 500)

        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(12, 12, 12, 12)

        # 页面说明标签
        description = f"{self.proxy_type.upper()}代理配置"
        self.description_label = QLabel(description)
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("""
            QLabel {
                padding: 6px;
                margin-bottom: 5px;
                font-size: 11px;
                color: #666;
            }
        """)
        layout.addWidget(self.description_label)

        # 基本信息组
        basic_group = QWidget()
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.setSpacing(6)

        # 名称
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        name_layout.addWidget(QLabel("名称:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(f"输入{self.proxy_type.upper()}代理名称")
        self.name_edit.setMinimumHeight(28)
        name_layout.addWidget(self.name_edit)
        basic_layout.addLayout(name_layout)

        # 网络接口选择器
        basic_layout.addWidget(QLabel("监听设置:"))
        self.interface_selector = NetworkInterfaceSelector(iface_kind='listen')
        basic_layout.addWidget(self.interface_selector)

        layout.addWidget(basic_group)

        # 功能配置组
        func_group = QWidget()
        func_layout = QVBoxLayout(func_group)
        func_layout.setSpacing(6)

        # 认证和安全管理复选框
        self.auth_check = QCheckBox("启用用户认证")
        func_layout.addWidget(self.auth_check)

        self.security_check = QCheckBox("启用安全管理")
        func_layout.addWidget(self.security_check)

        # HTTPS配置（仅HTTP代理）
        if self.proxy_type == "http":
            self.https_check = QCheckBox("启用HTTPS (SSL/TLS)")
            self.https_check.stateChanged.connect(self.on_https_changed)
            func_layout.addWidget(self.https_check)

            # 证书文件路径
            cert_layout = QHBoxLayout()
            cert_layout.setSpacing(6)
            cert_layout.addWidget(QLabel("证书文件:"))
            self.cert_edit = QLineEdit()
            self.cert_edit.setPlaceholderText("选择证书文件 (.crt/.pem)")
            self.cert_edit.setMinimumHeight(28)
            cert_layout.addWidget(self.cert_edit)
            cert_browse_btn = QPushButton("浏览...")
            cert_browse_btn.clicked.connect(self.browse_cert_file)
            cert_layout.addWidget(cert_browse_btn)
            func_layout.addLayout(cert_layout)

            # 私钥文件路径
            key_layout = QHBoxLayout()
            key_layout.setSpacing(6)
            key_layout.addWidget(QLabel("私钥文件:"))
            self.key_edit = QLineEdit()
            self.key_edit.setPlaceholderText("选择私钥文件 (.key/.pem)")
            self.key_edit.setMinimumHeight(28)
            key_layout.addWidget(self.key_edit)
            key_browse_btn = QPushButton("浏览...")
            key_browse_btn.clicked.connect(self.browse_key_file)
            key_layout.addWidget(key_browse_btn)
            func_layout.addLayout(key_layout)

            # 初始禁用证书路径
            self.cert_edit.setEnabled(False)
            self.key_edit.setEnabled(False)
            cert_browse_btn.setEnabled(False)
            key_browse_btn.setEnabled(False)

        # Proxy Protocol设置
        proxy_protocol_layout = QHBoxLayout()
        proxy_protocol_layout.setSpacing(6)

        self.enable_protocol_check = QCheckBox("启用 Proxy Protocol")
        self.enable_protocol_check.stateChanged.connect(self.on_protocol_enabled_changed)
        proxy_protocol_layout.addWidget(self.enable_protocol_check)

        proxy_protocol_layout.addWidget(QLabel("协议版本:"))

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["v1", "v2"])
        self.protocol_combo.setCurrentText("v2")
        self.protocol_combo.setMinimumHeight(28)
        self.protocol_combo.setEnabled(False)
        proxy_protocol_layout.addWidget(self.protocol_combo)

        proxy_protocol_layout.addStretch()
        func_layout.addLayout(proxy_protocol_layout)

        layout.addWidget(func_group)
        layout.addStretch()

        # 状态标签
        self.status_label = QLabel()
        self.status_label.setMinimumHeight(25)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                margin: 4px 0;
                border-radius: 3px;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.status_label)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setDefault(True)
        self.ok_btn.setMinimumHeight(32)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumHeight(32)

        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def load_config(self):
        """加载配置到界面"""
        # 如果传入的是dataclass对象，转换为字典用于显示
        if isinstance(self.config, (Socks5Proxy, HttpProxy)):
            config_dict = self.config.to_dict()
        else:
            config_dict = self.config or {}

        proxy_name = config_dict.get('proxy_name')
        logger.debug(f"proxy_name: {proxy_name}")
        if proxy_name:
            self.name_edit.setText(proxy_name)
        else:
            self.name_edit.setText(self.default_name)

        # 网络接口配置
        interface_config = OutboundInterface(
            iface_name=config_dict.get('iface_name', ''),
            ip=config_dict.get('ip', ''),
            port=config_dict.get('port', 1080 if self.proxy_type == "socks5" else 8080)
        )
        self.interface_selector.set_config(interface_config)

        # 功能配置
        self.auth_check.setChecked(config_dict.get('auth_enabled', False))
        self.security_check.setChecked(config_dict.get('security_enabled', False))

        if self.proxy_type == "http":
            if hasattr(self, 'https_check'):
                use_https = config_dict.get('use_https', False)
                self.https_check.setChecked(use_https)
                self.on_https_changed(use_https)

            if hasattr(self, 'cert_edit'):
                self.cert_edit.setText(config_dict.get('cert_file', ''))

            if hasattr(self, 'key_edit'):
                self.key_edit.setText(config_dict.get('key_file', ''))

        # Proxy Protocol
        protocol = config_dict.get('proxy_protocol', None)
        if protocol:
            self.enable_protocol_check.setChecked(True)
            index = self.protocol_combo.findText(protocol)
            if index >= 0:
                self.protocol_combo.setCurrentIndex(index)
        else:
            self.enable_protocol_check.setChecked(False)
            self.protocol_combo.setEnabled(False)

    def on_https_changed(self, state):
        """HTTPS复选框状态改变"""
        if hasattr(self, 'cert_edit'):
            enabled = bool(state)
            self.cert_edit.setEnabled(enabled)
            self.key_edit.setEnabled(enabled)

            for child in self.findChildren(QPushButton):
                if child.text() == "浏览...":
                    child.setEnabled(enabled)

    def browse_cert_file(self):
        """浏览证书文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择证书文件", "", "证书文件 (*.crt *.pem);;所有文件 (*.*)"
        )
        if file_path:
            self.cert_edit.setText(file_path)

    def browse_key_file(self):
        """浏览私钥文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择私钥文件", "", "私钥文件 (*.key *.pem);;所有文件 (*.*)"
        )
        if file_path:
            self.key_edit.setText(file_path)

    def on_protocol_enabled_changed(self, state):
        """Proxy Protocol启用状态改变"""
        self.protocol_combo.setEnabled(bool(state))

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        # 验证名称
        name = self.name_edit.text()
        if not name:
            return False, "请输入代理名称"

        # 验证网络接口
        is_valid, error_msg = self.interface_selector.validate_interface()
        if not is_valid:
            return False, f"网络接口验证失败: {error_msg}"

        # 验证HTTPS配置
        if self.proxy_type == "http" and hasattr(self, 'https_check'):
            if self.https_check.isChecked():
                if not self.cert_edit.text():
                    return False, "请选择证书文件"
                if not self.key_edit.text():
                    return False, "请选择私钥文件"

                if not os.path.exists(self.cert_edit.text()):
                    return False, f"证书文件不存在: {self.cert_edit.text()}"
                if not os.path.exists(self.key_edit.text()):
                    return False, f"私钥文件不存在: {self.key_edit.text()}"

        return True, "配置验证通过"

    def get_config(self) -> Dict[str, Any]:
        """获取配置，返回字典形式"""
        interface_config = self.interface_selector.get_config()
        config_dict = {
            'proxy_name': self.name_edit.text(),
            'iface_name': interface_config.iface_name,
            'ip': interface_config.ip,
            'port': interface_config.port,
            'auth_enabled': self.auth_check.isChecked(),
            'security_enabled': self.security_check.isChecked(),
        }

        if self.enable_protocol_check.isChecked():
            protocol = self.protocol_combo.currentText()
            config_dict['proxy_protocol'] = protocol
        else:
            config_dict['proxy_protocol'] = None

        if self.proxy_type == "http":
            config_dict['use_https'] = self.https_check.isChecked()
            if config_dict['use_https']:
                config_dict['cert_file'] = self.cert_edit.text()
                config_dict['key_file'] = self.key_edit.text()
            else:
                config_dict['cert_file'] = ''
                config_dict['key_file'] = ''

        return config_dict

    def accept(self):
        """重写accept，添加验证"""
        is_valid, error_msg = self.validate_config()
        if not is_valid:
            self.show_status(error_msg, "error")
            return

        super().accept()

    def show_status(self, message: str, msg_type: str = "info"):
        """显示状态消息"""
        colors = {
            "info": "#0066cc",
            "success": "#009900",
            "warning": "#ff9900",
            "error": "#cc0000"
        }

        color = colors.get(msg_type, "#666666")
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; padding: 5px;")


class ProxyListWidget(QWidget):
    """代理列表管理部件"""

    config_modified = Signal()

    def __init__(self, proxy_type="socks5", parent=None):
        super().__init__(parent)
        self.proxy_type = proxy_type
        self.proxy_configs = []  # 存储Socks5Proxy或HttpProxy对象
        self.current_index = -1
        self._modified = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 列表和操作按钮区域
        list_container = QWidget()
        list_container_layout = QHBoxLayout()
        list_container_layout.setSpacing(10)

        # 代理列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setMinimumWidth(250)
        self.list_widget.currentRowChanged.connect(self.on_item_selected)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.edit_proxy)
        list_container_layout.addWidget(self.list_widget)

        # 操作按钮
        btn_container = QWidget()
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        # 新建按钮
        self.add_btn = QPushButton("新建")
        self.add_btn.clicked.connect(self.add_proxy)
        self.add_btn.setMinimumHeight(35)
        self.add_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.add_btn)

        # 编辑按钮
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_proxy)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setMinimumHeight(35)
        self.edit_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.edit_btn)

        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_proxy)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setMinimumHeight(35)
        self.delete_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.delete_btn)

        # 上移按钮
        self.move_up_btn = QPushButton("↑ 上移")
        self.move_up_btn.clicked.connect(self.move_up)
        self.move_up_btn.setEnabled(False)
        self.move_up_btn.setMinimumHeight(35)
        self.move_up_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.move_up_btn.setToolTip("将选中的代理向上移动一位")
        btn_layout.addWidget(self.move_up_btn)

        # 下移按钮
        self.move_down_btn = QPushButton("↓ 下移")
        self.move_down_btn.clicked.connect(self.move_down)
        self.move_down_btn.setEnabled(False)
        self.move_down_btn.setMinimumHeight(35)
        self.move_down_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.move_down_btn.setToolTip("将选中的代理向下移动一位")
        btn_layout.addWidget(self.move_down_btn)

        btn_layout.addStretch()
        btn_container.setLayout(btn_layout)
        btn_container.setFixedWidth(140)

        list_container_layout.addWidget(btn_container)
        list_container.setLayout(list_container_layout)
        layout.addWidget(list_container)

        # 状态标签
        self.status_label = QLabel()
        self.status_label.setMinimumHeight(30)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                margin: 5px 0;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.status_label)

        # 占位提示
        self.placeholder_label = QLabel(
            f"点击'新建'创建{self.proxy_type.upper()}代理配置\n"
            f"或从左侧列表中选择一个配置进行编辑"
        )
        layout.addWidget(self.placeholder_label)

        self.setLayout(layout)

    def move_up(self):
        """上移选中的代理"""
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            item_current = self.list_widget.takeItem(current_row)
            item_above = self.list_widget.takeItem(current_row - 1)

            self.list_widget.insertItem(current_row - 1, item_current)
            self.list_widget.insertItem(current_row, item_above)

            config_current = self.proxy_configs.pop(current_row)
            config_above = self.proxy_configs.pop(current_row - 1)

            self.proxy_configs.insert(current_row - 1, config_current)
            self.proxy_configs.insert(current_row, config_above)

            self.list_widget.setCurrentRow(current_row - 1)
            self.update_move_buttons()

            self.show_status(f"代理已上移", "success")
            self.emit_data_changed()

    def move_down(self):
        """下移选中的代理"""
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            item_current = self.list_widget.takeItem(current_row)
            item_below = self.list_widget.takeItem(current_row)

            self.list_widget.insertItem(current_row, item_below)
            self.list_widget.insertItem(current_row + 1, item_current)

            config_current = self.proxy_configs.pop(current_row)
            config_below = self.proxy_configs.pop(current_row)

            self.proxy_configs.insert(current_row, config_below)
            self.proxy_configs.insert(current_row + 1, config_current)

            self.list_widget.setCurrentRow(current_row + 1)
            self.update_move_buttons()

            self.show_status(f"代理已下移", "success")
            self.emit_data_changed()

    def update_move_buttons(self):
        """更新上移/下移按钮状态"""
        current_row = self.list_widget.currentRow()
        count = self.list_widget.count()

        self.move_up_btn.setEnabled(current_row > 0)
        self.move_down_btn.setEnabled(0 <= current_row < count - 1)

    def add_proxy(self):
        """新增代理"""
        default_name = self.proxy_type.upper() + '-' + str(self.list_widget.count()+1)
        dialog = ProxyConfigDialog(proxy_type=self.proxy_type, default_name=default_name, parent=self)
        if dialog.exec() == QDialog.Accepted:
            config_dict = dialog.get_config()

            # 根据代理类型创建对应的dataclass对象
            if self.proxy_type == "socks5":
                config = Socks5Proxy.from_dict(config_dict)
            else:  # http
                config = HttpProxy.from_dict(config_dict)

            # 生成显示名称
            display_name = self.generate_display_name(config)

            # 添加到列表
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, config)
            self.list_widget.addItem(item)
            self.proxy_configs.append(config)

            self.list_widget.setCurrentRow(self.list_widget.count() - 1)
            self.on_item_selected(self.list_widget.count() - 1)
            self.show_status(f"成功添加{self.proxy_type.upper()}代理", "success")
            self.update_move_buttons()
            self.emit_data_changed()

    def edit_proxy(self):
        """编辑代理"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            config = self.proxy_configs[current_row]

            # 将dataclass对象转换为字典用于对话框
            config_dict = config.to_dict()

            dialog = ProxyConfigDialog(proxy_type=self.proxy_type, config=config_dict, parent=self)
            if dialog.exec() == QDialog.Accepted:
                new_config_dict = dialog.get_config()

                # 根据代理类型创建新的dataclass对象
                if self.proxy_type == "socks5":
                    new_config = Socks5Proxy.from_dict(new_config_dict)
                else:  # http
                    new_config = HttpProxy.from_dict(new_config_dict)

                # 更新配置
                self.proxy_configs[current_row] = new_config

                # 更新列表项显示
                display_name = self.generate_display_name(new_config)
                item = self.list_widget.item(current_row)
                item.setText(display_name)
                item.setData(Qt.UserRole, new_config)

                self.show_status(f"成功更新{self.proxy_type.upper()}代理", "success")
                self.emit_data_changed()

    def delete_proxy(self):
        """删除代理"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "确认删除",
                "确定要删除这个代理配置吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.list_widget.takeItem(current_row)
                self.proxy_configs.pop(current_row)
                self.show_status(f"已删除{self.proxy_type.upper()}代理", "info")

                if self.list_widget.count() > 0:
                    new_row = min(current_row, self.list_widget.count() - 1)
                    self.list_widget.setCurrentRow(new_row)
                    self.on_item_selected(new_row)
                    self.update_move_buttons()
                else:
                    self.show_placeholder()

                self.emit_data_changed()

    def on_item_clicked(self, item):
        """处理项点击"""
        row = self.list_widget.row(item)
        self.on_item_selected(row)

    def emit_data_changed(self):
        """触发数据改变信号"""
        self._modified = True
        self.config_modified.emit()

    def is_modified(self) -> bool:
        """检查是否已修改"""
        return self._modified

    def clear_modified(self):
        """清除修改标记"""
        self._modified = False

    def generate_display_name(self, config) -> str:
        """生成显示名称"""
        # 现在config是Socks5Proxy或HttpProxy对象
        proxy_name = config.proxy_name or '未设置'

        if config.ip:
            ip = config.ip
        else:
            try:
                ip = NetworkInterface(iface_name=config.iface_name).ip
            except Exception:
                ip = '未知'

        port = config.port or '未知'
        auth = '认证' if config.auth_enabled else '无认证'
        sec = '安全管理' if config.security_enabled else '无安全管理'

        # Proxy Protocol标记
        pp = f"PP:{config.proxy_protocol}" if config.proxy_protocol else '无PP'

        # HTTP/HTTPS特殊标记
        protocol_marker = ""
        if isinstance(config, HttpProxy):
            protocol_marker = "HTTPS" if config.use_https else "HTTP"
        else:
            protocol_marker = "SOCKS5"

        return f"[{protocol_marker}代理]: {proxy_name} - {ip}:{port}, {auth}, {sec}, {pp}"

    def on_item_selected(self, row):
        """处理项选择"""
        self.current_index = row

        if row >= 0:
            self.placeholder_label.hide()
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.update_move_buttons()

            config = self.proxy_configs[row]
            proxy_name = config.proxy_name or '未命名'
            iface_name = config.iface_name or ''
            ip = config.ip or ''
            iface = NetworkInterface(iface_name=iface_name, ip=ip)
            port = config.port or '未知'
            self.show_status(f"已选中: [{proxy_name}] {iface.iface_name} - {iface.ip}:{port}", "info")
        else:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            self.show_placeholder()

    def show_placeholder(self):
        """显示占位提示"""
        self.placeholder_label.show()
        self.status_label.clear()
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.move_up_btn.setEnabled(False)
        self.move_down_btn.setEnabled(False)

    def show_status(self, message: str, msg_type: str = "info"):
        """显示状态消息"""
        colors = {
            "info": "#0066cc",
            "success": "#009900",
            "warning": "#ff9900",
            "error": "#cc0000"
        }

        color = colors.get(msg_type, "#666666")
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; padding: 5px;")

    def get_configs(self) -> List:
        """获取所有配置对象"""
        return self.proxy_configs.copy()

    def set_configs(self, configs: List):
        """设置配置列表"""
        # 清空列表
        self.list_widget.clear()
        self.proxy_configs.clear()

        if not configs:
            self.show_placeholder()
            return

        # 如果传入的是字典列表，转换为dataclass对象
        if isinstance(configs[0], dict):
            if self.proxy_type == "socks5":
                configs = [Socks5Proxy.from_dict(c) for c in configs]
            else:  # http
                configs = [HttpProxy.from_dict(c) for c in configs]

        self.list_widget.blockSignals(True)

        try:
            for config in configs:
                self.proxy_configs.append(config)
                display_name = self.generate_display_name(config)
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, config)
                self.list_widget.addItem(item)

            if self.proxy_configs:
                self.list_widget.setCurrentRow(0)
                self.on_item_selected(0)
            else:
                self.show_placeholder()

            self._modified = False
        finally:
            self.list_widget.blockSignals(False)


class Socks5SettingsTab(QWidget):
    """SOCKS5设置标签页"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 页面说明标签
        self.description_label = QLabel(
            "SOCKS5代理设置：\n"
            "• 配置和管理多个SOCKS5代理服务器\n"
            "• 每个代理可以监听不同的网络接口\n"
            "• 支持用户认证、安全管理和Proxy Protocol"
        )
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                margin-bottom: 10px;
                font-size: 11px;
                color: #666;
            }
        """)
        layout.addWidget(self.description_label)

        # SOCKS5代理列表管理
        self.socks5_list = ProxyListWidget("socks5", self)
        self.socks5_list.config_modified.connect(self.on_config_modified)
        layout.addWidget(self.socks5_list)

        layout.addStretch()
        self.setLayout(layout)

    def get_config(self) -> List[Socks5Proxy]:
        """获取配置，返回Socks5Proxy对象列表"""
        configs = self.socks5_list.get_configs()

        # 确保返回的是Socks5Proxy对象列表
        result = []
        for config in configs:
            if isinstance(config, dict):
                result.append(Socks5Proxy.from_dict(config))
            elif isinstance(config, Socks5Proxy):
                result.append(config)

        return result

    def set_config(self, configs: List):
        """设置配置"""
        self.socks5_list.set_configs(configs)
        self._modified = False

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        configs = self.get_config()
        if not configs:
            return True, "无SOCKS5代理配置"

        for i, proxy in enumerate(configs):
            # 检查端口是否有效
            if proxy.port and (proxy.port < 1 or proxy.port > 65535):
                return False, f"第{i+1}个代理端口 {proxy.port} 无效"

            # 检查重复项
            for j, other_proxy in enumerate(configs[i+1:], start=i+1):
                if proxy.port == other_proxy.port:
                    # 检查IP是否相同
                    ip1 = proxy.ip if proxy.ip else self._get_ip_from_iface(proxy.iface_name)
                    ip2 = other_proxy.ip if other_proxy.ip else self._get_ip_from_iface(other_proxy.iface_name)

                    if ip1 and ip2 and ip1 == ip2:
                        return False, f"第{i+1}个和第{j+1}个代理配置重复（IP: {ip1}, 端口: {proxy.port}）"

        return True, "SOCKS5配置验证通过"

    def _get_ip_from_iface(self, iface_name: str) -> Optional[str]:
        """从接口名称获取IP地址"""
        if not iface_name:
            return None

        try:
            from utils.interface_utils import NetworkInterface
            iface = NetworkInterface(iface_name=iface_name)
            return iface.ip
        except Exception:
            return None

    def is_modified(self) -> bool:
        """检查配置是否已修改"""
        return self._modified or self.socks5_list.is_modified()

    def clear_modified(self):
        """清除修改标记"""
        self._modified = False
        self.socks5_list.clear_modified()

    def on_config_modified(self):
        """配置修改事件"""
        self._modified = True
        self.config_modified.emit()


class HttpSettingsTab(QWidget):
    """HTTP/HTTPS设置标签页"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 页面说明标签
        self.description_label = QLabel(
            "HTTP/HTTPS代理设置：\n"
            "• 配置和管理多个HTTP/HTTPS代理服务器\n"
            "• 支持HTTP和HTTPS协议\n"
            "• 支持用户认证、SSL/TLS加密和Proxy Protocol"
        )
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                margin-bottom: 10px;
                font-size: 11px;
                color: #666;
            }
        """)
        layout.addWidget(self.description_label)

        # HTTP/HTTPS代理列表管理
        self.http_list = ProxyListWidget("http", self)
        self.http_list.config_modified.connect(self.on_config_modified)
        layout.addWidget(self.http_list)

        layout.addStretch()
        self.setLayout(layout)

    def get_config(self) -> List[HttpProxy]:
        """获取配置，返回HttpProxy对象列表"""
        configs = self.http_list.get_configs()

        # 确保返回的是HttpProxy对象列表
        result = []
        for config in configs:
            if isinstance(config, dict):
                result.append(HttpProxy.from_dict(config))
            elif isinstance(config, HttpProxy):
                result.append(config)

        return result

    def set_config(self, configs: List):
        """设置配置"""
        self.http_list.set_configs(configs)
        self._modified = False

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        configs = self.get_config()
        if not configs:
            return True, "无HTTP/HTTPS代理配置"

        for i, proxy in enumerate(configs):
            # 检查端口是否有效
            if proxy.port and (proxy.port < 1 or proxy.port > 65535):
                return False, f"第{i+1}个代理端口 {proxy.port} 无效"

            # 检查重复项
            for j, other_proxy in enumerate(configs[i+1:], start=i+1):
                if proxy.port == other_proxy.port:
                    # 检查IP是否相同
                    ip1 = proxy.ip if proxy.ip else self._get_ip_from_iface(proxy.iface_name)
                    ip2 = other_proxy.ip if other_proxy.ip else self._get_ip_from_iface(other_proxy.iface_name)

                    if ip1 and ip2 and ip1 == ip2:
                        return False, f"第{i+1}个和第{j+1}个代理配置重复（IP: {ip1}, 端口: {proxy.port}）"

            # 检查HTTPS配置
            if proxy.use_https:
                if not proxy.cert_file or not proxy.key_file:
                    return False, f"第{i+1}个代理启用HTTPS但未配置证书文件"

                if not os.path.exists(proxy.cert_file):
                    return False, f"第{i+1}个代理证书文件不存在: {proxy.cert_file}"

                if not os.path.exists(proxy.key_file):
                    return False, f"第{i+1}个代理私钥文件不存在: {proxy.key_file}"

        return True, "HTTP/HTTPS配置验证通过"

    def _get_ip_from_iface(self, iface_name: str) -> Optional[str]:
        """从接口名称获取IP地址"""
        if not iface_name:
            return None

        try:
            from utils.interface_utils import NetworkInterface
            iface = NetworkInterface(iface_name=iface_name)
            return iface.ip
        except Exception:
            return None

    def is_modified(self) -> bool:
        """检查配置是否已修改"""
        return self._modified or self.http_list.is_modified()

    def clear_modified(self):
        """清除修改标记"""
        self._modified = False
        self.http_list.clear_modified()

    def on_config_modified(self):
        """配置修改事件"""
        self._modified = True
        self.config_modified.emit()
