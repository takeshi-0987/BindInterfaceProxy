# -*- coding: utf-8 -*-
"""
Module: security_settings_tab.py
Author: Takeshi
Date: 2025-12-07

Description:
    安全管理设置标签页，支持HTTP和SOCKS5差异化配置
"""


import logging
from typing import  Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QCheckBox, QLineEdit, QComboBox, QSpinBox,
    QGroupBox, QPushButton, QScrollArea,
    QFrame, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal

from defaults.security_default import (
    CoreSecurityConfig,
    AuthFailureDetectionConfig,
    RapidConnectionDetectionConfig,
    AdvancedSecurityConfig,
    SecurityConfig
)

logger = logging.getLogger(__name__)


class SecuritySettingsTab(QWidget):
    """安全管理设置标签页"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self.config = SecurityConfig()  # 默认配置对象
        self._is_loading_config = False
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)

        # 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 主容器
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === 说明部分 ===
        description = QLabel(
            "安全管理器设置：\n"
            "• 配置IP黑白名单、临时封禁等安全策略\n"
            "• 支持HTTP和SOCKS5协议的差异化配置\n"
            "• 提供扫描防护等高级安全功能"
        )
        description.setWordWrap(True)
        description.setStyleSheet("""
            QLabel {
                padding: 10px;
                margin-bottom: 10px;
                font-size: 11px;
                color: #666;
                background-color: #f9f9f9;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(description)

        # 1. 核心设置组
        core_group = self.create_core_settings_group()
        main_layout.addWidget(core_group)

        # 2. 认证失败检测组
        auth_failure_group = self.create_auth_failure_group()
        main_layout.addWidget(auth_failure_group)

        # 3. 快速连接检测组
        rapid_connection_group = self.create_rapid_connection_group()
        main_layout.addWidget(rapid_connection_group)

        # 4. 高级设置组
        advanced_group = self.create_advanced_settings_group()
        main_layout.addWidget(advanced_group)

        # 添加弹性空间
        main_layout.addStretch()

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def create_core_settings_group(self) -> QGroupBox:
        """创建核心设置组"""
        group = QGroupBox("核心设置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QGridLayout()
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(10)
        layout.setContentsMargins(15, 20, 15, 15)

        # 安全模式
        row = 0
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(5)
        mode_label = QLabel("安全模式:")
        mode_label.setMinimumWidth(80)
        mode_layout.addWidget(mode_label)
        self.mode_combo = QComboBox()
        # 中文选项
        self.mode_combo.addItems(["黑名单模式", "白名单模式", "混合模式"])
        # 设置当前值
        mode_mapping = {
            "blacklist": "黑名单模式",
            "whitelist": "白名单模式",
            "mixed": "混合模式"
        }
        mode_text = mode_mapping.get(self.config.core.mode, "黑名单模式")
        self.mode_combo.setCurrentText(mode_text)
        self.mode_combo.currentTextChanged.connect(self.on_config_changed)
        self.mode_combo.setToolTip("黑名单模式: 仅阻止黑名单中的IP\n白名单模式: 仅允许白名单中的IP\n混合模式: 混合模式")
        self.mode_combo.setFixedWidth(100)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout, row, 0, 1, 2)

        # 清理间隔
        row += 1
        cleanup_layout = QHBoxLayout()
        cleanup_layout.setSpacing(5)
        cleanup_label = QLabel("清理间隔:")
        cleanup_label.setMinimumWidth(80)
        cleanup_layout.addWidget(cleanup_label)
        self.cleanup_spin = QSpinBox()
        self.cleanup_spin.setRange(60, 3600)
        self.cleanup_spin.setValue(self.config.core.cleanup_interval)
        self.cleanup_spin.setSingleStep(60)
        self.cleanup_spin.setSuffix(" 秒")
        self.cleanup_spin.valueChanged.connect(self.on_config_changed)
        self.cleanup_spin.setToolTip("清理过期封禁记录的时间间隔")
        self.cleanup_spin.setFixedWidth(100)
        cleanup_layout.addWidget(self.cleanup_spin)
        cleanup_layout.addStretch()
        layout.addLayout(cleanup_layout, row, 0, 1, 2)

        # 保存历史记录
        row += 1
        self.keep_history_check = QCheckBox("保存临时封禁历史记录")
        self.keep_history_check.setChecked(self.config.core.keep_ban_history)
        self.keep_history_check.stateChanged.connect(self.on_config_changed)
        self.keep_history_check.setToolTip("是否保存临时封禁和解封的历史记录")
        layout.addWidget(self.keep_history_check, row, 0, 1, 2)

        # 最大历史记录数
        row += 1
        max_history_layout = QHBoxLayout()
        max_history_layout.setSpacing(5)
        max_history_label = QLabel("最大历史记录数:")
        max_history_label.setMinimumWidth(80)
        max_history_layout.addWidget(max_history_label)
        self.max_history_spin = QSpinBox()
        self.max_history_spin.setRange(100, 10000)
        self.max_history_spin.setValue(self.config.core.max_history_size)
        self.max_history_spin.valueChanged.connect(self.on_config_changed)
        self.max_history_spin.setToolTip("保存的历史记录最大数量")
        self.max_history_spin.setFixedWidth(100)
        max_history_layout.addWidget(self.max_history_spin)
        max_history_layout.addStretch()
        layout.addLayout(max_history_layout, row, 0, 1, 2)

        # 文件路径区域
        row += 1
        file_path_label = QLabel("文件路径配置:")
        layout.addWidget(file_path_label, row, 0, 1, 2)

        row += 1
        # 黑名单文件路径
        blacklist_layout = QHBoxLayout()
        blacklist_layout.setSpacing(5)
        blacklist_label = QLabel("黑名单文件:")
        blacklist_label.setMinimumWidth(80)
        blacklist_layout.addWidget(blacklist_label)
        self.blacklist_edit = QLineEdit(self.config.core.blacklist_file)
        self.blacklist_edit.textChanged.connect(self.on_config_changed)
        self.blacklist_edit.setFixedWidth(300)
        blacklist_layout.addWidget(self.blacklist_edit)

        # 文件路径管理按钮
        self.file_btn = QPushButton("文件路径管理")
        self.file_btn.clicked.connect(self.manage_file_paths)
        self.file_btn.setFixedWidth(100)
        blacklist_layout.addWidget(self.file_btn)
        blacklist_layout.addStretch()

        layout.addLayout(blacklist_layout, row, 0, 1, 2)

        row += 1
        # 白名单文件
        whitelist_layout = QHBoxLayout()
        whitelist_layout.setSpacing(5)
        whitelist_label = QLabel("白名单文件:")
        whitelist_label.setMinimumWidth(80)
        whitelist_layout.addWidget(whitelist_label)
        self.whitelist_edit = QLineEdit(self.config.core.whitelist_file)
        self.whitelist_edit.textChanged.connect(self.on_config_changed)
        self.whitelist_edit.setFixedWidth(300)
        whitelist_layout.addWidget(self.whitelist_edit)
        whitelist_layout.addStretch()
        layout.addLayout(whitelist_layout, row, 0, 1, 2)

        row += 1
        # 临时封禁文件
        ban_history_layout = QHBoxLayout()
        ban_history_layout.setSpacing(5)
        ban_history_label = QLabel("封禁历史文件:")
        ban_history_label.setMinimumWidth(80)
        ban_history_layout.addWidget(ban_history_label)
        self.ban_history_edit = QLineEdit(self.config.core.ban_history_file)
        self.ban_history_edit.textChanged.connect(self.on_config_changed)
        self.ban_history_edit.setFixedWidth(300)
        ban_history_layout.addWidget(self.ban_history_edit)
        ban_history_layout.addStretch()
        layout.addLayout(ban_history_layout, row, 0, 1, 2)

        group.setLayout(layout)
        return group

    def create_auth_failure_group(self) -> QGroupBox:
        """创建认证失败检测设置组"""
        group = QGroupBox("认证失败检测")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 20, 15, 15)

        # 启用认证失败检测
        self.enable_auth_failure_check = QCheckBox("启用认证失败检测")
        self.enable_auth_failure_check.setChecked(self.config.auth_failure_detection.enabled)
        self.enable_auth_failure_check.stateChanged.connect(self.on_auth_failure_enabled_changed)
        layout.addWidget(self.enable_auth_failure_check)

        # 协议参数网格
        auth_grid = QGridLayout()
        auth_grid.setHorizontalSpacing(8)
        auth_grid.setVerticalSpacing(10)
        auth_grid.setAlignment(Qt.AlignLeft)

        # 标签行
        auth_grid.addWidget(QLabel("<b>HTTP代理</b>"), 0, 1, 1, 2, Qt.AlignLeft)
        auth_grid.addWidget(QLabel("<b>SOCKS5代理</b>"), 0, 3, 1, 2, Qt.AlignLeft)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        auth_grid.addWidget(separator, 1, 2, 4, 1)

        # HTTP最大认证失败次数
        row = 1
        http_auth_layout = QHBoxLayout()
        http_auth_layout.setSpacing(5)
        http_auth_label = QLabel("最大认证失败:")
        http_auth_label.setMinimumWidth(100)
        http_auth_layout.addWidget(http_auth_label)
        self.http_max_failures_spin = QSpinBox()
        self.http_max_failures_spin.setRange(1, 50)
        self.http_max_failures_spin.setValue(self.config.auth_failure_detection.http_max_failures)
        self.http_max_failures_spin.valueChanged.connect(self.on_config_changed)
        self.http_max_failures_spin.setToolTip("HTTP代理最大允许的认证失败次数")
        self.http_max_failures_spin.setFixedWidth(100)
        http_auth_layout.addWidget(self.http_max_failures_spin)
        auth_grid.addLayout(http_auth_layout, row, 1)

        # SOCKS5最大认证失败次数
        socks_auth_layout = QHBoxLayout()
        socks_auth_layout.setSpacing(5)
        socks_auth_label = QLabel("最大认证失败:")
        socks_auth_label.setMinimumWidth(100)
        socks_auth_layout.addWidget(socks_auth_label)
        self.socks_max_failures_spin = QSpinBox()
        self.socks_max_failures_spin.setRange(1, 50)
        self.socks_max_failures_spin.setValue(self.config.auth_failure_detection.socks_max_failures)
        self.socks_max_failures_spin.valueChanged.connect(self.on_config_changed)
        self.socks_max_failures_spin.setToolTip("SOCKS5代理最大允许的认证失败次数")
        self.socks_max_failures_spin.setFixedWidth(100)
        socks_auth_layout.addWidget(self.socks_max_failures_spin)
        auth_grid.addLayout(socks_auth_layout, row, 3)

        # HTTP封禁时长
        row += 1
        http_ban_layout = QHBoxLayout()
        http_ban_layout.setSpacing(5)
        http_ban_label = QLabel("封禁时长:")
        http_ban_label.setMinimumWidth(100)
        http_ban_layout.addWidget(http_ban_label)
        self.http_ban_duration_spin = QSpinBox()
        self.http_ban_duration_spin.setRange(60, 86400)
        self.http_ban_duration_spin.setValue(self.config.auth_failure_detection.http_ban_duration)
        self.http_ban_duration_spin.setSuffix(" 秒")
        self.http_ban_duration_spin.valueChanged.connect(self.on_config_changed)
        self.http_ban_duration_spin.setToolTip("HTTP代理触发封禁的时长")
        self.http_ban_duration_spin.setFixedWidth(100)
        http_ban_layout.addWidget(self.http_ban_duration_spin)
        auth_grid.addLayout(http_ban_layout, row, 1)

        # SOCKS5封禁时长
        socks_ban_layout = QHBoxLayout()
        socks_ban_layout.setSpacing(5)
        socks_ban_label = QLabel("封禁时长:")
        socks_ban_label.setMinimumWidth(100)
        socks_ban_layout.addWidget(socks_ban_label)
        self.socks_ban_duration_spin = QSpinBox()
        self.socks_ban_duration_spin.setRange(60, 86400)
        self.socks_ban_duration_spin.setValue(self.config.auth_failure_detection.socks_ban_duration)
        self.socks_ban_duration_spin.setSuffix(" 秒")
        self.socks_ban_duration_spin.valueChanged.connect(self.on_config_changed)
        self.socks_ban_duration_spin.setToolTip("SOCKS5代理触发封禁的时长")
        self.socks_ban_duration_spin.setFixedWidth(100)
        socks_ban_layout.addWidget(self.socks_ban_duration_spin)
        auth_grid.addLayout(socks_ban_layout, row, 3)

        layout.addLayout(auth_grid)

        # 说明标签
        note = QLabel("提示: 当同一IP在短时间内认证失败次数达到阈值时，会自动临时封禁")
        note.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        layout.addWidget(note)

        group.setLayout(layout)
        return group

    def create_rapid_connection_group(self) -> QGroupBox:
        """创建快速连接检测设置组"""
        group = QGroupBox("快速连接检测")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 20, 15, 15)

        # 启用快速连接检测
        self.enable_rapid_connection_check = QCheckBox("启用快速连接检测")
        self.enable_rapid_connection_check.setChecked(self.config.advanced.rapid_connection_detection.enabled)
        self.enable_rapid_connection_check.stateChanged.connect(self.on_rapid_connection_enabled_changed)
        layout.addWidget(self.enable_rapid_connection_check)

        # 协议参数网格
        rapid_grid = QGridLayout()
        rapid_grid.setHorizontalSpacing(8)
        rapid_grid.setVerticalSpacing(10)
        rapid_grid.setAlignment(Qt.AlignLeft)

        # 标签行
        rapid_grid.addWidget(QLabel("<b>HTTP代理</b>"), 0, 1, 1, 2, Qt.AlignLeft)
        rapid_grid.addWidget(QLabel("<b>SOCKS5代理</b>"), 0, 3, 1, 2, Qt.AlignLeft)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        rapid_grid.addWidget(separator, 1, 2, 4, 1)

        # HTTP快速连接阈值
        row = 1
        http_threshold_layout = QHBoxLayout()
        http_threshold_layout.setSpacing(5)
        http_threshold_label = QLabel("快速连接阈值:")
        http_threshold_label.setMinimumWidth(100)
        http_threshold_layout.addWidget(http_threshold_label)
        self.http_threshold_spin = QSpinBox()
        self.http_threshold_spin.setRange(10, 1000)
        self.http_threshold_spin.setValue(self.config.advanced.rapid_connection_detection.http_threshold)
        self.http_threshold_spin.valueChanged.connect(self.on_config_changed)
        self.http_threshold_spin.setToolTip("HTTP代理在时间窗口内允许的最大连接数")
        self.http_threshold_spin.setFixedWidth(100)
        http_threshold_layout.addWidget(self.http_threshold_spin)
        rapid_grid.addLayout(http_threshold_layout, row, 1)

        # SOCKS5快速连接阈值
        socks_threshold_layout = QHBoxLayout()
        socks_threshold_layout.setSpacing(5)
        socks_threshold_label = QLabel("快速连接阈值:")
        socks_threshold_label.setMinimumWidth(100)
        socks_threshold_layout.addWidget(socks_threshold_label)
        self.socks_threshold_spin = QSpinBox()
        self.socks_threshold_spin.setRange(5, 500)
        self.socks_threshold_spin.setValue(self.config.advanced.rapid_connection_detection.socks_threshold)
        self.socks_threshold_spin.valueChanged.connect(self.on_config_changed)
        self.socks_threshold_spin.setToolTip("SOCKS5代理在时间窗口内允许的最大连接数")
        self.socks_threshold_spin.setFixedWidth(100)
        socks_threshold_layout.addWidget(self.socks_threshold_spin)
        rapid_grid.addLayout(socks_threshold_layout, row, 3)

        # HTTP时间窗口
        row += 1
        http_window_layout = QHBoxLayout()
        http_window_layout.setSpacing(5)
        http_window_label = QLabel("时间窗口:")
        http_window_label.setMinimumWidth(100)
        http_window_layout.addWidget(http_window_label)
        self.http_window_spin = QSpinBox()
        self.http_window_spin.setRange(10, 300)
        self.http_window_spin.setValue(self.config.advanced.rapid_connection_detection.http_window)
        self.http_window_spin.setSuffix(" 秒")
        self.http_window_spin.valueChanged.connect(self.on_config_changed)
        self.http_window_spin.setToolTip("HTTP代理统计连接数的时间窗口")
        self.http_window_spin.setFixedWidth(100)
        http_window_layout.addWidget(self.http_window_spin)
        rapid_grid.addLayout(http_window_layout, row, 1)

        # SOCKS5时间窗口
        socks_window_layout = QHBoxLayout()
        socks_window_layout.setSpacing(5)
        socks_window_label = QLabel("时间窗口:")
        socks_window_label.setMinimumWidth(100)
        socks_window_layout.addWidget(socks_window_label)
        self.socks_window_spin = QSpinBox()
        self.socks_window_spin.setRange(10, 300)
        self.socks_window_spin.setValue(self.config.advanced.rapid_connection_detection.socks_window)
        self.socks_window_spin.setSuffix(" 秒")
        self.socks_window_spin.valueChanged.connect(self.on_config_changed)
        self.socks_window_spin.setToolTip("SOCKS5代理统计连接数的时间窗口")
        self.socks_window_spin.setFixedWidth(100)
        socks_window_layout.addWidget(self.socks_window_spin)
        rapid_grid.addLayout(socks_window_layout, row, 3)

        layout.addLayout(rapid_grid)

        # 说明标签
        note = QLabel("提示: 检测短时间内的大量连接（DDoS/暴力破解），超过阈值会触发扫描防护")
        note.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        layout.addWidget(note)

        group.setLayout(layout)
        return group

    def create_advanced_settings_group(self) -> QGroupBox:
        """创建高级设置组"""
        group = QGroupBox("高级安全设置 (扫描防护，测试功能，谨慎开启)")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 20, 15, 15)

        # 启用扫描防护
        self.enable_scan_check = QCheckBox("启用扫描防护")
        self.enable_scan_check.setChecked(self.config.advanced.enable_scan_protection)
        self.enable_scan_check.stateChanged.connect(self.on_scan_enabled_changed)
        layout.addWidget(self.enable_scan_check)

        # 扫描防护参数网格
        scan_grid = QGridLayout()
        scan_grid.setHorizontalSpacing(8)
        scan_grid.setVerticalSpacing(10)

        row = 0
        # 最大扫描尝试
        max_scan_layout = QHBoxLayout()
        max_scan_layout.setSpacing(2)
        max_scan_label = QLabel("最大扫描尝试:")
        max_scan_label.setMinimumWidth(80)
        max_scan_layout.addWidget(max_scan_label)
        self.max_scan_attempts_spin = QSpinBox()
        self.max_scan_attempts_spin.setRange(1, 50)
        self.max_scan_attempts_spin.setValue(self.config.advanced.max_scan_attempts)
        self.max_scan_attempts_spin.valueChanged.connect(self.on_config_changed)
        self.max_scan_attempts_spin.setEnabled(self.config.advanced.enable_scan_protection)
        self.max_scan_attempts_spin.setFixedWidth(100)
        max_scan_layout.addWidget(self.max_scan_attempts_spin)
        max_scan_layout.addStretch()
        scan_grid.addLayout(max_scan_layout, row, 0)

        # 扫描封禁时长
        scan_ban_layout = QHBoxLayout()
        scan_ban_layout.setSpacing(2)
        scan_ban_label = QLabel("扫描封禁时长:")
        scan_ban_label.setMinimumWidth(80)
        scan_ban_layout.addWidget(scan_ban_label)
        self.scan_ban_duration_spin = QSpinBox()
        self.scan_ban_duration_spin.setRange(60, 86400)
        self.scan_ban_duration_spin.setValue(self.config.advanced.scan_ban_duration)
        self.scan_ban_duration_spin.setSuffix(" 秒")
        self.scan_ban_duration_spin.valueChanged.connect(self.on_config_changed)
        self.scan_ban_duration_spin.setEnabled(self.config.advanced.enable_scan_protection)
        self.scan_ban_duration_spin.setFixedWidth(100)
        scan_ban_layout.addWidget(self.scan_ban_duration_spin)
        scan_ban_layout.addStretch()
        scan_grid.addLayout(scan_ban_layout, row, 1)

        row += 1
        # 扫描清理间隔
        scan_cleanup_layout = QHBoxLayout()
        scan_cleanup_layout.setSpacing(2)
        scan_cleanup_label = QLabel("扫描清理间隔:")
        scan_cleanup_label.setMinimumWidth(80)
        scan_cleanup_layout.addWidget(scan_cleanup_label)
        self.scan_cleanup_spin = QSpinBox()
        self.scan_cleanup_spin.setRange(300, 7200)
        self.scan_cleanup_spin.setValue(self.config.advanced.scan_cleanup_interval)
        self.scan_cleanup_spin.setSuffix(" 秒")
        self.scan_cleanup_spin.valueChanged.connect(self.on_config_changed)
        self.scan_cleanup_spin.setEnabled(self.config.advanced.enable_scan_protection)
        self.scan_cleanup_spin.setFixedWidth(100)
        scan_cleanup_layout.addWidget(self.scan_cleanup_spin)
        scan_cleanup_layout.addStretch()
        scan_grid.addLayout(scan_cleanup_layout, row, 0)

        layout.addLayout(scan_grid)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # 扫描检测规则组
        rules_group = QGroupBox("扫描检测规则")
        rules_group.setFlat(True)
        rules_layout = QGridLayout()
        rules_layout.setHorizontalSpacing(10)
        rules_layout.setVerticalSpacing(8)

        # SOCKS5检测规则
        rules_layout.addWidget(QLabel("<b>SOCKS5检测规则</b>"), 0, 0, 1, 2)

        self.invalid_version_check = QCheckBox("无效SOCKS版本检测")
        self.invalid_version_check.setChecked(self.config.advanced.enable_invalid_version_detection)
        self.invalid_version_check.stateChanged.connect(self.on_config_changed)
        self.invalid_version_check.setEnabled(self.config.advanced.enable_scan_protection)
        rules_layout.addWidget(self.invalid_version_check, 1, 0)

        self.invalid_method_check = QCheckBox("无效认证方法检测")
        self.invalid_method_check.setChecked(self.config.advanced.enable_invalid_method_detection)
        self.invalid_method_check.stateChanged.connect(self.on_config_changed)
        self.invalid_method_check.setEnabled(self.config.advanced.enable_scan_protection)
        rules_layout.addWidget(self.invalid_method_check, 1, 1)

        # HTTP检测规则
        rules_layout.addWidget(QLabel("<b>HTTP检测规则</b>"), 2, 0, 1, 2)

        self.invalid_http_method_check = QCheckBox("无效HTTP方法检测")
        self.invalid_http_method_check.setChecked(self.config.advanced.enable_invalid_http_method_detection)
        self.invalid_http_method_check.stateChanged.connect(self.on_config_changed)
        self.invalid_http_method_check.setEnabled(self.config.advanced.enable_scan_protection)
        rules_layout.addWidget(self.invalid_http_method_check, 3, 0)

        self.malformed_connect_check = QCheckBox("畸形CONNECT请求检测")
        self.malformed_connect_check.setChecked(self.config.advanced.enable_malformed_connect_detection)
        self.malformed_connect_check.stateChanged.connect(self.on_config_changed)
        self.malformed_connect_check.setEnabled(self.config.advanced.enable_scan_protection)
        rules_layout.addWidget(self.malformed_connect_check, 3, 1)

        self.invalid_port_check = QCheckBox("无效端口号检测")
        self.invalid_port_check.setChecked(self.config.advanced.enable_invalid_port_detection)
        self.invalid_port_check.stateChanged.connect(self.on_config_changed)
        self.invalid_port_check.setEnabled(self.config.advanced.enable_scan_protection)
        rules_layout.addWidget(self.invalid_port_check, 4, 0)

        self.suspicious_headers_check = QCheckBox("可疑HTTP头检测")
        self.suspicious_headers_check.setChecked(self.config.advanced.enable_suspicious_headers_detection)
        self.suspicious_headers_check.stateChanged.connect(self.on_config_changed)
        self.suspicious_headers_check.setEnabled(self.config.advanced.enable_scan_protection)
        rules_layout.addWidget(self.suspicious_headers_check, 4, 1)

        # 通用检测规则
        rules_layout.addWidget(QLabel("<b>通用检测规则</b>"), 5, 0, 1, 2)

        self.malformed_request_check = QCheckBox("畸形请求检测")
        self.malformed_request_check.setChecked(self.config.advanced.enable_malformed_request_detection)
        self.malformed_request_check.stateChanged.connect(self.on_config_changed)
        self.malformed_request_check.setEnabled(self.config.advanced.enable_scan_protection)
        rules_layout.addWidget(self.malformed_request_check, 6, 0)

        rules_group.setLayout(rules_layout)
        layout.addWidget(rules_group)

        # 全选/全不选按钮
        button_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all_rules)
        self.select_all_btn.setEnabled(self.config.advanced.enable_scan_protection)
        self.select_all_btn.setFixedWidth(80)
        button_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("全不选")
        self.deselect_all_btn.clicked.connect(self.deselect_all_rules)
        self.deselect_all_btn.setEnabled(self.config.advanced.enable_scan_protection)
        self.deselect_all_btn.setFixedWidth(80)
        button_layout.addWidget(self.deselect_all_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 说明标签
        note = QLabel("注意: 扫描防护功能默认关闭，启用后可能会增加服务器负载")
        note.setStyleSheet("color: #cc0000; font-size: 11px;")
        layout.addWidget(note)

        group.setLayout(layout)
        return group

    def on_auth_failure_enabled_changed(self, state):
        """认证失败检测启用状态改变"""
        enabled = bool(state)

        # 启用/禁用相关控件
        self.http_max_failures_spin.setEnabled(enabled)
        self.socks_max_failures_spin.setEnabled(enabled)
        self.http_ban_duration_spin.setEnabled(enabled)
        self.socks_ban_duration_spin.setEnabled(enabled)

        self.on_config_changed()

    def on_rapid_connection_enabled_changed(self, state):
        """快速连接检测启用状态改变"""
        enabled = bool(state)

        # 启用/禁用相关控件
        self.http_threshold_spin.setEnabled(enabled)
        self.socks_threshold_spin.setEnabled(enabled)
        self.http_window_spin.setEnabled(enabled)
        self.socks_window_spin.setEnabled(enabled)

        self.on_config_changed()

    def on_scan_enabled_changed(self, state):
        """扫描防护启用状态改变"""
        enabled = bool(state)

        # 启用/禁用相关控件
        self.max_scan_attempts_spin.setEnabled(enabled)
        self.scan_ban_duration_spin.setEnabled(enabled)
        self.scan_cleanup_spin.setEnabled(enabled)
        self.select_all_btn.setEnabled(enabled)
        self.deselect_all_btn.setEnabled(enabled)

        # 启用/禁用检测规则
        rule_checks = [
            self.invalid_version_check,
            self.invalid_method_check,
            self.invalid_http_method_check,
            self.malformed_connect_check,
            self.invalid_port_check,
            self.suspicious_headers_check,
            self.malformed_request_check,
        ]

        for check in rule_checks:
            check.setEnabled(enabled)

        self.on_config_changed()

    def select_all_rules(self):
        """全选所有检测规则"""
        rule_checks = [
            self.invalid_version_check,
            self.invalid_method_check,
            self.invalid_http_method_check,
            self.malformed_connect_check,
            self.invalid_port_check,
            self.suspicious_headers_check,
            self.malformed_request_check,
        ]

        for check in rule_checks:
            check.setChecked(True)

    def deselect_all_rules(self):
        """全不选所有检测规则"""
        rule_checks = [
            self.invalid_version_check,
            self.invalid_method_check,
            self.invalid_http_method_check,
            self.malformed_connect_check,
            self.invalid_port_check,
            self.suspicious_headers_check,
            self.malformed_request_check,
        ]

        for check in rule_checks:
            check.setChecked(False)

    def on_config_changed(self):
        """配置改变事件"""
        self._modified = True
        self.config_modified.emit()

    def get_config(self) -> SecurityConfig:
        """获取配置对象 - 返回SecurityConfig对象"""
        try:
            # 将中文模式转换为英文模式
            mode_mapping = {
                "黑名单模式": "blacklist",
                "白名单模式": "whitelist",
                "混合模式": "mixed"
            }
            current_mode = self.mode_combo.currentText()
            mode = mode_mapping.get(current_mode, "blacklist")

            # 创建SecurityConfig对象
            security_config = SecurityConfig(
                core=CoreSecurityConfig(
                    mode=mode,
                    cleanup_interval=self.cleanup_spin.value(),
                    keep_ban_history=self.keep_history_check.isChecked(),
                    max_history_size=self.max_history_spin.value(),
                    blacklist_file=self.blacklist_edit.text(),
                    whitelist_file=self.whitelist_edit.text(),
                    ban_history_file=self.ban_history_edit.text()
                ),
                auth_failure_detection=AuthFailureDetectionConfig(
                    enabled=self.enable_auth_failure_check.isChecked(),
                    http_max_failures=self.http_max_failures_spin.value(),
                    http_ban_duration=self.http_ban_duration_spin.value(),
                    socks_max_failures=self.socks_max_failures_spin.value(),
                    socks_ban_duration=self.socks_ban_duration_spin.value()
                ),
                advanced=AdvancedSecurityConfig(
                    enable_scan_protection=self.enable_scan_check.isChecked(),
                    max_scan_attempts=self.max_scan_attempts_spin.value(),
                    scan_ban_duration=self.scan_ban_duration_spin.value(),
                    scan_cleanup_interval=self.scan_cleanup_spin.value(),
                    enable_invalid_version_detection=self.invalid_version_check.isChecked(),
                    enable_invalid_method_detection=self.invalid_method_check.isChecked(),
                    enable_invalid_http_method_detection=self.invalid_http_method_check.isChecked(),
                    enable_malformed_connect_detection=self.malformed_connect_check.isChecked(),
                    enable_invalid_port_detection=self.invalid_port_check.isChecked(),
                    enable_suspicious_headers_detection=self.suspicious_headers_check.isChecked(),
                    enable_malformed_request_detection=self.malformed_request_check.isChecked(),
                    rapid_connection_detection=RapidConnectionDetectionConfig(
                        enabled=self.enable_rapid_connection_check.isChecked(),
                        http_threshold=self.http_threshold_spin.value(),
                        http_window=self.http_window_spin.value(),
                        socks_threshold=self.socks_threshold_spin.value(),
                        socks_window=self.socks_window_spin.value()
                    )
                )
            )

            return security_config

        except Exception as e:
            logger.error(f"获取安全管理配置失败: {e}", exc_info=True)
            # 返回默认配置
            return SecurityConfig()

    def set_config(self, config: SecurityConfig):
        """设置配置 - 接受SecurityConfig对象"""
        try:
            # 标记加载中状态
            self._is_loading_config = True

            # 保存配置对象
            self.config = config

            # 阻塞信号避免触发修改事件
            self.blockSignals(True)

            try:
                # 核心配置 - 将英文模式转换为中文模式
                mode_mapping = {
                    "blacklist": "黑名单模式",
                    "whitelist": "白名单模式",
                    "mixed": "混合模式"
                }
                mode_text = mode_mapping.get(config.core.mode, "黑名单模式")
                self.mode_combo.setCurrentText(mode_text)

                self.cleanup_spin.setValue(config.core.cleanup_interval)
                self.keep_history_check.setChecked(config.core.keep_ban_history)
                self.max_history_spin.setValue(config.core.max_history_size)
                self.blacklist_edit.setText(config.core.blacklist_file)
                self.whitelist_edit.setText(config.core.whitelist_file)
                self.ban_history_edit.setText(config.core.ban_history_file)

                # 认证失败检测配置
                self.enable_auth_failure_check.setChecked(config.auth_failure_detection.enabled)
                self.http_max_failures_spin.setValue(config.auth_failure_detection.http_max_failures)
                self.http_ban_duration_spin.setValue(config.auth_failure_detection.http_ban_duration)
                self.socks_max_failures_spin.setValue(config.auth_failure_detection.socks_max_failures)
                self.socks_ban_duration_spin.setValue(config.auth_failure_detection.socks_ban_duration)

                # 更新认证失败检测相关控件的启用状态
                self.on_auth_failure_enabled_changed(config.auth_failure_detection.enabled)

                # 高级配置 - 扫描防护
                self.enable_scan_check.setChecked(config.advanced.enable_scan_protection)
                self.max_scan_attempts_spin.setValue(config.advanced.max_scan_attempts)
                self.scan_ban_duration_spin.setValue(config.advanced.scan_ban_duration)
                self.scan_cleanup_spin.setValue(config.advanced.scan_cleanup_interval)

                self.invalid_version_check.setChecked(config.advanced.enable_invalid_version_detection)
                self.invalid_method_check.setChecked(config.advanced.enable_invalid_method_detection)
                self.invalid_http_method_check.setChecked(config.advanced.enable_invalid_http_method_detection)
                self.malformed_connect_check.setChecked(config.advanced.enable_malformed_connect_detection)
                self.invalid_port_check.setChecked(config.advanced.enable_invalid_port_detection)
                self.suspicious_headers_check.setChecked(config.advanced.enable_suspicious_headers_detection)
                self.malformed_request_check.setChecked(config.advanced.enable_malformed_request_detection)

                # 更新扫描防护相关控件的启用状态
                self.on_scan_enabled_changed(config.advanced.enable_scan_protection)

                # 快速连接检测配置
                self.enable_rapid_connection_check.setChecked(config.advanced.rapid_connection_detection.enabled)
                self.http_threshold_spin.setValue(config.advanced.rapid_connection_detection.http_threshold)
                self.http_window_spin.setValue(config.advanced.rapid_connection_detection.http_window)
                self.socks_threshold_spin.setValue(config.advanced.rapid_connection_detection.socks_threshold)
                self.socks_window_spin.setValue(config.advanced.rapid_connection_detection.socks_window)

                # 更新快速连接检测相关控件的启用状态
                self.on_rapid_connection_enabled_changed(config.advanced.rapid_connection_detection.enabled)

            finally:
                self.blockSignals(False)

            # 重置修改标记
            self._modified = False

        except Exception as e:
            logger.error(f"设置安全管理配置失败: {e}")
            # 出错时使用默认配置
            try:
                default_config = SecurityConfig()
                self.blockSignals(True)
                try:
                    self.mode_combo.setCurrentText('黑名单模式')
                    self.cleanup_spin.setValue(default_config.core.cleanup_interval)
                    self.keep_history_check.setChecked(default_config.core.keep_ban_history)
                    self.max_history_spin.setValue(default_config.core.max_history_size)
                    self.blacklist_edit.setText(default_config.core.blacklist_file)
                    self.whitelist_edit.setText(default_config.core.whitelist_file)
                    self.ban_history_edit.setText(default_config.core.ban_history_file)

                    # 其他控件使用默认值
                    self.enable_auth_failure_check.setChecked(default_config.auth_failure_detection.enabled)
                    self.http_max_failures_spin.setValue(default_config.auth_failure_detection.http_max_failures)
                    self.http_ban_duration_spin.setValue(default_config.auth_failure_detection.http_ban_duration)
                    self.socks_max_failures_spin.setValue(default_config.auth_failure_detection.socks_max_failures)
                    self.socks_ban_duration_spin.setValue(default_config.auth_failure_detection.socks_ban_duration)

                    self.on_auth_failure_enabled_changed(default_config.auth_failure_detection.enabled)

                    self.enable_scan_check.setChecked(default_config.advanced.enable_scan_protection)
                    self.on_scan_enabled_changed(default_config.advanced.enable_scan_protection)

                    self.enable_rapid_connection_check.setChecked(default_config.advanced.rapid_connection_detection.enabled)
                    self.http_threshold_spin.setValue(default_config.advanced.rapid_connection_detection.http_threshold)
                    self.http_window_spin.setValue(default_config.advanced.rapid_connection_detection.http_window)
                    self.socks_threshold_spin.setValue(default_config.advanced.rapid_connection_detection.socks_threshold)
                    self.socks_window_spin.setValue(default_config.advanced.rapid_connection_detection.socks_window)

                    self.on_rapid_connection_enabled_changed(default_config.advanced.rapid_connection_detection.enabled)

                finally:
                    self.blockSignals(False)

            except Exception as inner_e:
                logger.error(f"设置默认配置也失败: {inner_e}")
        finally:
            self._is_loading_config = False

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        try:
            config = self.get_config()

            # 验证文件路径
            for key, path in [
                ('黑名单文件', config.core.blacklist_file),
                ('白名单文件', config.core.whitelist_file),
                ('封禁历史文件', config.core.ban_history_file)
            ]:
                if not path:
                    return False, f"{key}不能为空"

            # 验证HTTP/SOCKS5配置逻辑
            if config.advanced.rapid_connection_detection.enabled:
                http_threshold = config.advanced.rapid_connection_detection.http_threshold
                socks_threshold = config.advanced.rapid_connection_detection.socks_threshold

                if socks_threshold >= http_threshold:
                    # 可以不强制SOCKS5阈值小于HTTP，但给出建议
                    pass

            # 验证扫描防护配置
            if config.advanced.enable_scan_protection:
                max_attempts = config.advanced.max_scan_attempts
                if max_attempts < 1 or max_attempts > 50:
                    return False, "最大扫描尝试次数应在1-50之间"

            return True, "配置验证通过"

        except Exception as e:
            logger.error(f"验证配置失败: {e}")
            return False, f"配置验证失败: {str(e)}"

    def is_modified(self) -> bool:
        """检查配置是否已修改"""
        return self._modified

    def clear_modified(self):
        """清除修改标记"""
        self._modified = False

    def manage_file_paths(self):
        """管理文件路径"""
        try:
            config = self.get_config()

            # 显示文件路径管理对话框
            dialog = FilePathManagerDialog(config, self)
            if dialog.exec():
                # 获取更新后的配置
                updated_config = dialog.get_config()
                self.set_config(updated_config)
                logger.info("文件路径已更新")

        except Exception as e:
            logger.error(f"管理文件路径失败: {e}")


class FilePathManagerDialog(QMessageBox):
    """文件路径管理对话框"""

    def __init__(self, config: SecurityConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.success = False

        self.setWindowTitle("文件路径管理")
        self.setIcon(QMessageBox.Question)

        # 创建自定义内容
        content = QWidget()
        layout = QVBoxLayout(content)

        info_label = QLabel("请设置安全管理文件的存储路径：")
        info_label.setStyleSheet("font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # 黑名单文件
        blacklist_layout = QHBoxLayout()
        blacklist_layout.setSpacing(5)
        blacklist_layout.addWidget(QLabel("黑名单文件:"))
        self.blacklist_edit = QLineEdit(self.config.core.blacklist_file)
        self.blacklist_edit.setMinimumWidth(250)
        blacklist_layout.addWidget(self.blacklist_edit)
        browse_blacklist_btn = QPushButton("浏览...")
        browse_blacklist_btn.clicked.connect(lambda: self.browse_file(self.blacklist_edit))
        blacklist_layout.addWidget(browse_blacklist_btn)
        layout.addLayout(blacklist_layout)

        # 白名单文件
        whitelist_layout = QHBoxLayout()
        whitelist_layout.setSpacing(5)
        whitelist_layout.addWidget(QLabel("白名单文件:"))
        self.whitelist_edit = QLineEdit(self.config.core.whitelist_file)
        self.whitelist_edit.setMinimumWidth(250)
        whitelist_layout.addWidget(self.whitelist_edit)
        browse_whitelist_btn = QPushButton("浏览...")
        browse_whitelist_btn.clicked.connect(lambda: self.browse_file(self.whitelist_edit))
        whitelist_layout.addWidget(browse_whitelist_btn)
        layout.addLayout(whitelist_layout)

        # 临时封禁文件
        ban_history_layout = QHBoxLayout()
        ban_history_layout.setSpacing(5)
        ban_history_layout.addWidget(QLabel("封禁历史文件:"))
        self.ban_history_edit = QLineEdit(self.config.core.ban_history_file)
        self.ban_history_edit.setMinimumWidth(250)
        ban_history_layout.addWidget(self.ban_history_edit)
        browse_ban_history_btn = QPushButton("浏览...")
        browse_ban_history_btn.clicked.connect(lambda: self.browse_file(self.ban_history_edit))
        ban_history_layout.addWidget(browse_ban_history_btn)
        layout.addLayout(ban_history_layout)

        # 添加到对话框
        self.layout().addWidget(content, 0, 1, 1, self.layout().columnCount() - 1)

        # 设置按钮
        self.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        self.buttonClicked.connect(self.on_button_clicked)

    def on_button_clicked(self, button):
        """按钮点击事件"""
        role = self.buttonRole(button)
        if role == QMessageBox.AcceptRole:
            # 验证文件路径
            if not self._validate_file_paths():
                # 显示错误消息但不关闭对话框
                self.setText("请填写所有文件路径")
                self.setIcon(QMessageBox.Warning)
                return
            self.success = True

    def _validate_file_paths(self) -> bool:
        """验证文件路径"""
        return (bool(self.blacklist_edit.text().strip()) and
                bool(self.whitelist_edit.text().strip()) and
                bool(self.ban_history_edit.text().strip()))

    def browse_file(self, line_edit: QLineEdit):
        """浏览文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择或创建文件", "", "JSON文件 (*.json);;所有文件 (*.*)"
        )
        if file_path:
            line_edit.setText(file_path)

    def get_config(self) -> SecurityConfig:
        """获取更新后的SecurityConfig对象"""
        # 创建新的CoreSecurityConfig
        new_core = CoreSecurityConfig(
            mode=self.config.core.mode,
            cleanup_interval=self.config.core.cleanup_interval,
            keep_ban_history=self.config.core.keep_ban_history,
            max_history_size=self.config.core.max_history_size,
            blacklist_file=self.blacklist_edit.text(),
            whitelist_file=self.whitelist_edit.text(),
            ban_history_file=self.ban_history_edit.text()
        )

        # 创建新的SecurityConfig
        return SecurityConfig(
            core=new_core,
            auth_failure_detection=self.config.auth_failure_detection,
            advanced=self.config.advanced
        )

    def exec(self) -> bool:
        """执行对话框"""
        super().exec()
        return self.success
