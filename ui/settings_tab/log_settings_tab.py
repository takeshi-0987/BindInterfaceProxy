import os
import logging
from typing import Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QGroupBox, QSpinBox,
    QComboBox, QFileDialog, QFrame, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from defaults.log_default import LogConfig, FileLogConfig, UILogConfig, ConsoleLogConfig

logger = logging.getLogger(__name__)


class LogSettingsTab(QWidget):
    """日志设置标签页 - 基于LogConfig dataclass"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self.init_ui()
        self.set_default_config()  # 初始化时使用默认配置

    def init_ui(self):
        """初始化UI"""
        # 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 主容器
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 页面说明
        description = QLabel(
            "日志设置：\n"
            "• 控制台日志：开发调试时在终端显示，建议保持DEBUG级别\n"
            "• 界面日志：在程序界面中显示，可控制显示行数\n"
            "• 文件日志：按级别分开存储，勾选需要的级别即可"
        )
        description.setWordWrap(True)
        description.setStyleSheet("""
            QLabel {
                padding: 10px;
                margin-bottom: 10px;
                font-size: 11px;
                color: #666;
                background-color: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
            }
        """)
        main_layout.addWidget(description)

        # 1. 控制台日志组
        self.console_group = self.create_console_group()
        main_layout.addWidget(self.console_group)

        # 2. 界面日志组
        self.ui_group = self.create_ui_group()
        main_layout.addWidget(self.ui_group)

        # 3. 文件日志组
        self.file_group = self.create_file_group()
        main_layout.addWidget(self.file_group)

        # 添加弹性空间
        main_layout.addStretch()

        scroll_area.setWidget(main_widget)

        # 设置主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def create_console_group(self) -> QGroupBox:
        """创建控制台日志配置组"""
        group = QGroupBox("控制台日志")
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

        # 启用开关
        self.console_enable = QCheckBox("启用控制台日志")
        self.console_enable.stateChanged.connect(self.mark_modified)
        layout.addWidget(self.console_enable)

        # 日志级别
        level_layout = QHBoxLayout()
        level_layout.setSpacing(8)

        level_layout.addWidget(QLabel("日志级别:"))
        self.console_level = QComboBox()
        self.console_level.setFixedWidth(120)
        self.console_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.console_level.currentTextChanged.connect(self.mark_modified)
        level_layout.addWidget(self.console_level)

        level_layout.addStretch()
        layout.addLayout(level_layout)

        # 说明文字
        desc_label = QLabel(
            "控制台日志主要用于开发和调试。\n"
            "打包成EXE后不会显示，请使用文件日志记录调试信息。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        group.setLayout(layout)
        return group

    def create_ui_group(self) -> QGroupBox:
        """创建界面日志配置组"""
        group = QGroupBox("界面日志")
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

        # 启用开关
        self.ui_enable = QCheckBox("启用界面日志")
        self.ui_enable.stateChanged.connect(self.on_ui_enable_changed)
        self.ui_enable.stateChanged.connect(self.mark_modified)
        layout.addWidget(self.ui_enable)

        # 配置网格
        config_layout = QVBoxLayout()
        config_layout.setSpacing(12)

        # 日志级别
        level_layout = QHBoxLayout()
        level_layout.setSpacing(2)

        level_label = QLabel("日志级别:")
        level_label.setMinimumWidth(65)
        level_layout.addWidget(level_label)

        self.ui_level = QComboBox()
        self.ui_level.setFixedWidth(120)
        self.ui_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.ui_level.currentTextChanged.connect(self.mark_modified)
        level_layout.addWidget(self.ui_level)

        level_layout.addStretch()
        config_layout.addLayout(level_layout)

        # 最大行数
        max_lines_layout = QHBoxLayout()
        max_lines_layout.setSpacing(2)

        max_lines_label = QLabel("最大行数:")
        max_lines_label.setMinimumWidth(65)
        max_lines_layout.addWidget(max_lines_label)

        self.ui_max_lines = QSpinBox()
        self.ui_max_lines.setFixedWidth(120)
        self.ui_max_lines.setRange(100, 10000)
        self.ui_max_lines.setSuffix(" 行")
        self.ui_max_lines.valueChanged.connect(self.mark_modified)
        max_lines_layout.addWidget(self.ui_max_lines)

        max_lines_layout.addStretch()
        config_layout.addLayout(max_lines_layout)

        layout.addLayout(config_layout)

        # 其他选项
        self.ui_auto_scroll = QCheckBox("自动滚动到最新")
        self.ui_auto_scroll.stateChanged.connect(self.mark_modified)
        layout.addWidget(self.ui_auto_scroll)

        # 说明文字
        desc_label = QLabel(
            "界面日志显示在程序的日志面板中，建议保持INFO级别以避免界面卡顿。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        group.setLayout(layout)
        return group

    def create_file_group(self) -> QGroupBox:
        """创建文件日志配置组"""
        group = QGroupBox("文件日志")
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
        layout.setSpacing(12)

        # 说明文字
        desc_label = QLabel("勾选需要记录的日志级别：（勾选即创建对应的日志文件）")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 8px;")
        layout.addWidget(desc_label)

        # 级别配置表格
        levels_frame = QFrame()
        levels_frame.setFrameShape(QFrame.StyledPanel)
        levels_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #dee2e6;
                padding: 12px;
            }
        """)

        levels_layout = QGridLayout()
        levels_layout.setSpacing(10)
        levels_layout.setColumnStretch(3, 1)

        # 表头
        levels_layout.addWidget(QLabel("级别"), 0, 0, Qt.AlignCenter)
        levels_layout.addWidget(QLabel("最大文件大小"), 0, 1, Qt.AlignCenter)
        levels_layout.addWidget(QLabel("备份数量"), 0, 2, Qt.AlignCenter)
        levels_layout.addWidget(QLabel("说明"), 0, 3, Qt.AlignCenter)

        # DEBUG级别配置
        self.debug_enable = QCheckBox("DEBUG")
        self.debug_enable.stateChanged.connect(self.on_level_enable_changed)
        self.debug_enable.stateChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.debug_enable, 1, 0)

        self.debug_size = QSpinBox()
        self.debug_size.setRange(1, 2000)
        self.debug_size.setSuffix(" MB")
        self.debug_size.setValue(50)
        self.debug_size.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.debug_size, 1, 1)

        self.debug_backup = QSpinBox()
        self.debug_backup.setRange(1, 50)
        self.debug_backup.setSuffix(" 个")
        self.debug_backup.setValue(3)
        self.debug_backup.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.debug_backup, 1, 2)

        debug_desc = QLabel("调试用，日志量很大")
        debug_desc.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        levels_layout.addWidget(debug_desc, 1, 3)

        # INFO级别配置
        self.info_enable = QCheckBox("INFO")
        self.info_enable.stateChanged.connect(self.on_level_enable_changed)
        self.info_enable.stateChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.info_enable, 2, 0)

        self.info_size = QSpinBox()
        self.info_size.setRange(1, 1000)
        self.info_size.setSuffix(" MB")
        self.info_size.setValue(20)
        self.info_size.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.info_size, 2, 1)

        self.info_backup = QSpinBox()
        self.info_backup.setRange(1, 99)
        self.info_backup.setSuffix(" 个")
        self.info_backup.setValue(5)
        self.info_backup.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.info_backup, 2, 2)

        info_desc = QLabel("常规记录，中等日志量")
        info_desc.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        levels_layout.addWidget(info_desc, 2, 3)

        # WARNING级别配置
        self.warning_enable = QCheckBox("WARNING")
        self.warning_enable.stateChanged.connect(self.on_level_enable_changed)
        self.warning_enable.stateChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.warning_enable, 3, 0)

        self.warning_size = QSpinBox()
        self.warning_size.setRange(1, 500)
        self.warning_size.setSuffix(" MB")
        self.warning_size.setValue(10)
        self.warning_size.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.warning_size, 3, 1)

        self.warning_backup = QSpinBox()
        self.warning_backup.setRange(1, 50)
        self.warning_backup.setSuffix(" 个")
        self.warning_backup.setValue(10)
        self.warning_backup.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.warning_backup, 3, 2)

        warning_desc = QLabel("警告信息，长期保存")
        warning_desc.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        levels_layout.addWidget(warning_desc, 3, 3)

        # ERROR级别配置
        self.error_enable = QCheckBox("ERROR")
        self.error_enable.stateChanged.connect(self.on_level_enable_changed)
        self.error_enable.stateChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.error_enable, 4, 0)

        self.error_size = QSpinBox()
        self.error_size.setRange(1, 200)
        self.error_size.setSuffix(" MB")
        self.error_size.setValue(5)
        self.error_size.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.error_size, 4, 1)

        self.error_backup = QSpinBox()
        self.error_backup.setRange(1, 99)
        self.error_backup.setSuffix(" 个")
        self.error_backup.setValue(20)
        self.error_backup.valueChanged.connect(self.mark_modified)
        levels_layout.addWidget(self.error_backup, 4, 2)

        error_desc = QLabel("错误信息，备份最多")
        error_desc.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        levels_layout.addWidget(error_desc, 4, 3)

        levels_frame.setLayout(levels_layout)
        layout.addWidget(levels_frame)

        # 文件名模板
        template_layout = QHBoxLayout()
        template_layout.setSpacing(8)

        template_layout.addWidget(QLabel("文件名模板:"))
        self.file_template = QLabel("logs/proxy_server_{level}.log")
        self.file_template.setStyleSheet("""
            QLabel {
                background-color: #fff;
                border: 1px solid #dee2e6;
                padding: 6px 8px;
                border-radius: 4px;
                color: #495057;
                font-family: monospace;
                min-height: 22px;
            }
        """)
        template_layout.addWidget(self.file_template, 1)

        layout.addLayout(template_layout)

        # 日志目录
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(8)

        dir_layout.addWidget(QLabel("日志目录:"))
        self.log_dir = QLineEdit()
        self.log_dir.textChanged.connect(self.on_log_dir_changed)
        self.log_dir.textChanged.connect(self.mark_modified)
        self.log_dir.setPlaceholderText("输入日志目录路径")
        self.log_dir.setStyleSheet("""
            QLineEdit {
                padding: 6px 8px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        dir_layout.addWidget(self.log_dir, 1)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_log_dir)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        dir_layout.addWidget(self.browse_btn)

        self.open_dir_btn = QPushButton("打开目录")
        self.open_dir_btn.clicked.connect(self.open_log_dir)
        self.open_dir_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        dir_layout.addWidget(self.open_dir_btn)

        layout.addLayout(dir_layout)

        # 文件日志说明
        file_desc = QLabel(
            "• DEBUG日志：文件大备份少，用于详细调试，建议开发阶段开启\n"
            "• INFO日志：中等文件中等备份，用于常规记录\n"
            "• WARNING日志：文件小备份多，用于记录警告\n"
            "• ERROR日志：文件小但备份最多，便于长期排查问题"
        )
        file_desc.setWordWrap(True)
        file_desc.setStyleSheet("color: #666; font-size: 11px; margin-top: 8px;")
        layout.addWidget(file_desc)

        group.setLayout(layout)
        return group

    def on_ui_enable_changed(self):
        """界面日志启用状态改变"""
        enabled = self.ui_enable.isChecked()
        self.ui_level.setEnabled(enabled)
        self.ui_max_lines.setEnabled(enabled)
        self.ui_auto_scroll.setEnabled(enabled)

    def on_level_enable_changed(self):
        """单个级别启用状态改变"""
        # DEBUG级别
        debug_enabled = self.debug_enable.isChecked()
        self.debug_size.setEnabled(debug_enabled)
        self.debug_backup.setEnabled(debug_enabled)

        # INFO级别
        info_enabled = self.info_enable.isChecked()
        self.info_size.setEnabled(info_enabled)
        self.info_backup.setEnabled(info_enabled)

        # WARNING级别
        warning_enabled = self.warning_enable.isChecked()
        self.warning_size.setEnabled(warning_enabled)
        self.warning_backup.setEnabled(warning_enabled)

        # ERROR级别
        error_enabled = self.error_enable.isChecked()
        self.error_size.setEnabled(error_enabled)
        self.error_backup.setEnabled(error_enabled)

        # 更新文件名模板
        self.update_file_template()

    def on_log_dir_changed(self):
        """日志目录改变"""
        self.update_file_template()

    def update_file_template(self):
        """更新文件名模板显示"""
        log_dir = self.log_dir.text().strip()
        if not log_dir:
            log_dir = "logs"

        # 确保目录路径标准化
        log_dir = log_dir.rstrip('/').rstrip('\\')

        # 更新模板显示
        template = f"{log_dir}/proxy_server_{{level}}.log"
        self.file_template.setText(template)

    def browse_log_dir(self):
        """浏览日志目录"""
        current_dir = self.log_dir.text()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = "."

        dir_path = QFileDialog.getExistingDirectory(
            self, "选择日志目录", current_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if dir_path:
            self.log_dir.setText(dir_path)

    def open_log_dir(self):
        """用系统文件管理器打开日志目录"""
        log_dir = self.log_dir.text().strip()

        if not log_dir:
            QMessageBox.warning(self, "提示", "请先设置日志目录")
            return

        # 如果目录不存在，尝试创建
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法创建日志目录:\n{str(e)}")
                return

        # 使用系统方式打开目录
        try:
            import platform
            import subprocess

            system = platform.system()

            if system == "Windows":
                os.startfile(log_dir)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", log_dir])
            else:  # Linux
                subprocess.run(["xdg-open", log_dir])

        except Exception as e:
            logger.error(f"打开日志目录失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开目录:\n{str(e)}")

    def mark_modified(self):
        """标记配置已修改"""
        self._modified = True
        self.config_modified.emit()

    def clear_modified(self):
        """清除修改标记"""
        self._modified = False

    def is_modified(self) -> bool:
        """检查配置是否已修改"""
        return self._modified

    def get_config(self) -> LogConfig:
        """获取LogConfig对象"""
        try:
            # 获取日志目录
            log_dir = self.log_dir.text().strip()
            if not log_dir:
                log_dir = "logs"

            # 创建ConsoleLogConfig对象
            console_config = ConsoleLogConfig(
                enabled=self.console_enable.isChecked(),
                level=self.console_level.currentText()
            )

            # 创建UILogConfig对象
            ui_config = UILogConfig(
                enabled=self.ui_enable.isChecked(),
                level=self.ui_level.currentText(),
                max_lines=self.ui_max_lines.value(),
                auto_scroll=self.ui_auto_scroll.isChecked()
            )

            # 创建FileLogConfig对象列表
            file_configs = []

            # DEBUG 级别
            if self.debug_enable.isChecked():
                file_configs.append(FileLogConfig(
                    enabled=True,
                    level='DEBUG',
                    filename=f"{log_dir}/proxy_server_debug.log",
                    max_size_mb=self.debug_size.value(),
                    backup_count=self.debug_backup.value()
                ))

            # INFO 级别
            if self.info_enable.isChecked():
                file_configs.append(FileLogConfig(
                    enabled=True,
                    level='INFO',
                    filename=f"{log_dir}/proxy_server_info.log",
                    max_size_mb=self.info_size.value(),
                    backup_count=self.info_backup.value()
                ))

            # WARNING 级别
            if self.warning_enable.isChecked():
                file_configs.append(FileLogConfig(
                    enabled=True,
                    level='WARNING',
                    filename=f"{log_dir}/proxy_server_warning.log",
                    max_size_mb=self.warning_size.value(),
                    backup_count=self.warning_backup.value()
                ))

            # ERROR 级别
            if self.error_enable.isChecked():
                file_configs.append(FileLogConfig(
                    enabled=True,
                    level='ERROR',
                    filename=f"{log_dir}/proxy_server_error.log",
                    max_size_mb=self.error_size.value(),
                    backup_count=self.error_backup.value()
                ))

            # 创建LogConfig对象
            log_config = LogConfig(
                console=console_config,
                ui=ui_config,
                file=file_configs
            )

            return log_config

        except Exception as e:
            logger.error(f"获取日志配置失败: {e}", exc_info=True)
            # 返回默认配置
            return LogConfig.get_default_config()

    def set_config(self, config: LogConfig):
        """设置LogConfig对象"""
        try:
            # 阻塞所有信号
            self.block_all_signals(True)

            # 如果config是字典，转换为LogConfig对象
            if isinstance(config, dict):
                config = LogConfig.from_dict(config)
            elif not isinstance(config, LogConfig):
                raise TypeError(f"期望LogConfig对象或字典，得到: {type(config)}")

            # 设置控制台配置
            self.console_enable.setChecked(config.console.enabled)
            self.console_level.setCurrentText(config.console.level)

            # 设置界面配置
            self.ui_enable.setChecked(config.ui.enabled)
            self.ui_level.setCurrentText(config.ui.level)
            self.ui_max_lines.setValue(config.ui.max_lines)
            self.ui_auto_scroll.setChecked(config.ui.auto_scroll)

            # 设置文件配置
            log_dir = "logs"  # 默认目录

            # # 重置所有文件级别
            # self.debug_enable.setChecked(False)
            # self.info_enable.setChecked(False)
            # self.warning_enable.setChecked(False)
            # self.error_enable.setChecked(False)

            # 设置各个文件级别
            for file_config in config.file:

                if file_config.level == 'DEBUG':
                    self.debug_enable.setChecked(True) if file_config.enabled else self.debug_enable.setChecked(False)
                    self.debug_size.setValue(file_config.max_size_mb)
                    self.debug_backup.setValue(file_config.backup_count)

                elif file_config.level == 'INFO':
                    self.info_enable.setChecked(True) if file_config.enabled else self.info_enable.setChecked(False)
                    self.info_size.setValue(file_config.max_size_mb)
                    self.info_backup.setValue(file_config.backup_count)

                elif file_config.level == 'WARNING':
                    self.warning_enable.setChecked(True) if file_config.enabled else self.warning_enable.setChecked(False)
                    self.warning_size.setValue(file_config.max_size_mb)
                    self.warning_backup.setValue(file_config.backup_count)

                elif file_config.level == 'ERROR':
                    self.error_enable.setChecked(True)  if file_config.enabled else self.error_enable.setChecked(False)
                    self.error_size.setValue(file_config.max_size_mb)
                    self.error_backup.setValue(file_config.backup_count)

                # 从文件名中提取目录
                if file_config.filename:
                    dir_path = os.path.dirname(file_config.filename)
                    if dir_path:
                        log_dir = dir_path

            # 设置目录
            self.log_dir.setText(log_dir)

            # 更新控件状态
            self.update_widget_states()

            # 清除修改标记
            self.clear_modified()

        except Exception as e:
            logger.error(f"设置日志配置失败: {e}")
            # 出错时使用默认配置
            try:
                self.set_config(LogConfig.get_default_config())
            except Exception as inner_e:
                logger.error(f"回退到默认配置也失败: {inner_e}")
                # 直接设置UI
                self.block_all_signals(True)
                try:
                    self.console_enable.setChecked(True)
                    self.console_level.setCurrentText('DEBUG')

                    self.ui_enable.setChecked(True)
                    self.ui_level.setCurrentText('INFO')
                    self.ui_max_lines.setValue(1000)
                    self.ui_auto_scroll.setChecked(True)

                    # 使用LogConfig.get_default_config()的默认值
                    default_config = LogConfig.get_default_config()

                    # 只设置启用的日志级别
                    for file_config in default_config.file:
                        if file_config.enabled:
                            if file_config.level == 'DEBUG':
                                self.debug_enable.setChecked(True)
                                self.debug_size.setValue(file_config.max_size_mb)
                                self.debug_backup.setValue(file_config.backup_count)
                            elif file_config.level == 'INFO':
                                self.info_enable.setChecked(True)
                                self.info_size.setValue(file_config.max_size_mb)
                                self.info_backup.setValue(file_config.backup_count)
                            elif file_config.level == 'WARNING':
                                self.warning_enable.setChecked(True)
                                self.warning_size.setValue(file_config.max_size_mb)
                                self.warning_backup.setValue(file_config.backup_count)
                            elif file_config.level == 'ERROR':
                                self.error_enable.setChecked(True)
                                self.error_size.setValue(file_config.max_size_mb)
                                self.error_backup.setValue(file_config.backup_count)

                    self.log_dir.setText('logs')

                    self.update_widget_states()
                finally:
                    self.block_all_signals(False)
        finally:
            self.block_all_signals(False)

    def block_all_signals(self, block: bool):
        """阻塞或恢复所有信号"""
        widgets = [
            self.console_enable, self.console_level,
            self.ui_enable, self.ui_level, self.ui_max_lines,
            self.ui_auto_scroll,
            self.debug_enable, self.debug_size,
            self.debug_backup, self.info_enable, self.info_size,
            self.info_backup, self.warning_enable, self.warning_size,
            self.warning_backup, self.error_enable, self.error_size,
            self.error_backup, self.log_dir
        ]

        for widget in widgets:
            if hasattr(widget, 'blockSignals'):
                widget.blockSignals(block)

    def update_widget_states(self):
        """更新所有控件的启用状态"""
        self.on_ui_enable_changed()
        self.on_level_enable_changed()

    def set_default_config(self):
        """设置默认配置"""
        self.block_all_signals(True)

        try:
            # 使用默认配置
            default_config = LogConfig.get_default_config()

            # 设置控制台配置
            self.console_enable.setChecked(default_config.console.enabled)
            self.console_level.setCurrentText(default_config.console.level)

            # 设置界面配置
            self.ui_enable.setChecked(default_config.ui.enabled)
            self.ui_level.setCurrentText(default_config.ui.level)
            self.ui_max_lines.setValue(default_config.ui.max_lines)
            self.ui_auto_scroll.setChecked(default_config.ui.auto_scroll)

            # 设置文件配置
            log_dir = "logs"

            # 设置默认的文件配置
            for file_config in default_config.file:
                if file_config.level == 'DEBUG':
                    self.debug_enable.setChecked(True) if file_config.enabled else self.debug_enable.setChecked(False)
                    self.debug_size.setValue(file_config.max_size_mb)
                    self.debug_backup.setValue(file_config.backup_count)

                elif file_config.level == 'INFO':
                    self.info_enable.setChecked(True) if file_config.enabled else self.info_enable.setChecked(False)
                    self.info_size.setValue(file_config.max_size_mb)
                    self.info_backup.setValue(file_config.backup_count)

                elif file_config.level == 'WARNING':
                    self.warning_enable.setChecked(True) if file_config.enabled else self.warning_enable.setChecked(False)
                    self.warning_size.setValue(file_config.max_size_mb)
                    self.warning_backup.setValue(file_config.backup_count)

                elif file_config.level == 'ERROR':
                    self.error_enable.setChecked(True) if file_config.enabled else self.error_enable.setChecked(False)
                    self.error_size.setValue(file_config.max_size_mb)
                    self.error_backup.setValue(file_config.backup_count)

                # 从文件名提取目录
                if file_config.filename:
                    dir_path = os.path.dirname(file_config.filename)
                    if dir_path:
                        log_dir = dir_path

            # 设置目录
            self.log_dir.setText(log_dir)

            # 更新控件状态
            self.update_widget_states()

        finally:
            self.block_all_signals(False)

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        # 检查目录是否有效
        log_dir = self.log_dir.text().strip()

        # 检查是否设置了目录
        if not log_dir:
            return False, "请设置日志目录"

        # 检查是否有至少一个级别被启用
        # if not (self.debug_enable.isChecked() or
        #         self.info_enable.isChecked() or
        #         self.warning_enable.isChecked() or
        #         self.error_enable.isChecked()):
        #     return False, "请至少启用一个日志级别"

        # 尝试创建目录（但不报错，只是检查权限）
        try:
            test_path = os.path.join(log_dir, ".test_write")
            os.makedirs(log_dir, exist_ok=True)
            # 尝试创建一个临时文件检查写入权限
            with open(test_path, 'w') as f:
                f.write('test')
            os.remove(test_path)
        except Exception as e:
            return False, f"日志目录无法访问或创建失败：{str(e)}"

        return True, "日志配置验证通过"
