# settings/ip_geo_settings.py

import os
import re  # 添加这个
import logging
from typing import Dict, Tuple, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QLineEdit, QComboBox, QPushButton, QFileDialog, QGroupBox,
    QSpinBox, QScrollArea, QListWidget, QAbstractItemView,
    QListWidgetItem, QMessageBox, QFrame, QSizePolicy, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Signal, Qt

from defaults.config_manager import get_config_manager
from defaults.ip_geo_default import (IPGeoConfig, DatabaseConfig, SearchURLConfig,
                                    DisplayConfig, QueryStrategyConfig, CacheConfig
                                    )

logger = logging.getLogger(__name__)


class DatabaseConfigDialog(QDialog):
    """数据库配置对话框"""

    def __init__(self, config: DatabaseConfig = None, parent=None):
        super().__init__(parent)
        self.config = config or DatabaseConfig(name="", path="", db_type="mmdb", priority=1)
        self.init_ui()
        self.load_config()

    def init_ui(self):
        self.setWindowTitle("配置本地数据库")
        self.setMinimumSize(500, 300)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 说明文字
        desc_label = QLabel(
            "配置本地IP地理数据库，完全离线工作。\n"
            "支持的格式：GeoLite2 (.mmdb)、IP2Location (.bin)"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 数据库名称
        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)

        name_label = QLabel("数据库名称:")
        name_label.setMinimumWidth(100)
        name_layout.addWidget(name_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：GeoLite2-City")
        name_layout.addWidget(self.name_edit, 1)

        layout.addLayout(name_layout)

        # 数据库类型
        type_layout = QHBoxLayout()
        type_layout.setSpacing(8)

        type_label = QLabel("数据库类型:")
        type_label.setMinimumWidth(100)
        type_layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["mmdb", "ip2location_bin"])
        self.type_combo.setCurrentText("mmdb")
        type_layout.addWidget(self.type_combo, 1)

        layout.addLayout(type_layout)

        # 文件路径
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        path_label = QLabel("文件路径:")
        path_label.setMinimumWidth(100)
        path_layout.addWidget(path_label)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择数据库文件")
        path_layout.addWidget(self.path_edit, 1)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_file)
        path_layout.addWidget(self.browse_btn)

        layout.addLayout(path_layout)

        # 启用开关
        self.enabled_check = QCheckBox("启用此数据库")
        self.enabled_check.setChecked(True)
        layout.addWidget(self.enabled_check)

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

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)

        # 设置按钮样式
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setDefault(True)

        layout.addWidget(button_box)

        self.setLayout(layout)

    def load_config(self):
        """加载配置"""
        self.name_edit.setText(self.config.name)
        self.type_combo.setCurrentText(self.config.db_type)
        self.path_edit.setText(self.config.path)
        self.enabled_check.setChecked(self.config.enabled)

    def browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择数据库文件", "",
            "数据库文件 (*.mmdb *.bin *.dat *.csv *.txt);;所有文件 (*.*)"
        )
        if file_path:
            self.path_edit.setText(file_path)

            # 根据文件扩展名自动设置类型
            if file_path.endswith('.mmdb'):
                self.type_combo.setCurrentText("mmdb")
            elif file_path.endswith('.bin'):
                self.type_combo.setCurrentText("ip2location_bin")

            self.show_status(f"已选择文件: {os.path.basename(file_path)}", "success")

    def get_config(self) -> DatabaseConfig:
        """获取配置"""
        return DatabaseConfig(
            name=self.name_edit.text(),
            path=self.path_edit.text(),
            db_type=self.type_combo.currentText(),
            enabled=self.enabled_check.isChecked(),
            priority=self.config.priority  # 保持原有的优先级（实际会根据列表顺序调整）
        )

    def validate_and_accept(self):
        """验证配置并接受"""
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()

        if not name:
            self.show_status("数据库名称不能为空", "error")
            return

        if not path:
            self.show_status("请选择数据库文件", "error")
            return

        if not os.path.exists(path):
            reply = QMessageBox.question(
                self, "文件不存在",
                f"数据库文件不存在：{path}\n是否继续保存？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
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


class DatabaseListWidget(QWidget):
    """数据库列表管理部件"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.database_configs = []  # 存储数据库配置列表
        self.current_index = -1
        self._modified = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # 说明文字
        desc_label = QLabel(
            "本地数据库列表：列表顺序即为查询优先级（从上到下优先级递减）。\n"
            "至少需要一个启用的数据库才能正常查询。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 8px;")
        layout.addWidget(desc_label)

        # 列表和操作按钮区域
        list_container = QWidget()
        list_container_layout = QHBoxLayout()
        list_container_layout.setSpacing(10)

        # 数据库列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setMinimumHeight(200)
        self.list_widget.currentRowChanged.connect(self.on_item_selected)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.edit_database)
        list_container_layout.addWidget(self.list_widget)

        # 操作按钮
        btn_container = QWidget()
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        # 新建按钮
        self.add_btn = QPushButton("新建")
        self.add_btn.clicked.connect(self.add_database)
        self.add_btn.setMinimumHeight(35)
        self.add_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.add_btn)

        # 编辑按钮
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_database)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setMinimumHeight(35)
        self.edit_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.edit_btn)

        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_database)
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
        self.move_up_btn.setToolTip("将选中的数据库向上移动一位（提高优先级）")
        btn_layout.addWidget(self.move_up_btn)

        # 下移按钮
        self.move_down_btn = QPushButton("↓ 下移")
        self.move_down_btn.clicked.connect(self.move_down)
        self.move_down_btn.setEnabled(False)
        self.move_down_btn.setMinimumHeight(35)
        self.move_down_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.move_down_btn.setToolTip("将选中的数据库向下移动一位（降低优先级）")
        btn_layout.addWidget(self.move_down_btn)

        # 分隔线
        separator = QLabel()
        separator.setFrameShape(QLabel.HLine)
        separator.setStyleSheet("color: #dee2e6; margin: 8px 0;")
        btn_layout.addWidget(separator)

        # 启用/禁用按钮
        self.enable_btn = QPushButton("启用/禁用")
        self.enable_btn.clicked.connect(self.toggle_enabled)
        self.enable_btn.setEnabled(False)
        self.enable_btn.setMinimumHeight(35)
        self.enable_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.enable_btn.setToolTip("切换选中数据库的启用状态")
        btn_layout.addWidget(self.enable_btn)

        btn_layout.addStretch()
        btn_container.setLayout(btn_layout)
        btn_container.setFixedWidth(140)

        list_container_layout.addWidget(btn_container)
        list_container.setLayout(list_container_layout)
        layout.addWidget(list_container)

        # 统计信息
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)

        self.total_label = QLabel("总计: 0")
        self.enabled_label = QLabel("已启用: 0")
        self.disabled_label = QLabel("已禁用: 0")

        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.enabled_label)
        stats_layout.addWidget(self.disabled_label)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        self.setLayout(layout)

    def move_up(self):
        """上移选中的数据库（提高优先级）"""
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            item_current = self.list_widget.takeItem(current_row)
            item_above = self.list_widget.takeItem(current_row - 1)

            self.list_widget.insertItem(current_row - 1, item_current)
            self.list_widget.insertItem(current_row, item_above)

            config_current = self.database_configs.pop(current_row)
            config_above = self.database_configs.pop(current_row - 1)

            self.database_configs.insert(current_row - 1, config_current)
            self.database_configs.insert(current_row, config_above)

            self.list_widget.setCurrentRow(current_row - 1)
            self.update_move_buttons()
            self.update_priorities()
            self.emit_data_changed()

    def move_down(self):
        """下移选中的数据库（降低优先级）"""
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            item_current = self.list_widget.takeItem(current_row)
            item_below = self.list_widget.takeItem(current_row)

            self.list_widget.insertItem(current_row, item_below)
            self.list_widget.insertItem(current_row + 1, item_current)

            config_current = self.database_configs.pop(current_row)
            config_below = self.database_configs.pop(current_row)

            self.database_configs.insert(current_row, config_below)
            self.database_configs.insert(current_row + 1, config_current)

            self.list_widget.setCurrentRow(current_row + 1)
            self.update_move_buttons()
            self.update_priorities()
            self.emit_data_changed()

    def update_move_buttons(self):
        """更新上移/下移按钮状态"""
        current_row = self.list_widget.currentRow()
        count = self.list_widget.count()

        self.move_up_btn.setEnabled(current_row > 0)
        self.move_down_btn.setEnabled(0 <= current_row < count - 1)

    def update_priorities(self):
        """根据列表顺序更新所有数据库的优先级"""
        for i, config in enumerate(self.database_configs, 1):
            config.priority = i
            # 更新列表项显示
            item = self.list_widget.item(i - 1)
            if item:
                item.setText(self.generate_display_name(config))

    def add_database(self):
        """新增数据库"""
        dialog = DatabaseConfigDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            new_config = dialog.get_config()
            new_config.priority = len(self.database_configs) + 1  # 设置优先级
            self.add_config_to_list(new_config)
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)
            self.on_item_selected(self.list_widget.count() - 1)
            self.update_stats()

    def add_config_to_list(self, config: DatabaseConfig):
        """添加配置到列表"""
        display_name = self.generate_display_name(config)
        item = QListWidgetItem(display_name)
        item.setData(Qt.UserRole, config)
        self.list_widget.addItem(item)
        self.database_configs.append(config)
        self.update_move_buttons()
        self.emit_data_changed()

    def edit_database(self):
        """编辑选中的数据库"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            config = self.database_configs[current_row]

            dialog = DatabaseConfigDialog(config, parent=self)
            if dialog.exec() == QDialog.Accepted:
                new_config = dialog.get_config()
                new_config.priority = config.priority  # 保持原有优先级

                # 更新列表
                self.database_configs[current_row] = new_config
                display_name = self.generate_display_name(new_config)
                item = self.list_widget.item(current_row)
                item.setText(display_name)
                item.setData(Qt.UserRole, new_config)

                self.emit_data_changed()
                self.update_stats()

    def toggle_enabled(self):
        """切换选中数据库的启用状态"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            config = self.database_configs[current_row]
            config.enabled = not config.enabled

            # 更新列表显示
            display_name = self.generate_display_name(config)
            item = self.list_widget.item(current_row)
            item.setText(display_name)
            item.setData(Qt.UserRole, config)

            # 更新按钮文本
            self.enable_btn.setText("禁用" if config.enabled else "启用")

            self.emit_data_changed()
            self.update_stats()

    def delete_database(self):
        """删除选中的数据库"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "确认删除",
                "确定要删除这个数据库配置吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.list_widget.takeItem(current_row)
                self.database_configs.pop(current_row)

                # 重新计算优先级
                self.update_priorities()

                if self.list_widget.count() > 0:
                    new_row = min(current_row, self.list_widget.count() - 1)
                    self.list_widget.setCurrentRow(new_row)
                    self.on_item_selected(new_row)
                    self.update_move_buttons()
                else:
                    self.edit_btn.setEnabled(False)
                    self.delete_btn.setEnabled(False)
                    self.move_up_btn.setEnabled(False)
                    self.move_down_btn.setEnabled(False)
                    self.enable_btn.setEnabled(False)

                self.emit_data_changed()
                self.update_stats()

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

    def generate_display_name(self, config: DatabaseConfig) -> str:
        """生成显示名称"""
        status = "✓" if config.enabled else "✗"
        priority = f"P{config.priority}"
        name = config.name or "未命名"

        # 提取文件名
        if config.path:
            filename = os.path.basename(config.path)
            db_type = config.db_type.upper()
            return f"{status} [{priority}] {name} ({filename}, {db_type})"

        return f"{status} [{priority}] {name}"

    def on_item_selected(self, row):
        """处理项选择"""
        self.current_index = row

        if row >= 0:
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.enable_btn.setEnabled(True)
            self.update_move_buttons()

            # 设置启用/禁用按钮文本
            if row < len(self.database_configs):
                config = self.database_configs[row]
                self.enable_btn.setText("禁用" if config.enabled else "启用")
        else:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            self.enable_btn.setEnabled(False)

    def update_stats(self):
        """更新统计信息"""
        total = len(self.database_configs)
        enabled = sum(1 for config in self.database_configs if config.enabled)
        disabled = total - enabled

        self.total_label.setText(f"总计: {total}")
        self.enabled_label.setText(f"已启用: {enabled}")
        self.disabled_label.setText(f"已禁用: {disabled}")

    def get_configs(self) -> List[DatabaseConfig]:
        """获取所有配置"""
        return self.database_configs.copy()

    def set_configs(self, configs: List[DatabaseConfig]):
        """设置配置列表"""
        # 清空列表
        self.list_widget.clear()
        self.database_configs.clear()

        if not configs:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            self.enable_btn.setEnabled(False)
            self.update_stats()
            return

        # 按优先级排序
        configs.sort(key=lambda x: x.priority)

        # 添加到列表
        for config in configs:
            self.add_config_to_list(config)

        if self.database_configs:
            self.list_widget.setCurrentRow(0)
            self.on_item_selected(0)
        else:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            self.enable_btn.setEnabled(False)

        self.update_stats()
        self._modified = False


class SearchURLConfigDialog(QDialog):
    """搜索网址配置对话框"""

    def __init__(self, config: Dict[str, str] = None, parent=None):
        super().__init__(parent)
        self.config = config or {"name": "", "url": ""}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        self.setWindowTitle("配置搜索网址")
        self.setMinimumSize(500, 200)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 说明文字
        desc_label = QLabel(
            "配置在线搜索网址，{ip} 会被替换为实际IP地址。\n"
            "例如：https://www.google.com/search?q=ip+{ip}"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 网站名称
        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)

        name_label = QLabel("网站名称:")
        name_label.setMinimumWidth(80)
        name_layout.addWidget(name_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：ip138查询")
        name_layout.addWidget(self.name_edit, 1)

        layout.addLayout(name_layout)

        # URL模板
        url_layout = QHBoxLayout()
        url_layout.setSpacing(8)

        url_label = QLabel("URL模板:")
        url_label.setMinimumWidth(80)
        url_layout.addWidget(url_label)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("如：https://www.ip138.com/iplookup.asp?ip={ip}&action=2")
        url_layout.addWidget(self.url_edit, 1)

        layout.addLayout(url_layout)

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

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)

        # 设置按钮样式
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setDefault(True)

        layout.addWidget(button_box)

        self.setLayout(layout)

    def load_config(self):
        """加载配置"""
        self.name_edit.setText(self.config.get('name', ''))
        self.url_edit.setText(self.config.get('url', ''))

    def get_config(self) -> Dict[str, str]:
        """获取配置"""
        return {
            'name': self.name_edit.text(),
            'url': self.url_edit.text()
        }

    def validate_and_accept(self):
        """验证配置并接受"""
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()

        if not name:
            self.show_status("网站名称不能为空", "error")
            return

        if not url:
            self.show_status("URL模板不能为空", "error")
            return

        if '{ip}' not in url:
            reply = QMessageBox.question(
                self, "确认保存",
                "URL模板中不包含 {ip} 占位符，可能无法正确替换IP地址。\n是否继续保存？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
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


class SearchURLListWidget(QWidget):
    """搜索网址列表管理部件"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_configs = []  # 存储搜索网址配置列表
        self.current_index = -1
        self._modified = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # 列表和操作按钮区域
        list_container = QWidget()
        list_container_layout = QHBoxLayout()
        list_container_layout.setSpacing(10)

        # 搜索网址列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setMinimumHeight(200)
        self.list_widget.currentRowChanged.connect(self.on_item_selected)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.edit_search_url)
        list_container_layout.addWidget(self.list_widget)

        # 操作按钮
        btn_container = QWidget()
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        # 新建按钮
        self.add_btn = QPushButton("新建")
        self.add_btn.clicked.connect(self.add_search_url)
        self.add_btn.setMinimumHeight(35)
        self.add_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.add_btn)

        # 编辑按钮
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_search_url)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setMinimumHeight(35)
        self.edit_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.edit_btn)

        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_search_url)
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
        self.move_up_btn.setToolTip("将选中的网址向上移动一位")
        btn_layout.addWidget(self.move_up_btn)

        # 下移按钮
        self.move_down_btn = QPushButton("↓ 下移")
        self.move_down_btn.clicked.connect(self.move_down)
        self.move_down_btn.setEnabled(False)
        self.move_down_btn.setMinimumHeight(35)
        self.move_down_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.move_down_btn.setToolTip("将选中的网址向下移动一位")
        btn_layout.addWidget(self.move_down_btn)

        # 分隔线
        separator = QLabel()
        separator.setFrameShape(QLabel.HLine)
        separator.setStyleSheet("color: #dee2e6; margin: 8px 0;")
        btn_layout.addWidget(separator)

        # 加载默认按钮
        self.load_default_btn = QPushButton("加载默认")
        self.load_default_btn.clicked.connect(self.load_default_urls)
        self.load_default_btn.setMinimumHeight(35)
        self.load_default_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.load_default_btn)

        # 清空按钮
        self.clear_all_btn = QPushButton("清空全部")
        self.clear_all_btn.clicked.connect(self.clear_all_urls)
        self.clear_all_btn.setMinimumHeight(35)
        self.clear_all_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.clear_all_btn)

        btn_layout.addStretch()
        btn_container.setLayout(btn_layout)
        btn_container.setFixedWidth(140)

        list_container_layout.addWidget(btn_container)
        list_container.setLayout(list_container_layout)
        layout.addWidget(list_container)

        self.setLayout(layout)

    def move_up(self):
        """上移选中的网址"""
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            item_current = self.list_widget.takeItem(current_row)
            item_above = self.list_widget.takeItem(current_row - 1)

            self.list_widget.insertItem(current_row - 1, item_current)
            self.list_widget.insertItem(current_row, item_above)

            config_current = self.search_configs.pop(current_row)
            config_above = self.search_configs.pop(current_row - 1)

            self.search_configs.insert(current_row - 1, config_current)
            self.search_configs.insert(current_row, config_above)

            self.list_widget.setCurrentRow(current_row - 1)
            self.update_move_buttons()
            self.emit_data_changed()

    def move_down(self):
        """下移选中的网址"""
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            item_current = self.list_widget.takeItem(current_row)
            item_below = self.list_widget.takeItem(current_row)

            self.list_widget.insertItem(current_row, item_below)
            self.list_widget.insertItem(current_row + 1, item_current)

            config_current = self.search_configs.pop(current_row)
            config_below = self.search_configs.pop(current_row)

            self.search_configs.insert(current_row, config_below)
            self.search_configs.insert(current_row + 1, config_current)

            self.list_widget.setCurrentRow(current_row + 1)
            self.update_move_buttons()
            self.emit_data_changed()

    def update_move_buttons(self):
        """更新上移/下移按钮状态"""
        current_row = self.list_widget.currentRow()
        count = self.list_widget.count()

        self.move_up_btn.setEnabled(current_row > 0)
        self.move_down_btn.setEnabled(0 <= current_row < count - 1)

    def add_search_url(self):
        """新增搜索网址"""
        dialog = SearchURLConfigDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            new_config = dialog.get_config()
            self.add_config_to_list(new_config)
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)
            self.on_item_selected(self.list_widget.count() - 1)

    def add_config_to_list(self, config: Dict[str, str]):
        """添加配置到列表"""
        display_name = self.generate_display_name(config)
        item = QListWidgetItem(display_name)
        item.setData(Qt.UserRole, config)
        self.list_widget.addItem(item)
        self.search_configs.append(config)
        self.update_move_buttons()
        self.emit_data_changed()

    def edit_search_url(self):
        """编辑选中的搜索网址"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            config = self.search_configs[current_row]

            dialog = SearchURLConfigDialog(config, parent=self)
            if dialog.exec() == QDialog.Accepted:
                new_config = dialog.get_config()

                # 更新列表
                self.search_configs[current_row] = new_config
                display_name = self.generate_display_name(new_config)
                item = self.list_widget.item(current_row)
                item.setText(display_name)
                item.setData(Qt.UserRole, new_config)

                self.emit_data_changed()

    def delete_search_url(self):
        """删除选中的搜索网址"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "确认删除",
                "确定要删除这个搜索网址吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.list_widget.takeItem(current_row)
                self.search_configs.pop(current_row)

                if self.list_widget.count() > 0:
                    new_row = min(current_row, self.list_widget.count() - 1)
                    self.list_widget.setCurrentRow(new_row)
                    self.on_item_selected(new_row)
                    self.update_move_buttons()
                else:
                    self.edit_btn.setEnabled(False)
                    self.delete_btn.setEnabled(False)
                    self.move_up_btn.setEnabled(False)
                    self.move_down_btn.setEnabled(False)

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

    def generate_display_name(self, config: Dict[str, str]) -> str:
        """生成显示名称"""
        name = config.get('name', '未命名')
        url = config.get('url', '')

        # 简化URL显示
        if url:
            # 提取域名部分
            if '://' in url:
                domain = url.split('://')[1].split('/')[0]
                return f"{name} ({domain})"

        return name

    def on_item_selected(self, row):
        """处理项选择"""
        self.current_index = row

        if row >= 0:
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.update_move_buttons()
        else:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)

    def load_default_urls(self):
        """加载默认网址"""
        reply = QMessageBox.question(
            self, "加载默认网址",
            "这将替换当前的所有网址配置，是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            from defaults.ip_geo_default import SearchURLConfig
            default_urls = SearchURLConfig().urls

            # 清空列表
            self.list_widget.clear()
            self.search_configs.clear()

            # 添加默认网址
            for config in default_urls:
                self.add_config_to_list(config)

            if self.search_configs:
                self.list_widget.setCurrentRow(0)
                self.on_item_selected(0)

            self.emit_data_changed()

    def clear_all_urls(self):
        """清空所有网址"""
        reply = QMessageBox.question(
            self, "清空网址",
            "确定要清空所有搜索网址吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.list_widget.clear()
            self.search_configs.clear()

            # 更新按钮状态
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)

            self.emit_data_changed()

    def get_configs(self) -> List[Dict[str, str]]:
        """获取所有配置"""
        return self.search_configs.copy()

    def set_configs(self, configs: List[Dict[str, str]]):
        """设置配置列表"""
        # 清空列表
        self.list_widget.clear()
        self.search_configs.clear()

        if not configs:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            return

        # 添加到列表
        for config in configs:
            self.add_config_to_list(config)

        if self.search_configs:
            self.list_widget.setCurrentRow(0)
            self.on_item_selected(0)
        else:
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)

        self._modified = False


class IPGeoSettingsTab(QWidget):
    """IP地理信息设置控件"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self.database_widgets: List[DatabaseListWidget] = []
        self._custom_urls: List[Tuple[str, str]] = []
        self._is_initializing = True
        self._is_loading_config = False

        self.init_ui()
        self._connect_signals()
        self._is_initializing = False

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
            "IP地理位置查询设置：\n"
            "• 本地数据库：完全离线工作，支持多种数据库格式\n"
            "• 查询策略：配置查询方式和显示格式\n"
            "• 缓存配置：配置查询结果的缓存策略\n"
            "• 在线搜索：在浏览器中快速搜索IP信息\n\n"
            "注意：本功能基于本地数据库运行，无需网络连接即可查询IP地理位置。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("""
            QLabel {
                padding: 12px;
                margin-bottom: 10px;
                font-size: 11px;
                color: #666;
                background-color: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
                line-height: 1.4;
            }
        """)
        main_layout.addWidget(description)

        # 1. 主开关
        self.enable_check = QCheckBox("启用本地IP地理位置查询")
        self.enable_check.setStyleSheet("font-weight: bold;")
        self.enable_check.stateChanged.connect(self._on_enable_changed)
        main_layout.addWidget(self.enable_check)


        # 2. 本地数据库配置
        self.db_group = self.create_database_group()
        main_layout.addWidget(self.db_group)

        # 3. 查询策略配置
        self.query_group = self.create_query_strategy_group()
        main_layout.addWidget(self.query_group)

        # 4. 缓存配置
        self.cache_group = self.create_cache_group()
        main_layout.addWidget(self.cache_group)

        # 5. 显示配置
        self.display_group = self.create_display_group()
        main_layout.addWidget(self.display_group)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #dee2e6; margin: 10px 0;")
        main_layout.addWidget(line)

        # 6. 在线搜索配置
        self.search_group = self.create_search_urls_group()
        main_layout.addWidget(self.search_group)

        # 添加弹性空间
        main_layout.addStretch()

        scroll_area.setWidget(main_widget)

        # 设置主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def create_database_group(self) -> QGroupBox:
        """创建数据库配置组"""
        group = QGroupBox("本地数据库配置")
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

        # 说明文字
        desc_label = QLabel(
            "本地数据库提供最快的查询速度，完全离线工作。\n"
            "支持的格式：GeoLite2 (.mmdb)、IP2Location (.bin)\n"
            "列表顺序即为查询优先级（从上到下优先级递减）"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        # 数据库列表管理
        self.db_list = DatabaseListWidget()
        self.db_list.config_modified.connect(self._mark_modified)
        layout.addWidget(self.db_list)

        group.setLayout(layout)
        return group

    def create_query_strategy_group(self) -> QGroupBox:
        """创建查询策略配置组"""
        group = QGroupBox("查询策略")
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

        # 说明文字
        desc_label = QLabel("配置IP地址查询的方式和选项")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        # 配置网格
        config_layout = QVBoxLayout()
        config_layout.setSpacing(12)

        # 查询方式
        strategy_layout = QHBoxLayout()
        strategy_layout.setSpacing(8)

        strategy_label = QLabel("查询方式:")
        strategy_label.setMinimumWidth(80)
        strategy_layout.addWidget(strategy_label)

        self.strategy_combo = QComboBox()
        self.strategy_combo.setFixedWidth(150)
        self.strategy_combo.addItems(["串行查询", "并行查询"])
        self.strategy_combo.setToolTip("串行：按优先级顺序查询\n并行：同时查询所有数据库")
        self.strategy_combo.currentTextChanged.connect(self._mark_modified)
        strategy_layout.addWidget(self.strategy_combo)

        strategy_layout.addStretch()
        config_layout.addLayout(strategy_layout)

        # 并发查询数
        concurrent_layout = QHBoxLayout()
        concurrent_layout.setSpacing(8)

        concurrent_label = QLabel("最大并发数（并行适用）:")
        concurrent_label.setMinimumWidth(80)
        concurrent_layout.addWidget(concurrent_label)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setFixedWidth(90)
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(3)
        self.concurrent_spin.setSuffix(" 个")
        self.concurrent_spin.valueChanged.connect(self._mark_modified)
        concurrent_layout.addWidget(self.concurrent_spin)

        concurrent_layout.addStretch()
        config_layout.addLayout(concurrent_layout)

        layout.addLayout(config_layout)

        # 查询选项
        options_label = QLabel("查询选项:")
        options_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 5px;")
        layout.addWidget(options_label)

        self.skip_private_check = QCheckBox("跳过内网IP查询")
        self.skip_private_check.setChecked(True)
        self.skip_private_check.setToolTip("自动识别并跳过内网地址（如192.168.x.x, 10.x.x.x等）")
        self.skip_private_check.stateChanged.connect(self._mark_modified)
        layout.addWidget(self.skip_private_check)

        self.skip_special_check = QCheckBox("跳过特殊IP查询")
        self.skip_special_check.setChecked(True)
        self.skip_special_check.setToolTip("跳过回环地址（127.0.0.1）、组播地址等特殊IP")
        self.skip_special_check.stateChanged.connect(self._mark_modified)
        layout.addWidget(self.skip_special_check)

        self.stop_on_success_check = QCheckBox("找到第一个成功结果时停止")
        self.stop_on_success_check.setChecked(True)
        self.stop_on_success_check.setToolTip("获取到第一个成功的查询结果后不再查询其他数据库")
        self.stop_on_success_check.stateChanged.connect(self._mark_modified)
        layout.addWidget(self.stop_on_success_check)

        group.setLayout(layout)
        return group

    def create_cache_group(self) -> QGroupBox:
        """创建缓存配置组"""
        group = QGroupBox("缓存配置")
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

        # 说明文字
        desc_label = QLabel("配置查询结果的缓存策略，可以提高重复查询的性能")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        # 主开关
        self.cache_enable_check = QCheckBox("启用缓存")
        self.cache_enable_check.setChecked(True)
        self.cache_enable_check.setToolTip("启用查询结果缓存功能")
        self.cache_enable_check.stateChanged.connect(self._mark_modified)
        layout.addWidget(self.cache_enable_check)

        # 配置项布局 - 与查询策略保持一致
        config_layout = QVBoxLayout()
        config_layout.setSpacing(12)

        # 缓存时间
        ttl_layout = QHBoxLayout()
        ttl_layout.setSpacing(8)

        ttl_label = QLabel("缓存时间:")
        ttl_label.setMinimumWidth(80)  # 与查询策略对齐
        ttl_layout.addWidget(ttl_label)

        self.ttl_spin = QSpinBox()
        self.ttl_spin.setFixedWidth(150)
        self.ttl_spin.setRange(60, 86400)
        self.ttl_spin.setValue(600)
        self.ttl_spin.setSuffix(" 秒")
        self.ttl_spin.setToolTip("查询结果在缓存中保存的时间（秒）")
        self.ttl_spin.valueChanged.connect(self._mark_modified)
        ttl_layout.addWidget(self.ttl_spin)
        ttl_layout.addStretch()

        config_layout.addLayout(ttl_layout)

        # 最大缓存条数
        max_size_layout = QHBoxLayout()
        max_size_layout.setSpacing(8)

        max_size_label = QLabel("最大缓存条数:")
        max_size_label.setMinimumWidth(80)  # 与查询策略对齐
        max_size_layout.addWidget(max_size_label)

        self.max_size_spin = QSpinBox()
        self.max_size_spin.setFixedWidth(150)
        self.max_size_spin.setRange(10, 1000)
        self.max_size_spin.setValue(100)
        self.max_size_spin.setSuffix(" 条")
        self.max_size_spin.setToolTip("最多缓存多少个IP的查询结果")
        self.max_size_spin.valueChanged.connect(self._mark_modified)
        max_size_layout.addWidget(self.max_size_spin)
        max_size_layout.addStretch()

        config_layout.addLayout(max_size_layout)

        layout.addLayout(config_layout)
        group.setLayout(layout)

        return group

    def create_display_group(self) -> QGroupBox:
        """创建显示配置组"""
        group = QGroupBox("显示配置")
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

        # 说明文字
        desc_label = QLabel("配置IP地理位置的显示格式和选项")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        # 配置网格
        config_layout = QVBoxLayout()
        config_layout.setSpacing(12)

        # 位置格式
        format_layout = QHBoxLayout()
        format_layout.setSpacing(8)

        format_label = QLabel("位置格式（用于基础显示）:")
        format_label.setMinimumWidth(80)
        format_layout.addWidget(format_label)

        self.format_combo = QComboBox()
        self.format_combo.setFixedWidth(220)
        self.format_combo.addItems([
            "{country}",
            "{country}-{region}",
            "{country}-{region}-{city}",
            "自定义格式"
        ])
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo)

        # 自定义格式输入框
        self.custom_format_edit = QLineEdit()
        self.custom_format_edit.setPlaceholderText("支持字段：{country}、{region}、{city}、{isp}、{asn}")
        # self.custom_format_edit.setText("{country}-{region}-{city}")
        self.custom_format_edit.hide()
        format_layout.addWidget(self.custom_format_edit, 1)

        format_layout.addStretch()
        config_layout.addLayout(format_layout)

        layout.addLayout(config_layout)

        # 显示选项
        options_label = QLabel("显示选项（用于IP详情）:")
        options_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 5px;")
        layout.addWidget(options_label)

        self.show_isp_check = QCheckBox("显示ISP信息")
        self.show_isp_check.setChecked(True)
        self.show_isp_check.setToolTip("显示互联网服务提供商名称")
        self.show_isp_check.stateChanged.connect(self._mark_modified)
        layout.addWidget(self.show_isp_check)

        self.show_network_check = QCheckBox("显示网络信息")
        self.show_network_check.setChecked(True)
        self.show_network_check.setToolTip("显示网络CIDR等信息")
        self.show_network_check.stateChanged.connect(self._mark_modified)
        layout.addWidget(self.show_network_check)

        self.show_asn_check = QCheckBox("显示ASN信息")
        self.show_asn_check.setChecked(False)
        self.show_asn_check.setToolTip("显示自治系统号（需要数据库支持）")
        self.show_asn_check.stateChanged.connect(self._mark_modified)
        layout.addWidget(self.show_asn_check)

        group.setLayout(layout)
        return group


    def _on_format_changed(self, text):
        """格式选择改变"""
        if text == "自定义格式":
            self.custom_format_edit.show()
        else:
            self.custom_format_edit.hide()
        self._mark_modified()

    def create_search_urls_group(self) -> QGroupBox:
        """创建在线搜索配置组"""
        group = QGroupBox("在线搜索配置")
        group.setCheckable(True)
        group.setChecked(True)
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
            QGroupBox::indicator {
                width: 13px;
                height: 13px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # 说明文字
        desc_label = QLabel(
            "配置在线搜索网址，可在右键菜单中快速打开浏览器搜索IP信息。\n"
            "注意：在线搜索需要网络连接。{ip} 会被替换为实际IP地址。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        # 搜索网址列表管理
        self.search_list = SearchURLListWidget()
        self.search_list.config_modified.connect(self._mark_modified)
        layout.addWidget(self.search_list)

        group.setLayout(layout)

        return group

    def _connect_signals(self):
        """连接信号"""
        # 主开关
        self.enable_check.stateChanged.connect(self._on_enable_changed)

        # 查询策略
        self.strategy_combo.currentTextChanged.connect(self._mark_modified)
        self.concurrent_spin.valueChanged.connect(self._mark_modified)
        self.skip_private_check.stateChanged.connect(self._mark_modified)
        self.skip_special_check.stateChanged.connect(self._mark_modified)
        self.stop_on_success_check.stateChanged.connect(self._mark_modified)

        # 缓存配置
        self.cache_enable_check.stateChanged.connect(self._mark_modified)
        self.ttl_spin.valueChanged.connect(self._mark_modified)
        self.max_size_spin.valueChanged.connect(self._mark_modified)

        # 显示配置
        self.format_combo.currentTextChanged.connect(self._on_format_changed)  # 注意：这里改为 _on_format_changed
        self.custom_format_edit.textChanged.connect(self._mark_modified)
        self.show_isp_check.stateChanged.connect(self._mark_modified)
        self.show_network_check.stateChanged.connect(self._mark_modified)
        self.show_asn_check.stateChanged.connect(self._mark_modified)

        # 搜索配置
        self.search_group.toggled.connect(self._mark_modified)

        # 数据库列表配置变化信号
        if hasattr(self, 'db_list'):
            self.db_list.config_modified.connect(self._mark_modified)

        # 搜索网址列表配置变化信号
        if hasattr(self, 'search_list'):
            self.search_list.config_modified.connect(self._mark_modified)

    def _on_enable_changed(self):
        """启用状态改变"""
        enabled = self.enable_check.isChecked()

        # 启用/禁用所有控件
        widgets_to_toggle = [
            self.db_list.add_btn,
            self.strategy_combo,
            self.concurrent_spin,
            self.skip_private_check,
            self.skip_special_check,
            self.stop_on_success_check,
            self.cache_enable_check,
            self.ttl_spin,
            self.max_size_spin,
            self.format_combo,
            self.show_isp_check,
            self.show_network_check,
            self.show_asn_check,
        ]

        for widget in widgets_to_toggle:
            if widget is not None:
                widget.setEnabled(enabled)

        # 数据库控件
        if hasattr(self, 'db_list'):
            self.db_list.setEnabled(enabled)

        if not self._is_initializing and not self._is_loading_config:
            self._mark_modified()


    def _mark_modified(self):
        """标记配置已修改"""
        if self._is_initializing or self._is_loading_config:
            return

        self._modified = True
        self.config_modified.emit()

    def clear_modified(self):
        """清除修改标记"""
        self._modified = False

    def is_modified(self) -> bool:
        """检查配置是否已修改"""
        return self._modified

    def get_config(self) -> IPGeoConfig:
        """从UI获取IPGeoConfig对象"""
        try:
            # 获取格式字符串
            format_text = self.format_combo.currentText()
            if format_text == "自定义格式":
                format_string = self.custom_format_edit.text()
            else:
                format_string = format_text

            # 离线数据库
            databases = []
            if hasattr(self, 'db_list'):
                databases = self.db_list.get_configs()

            # 获取自定义网址列表
            urls = []
            if hasattr(self, 'search_list'):
                urls = self.search_list.get_configs()

            # 从UI数据创建IPGeoConfig对象
            config_obj = IPGeoConfig(
                # 基础设置
                enabled=self.enable_check.isChecked(),

                # 离线数据库
                databases=databases,

                # 查询配置
                max_concurrent_queries=self.concurrent_spin.value(),
                query_config=QueryStrategyConfig(
                    strategy="parallel" if self.strategy_combo.currentText() == "并行查询" else "sequential",
                    stop_on_first_success=self.stop_on_success_check.isChecked(),
                    skip_private_ips=self.skip_private_check.isChecked(),
                    skip_special_ips=self.skip_special_check.isChecked()
                ),

                # 缓存配置
                cache_config=CacheConfig(
                    enabled=self.cache_enable_check.isChecked(),
                    ttl_seconds=self.ttl_spin.value(),
                    max_size=self.max_size_spin.value()
                ),

                # 显示配置
                display_config=DisplayConfig(
                    format_string=format_string,
                    show_isp=self.show_isp_check.isChecked(),
                    show_asn=self.show_asn_check.isChecked(),
                    show_network=self.show_network_check.isChecked()
                ),

                # 搜索网址
                search_urls=SearchURLConfig(
                    enabled=self.search_group.isChecked(),
                    urls=urls
                ),
            )

            return config_obj

        except Exception as e:
            logger.error(f"获取IP地理信息配置失败: {e}", exc_info=True)
            # 返回默认配置
            return IPGeoConfig()


    def set_config(self, config: IPGeoConfig):
        """设置IPGeoConfig对象"""
        self._is_loading_config = True
        self._modified = False

        try:
            # 清理现有数据库控件
            for widget in self.database_widgets:
                widget.deleteLater()
            self.database_widgets.clear()

            # 1. 基础设置
            self.enable_check.setChecked(config.enabled)

            # 2. 离线数据库
            if hasattr(self, 'db_list'):
                self.db_list.set_configs(config.databases)

            # 3. 查询策略
            if config.query_config.strategy == "parallel":
                self.strategy_combo.setCurrentText("并行查询")
            else:
                self.strategy_combo.setCurrentText("串行查询")

            self.concurrent_spin.setValue(config.max_concurrent_queries)
            self.skip_private_check.setChecked(config.query_config.skip_private_ips)
            self.skip_special_check.setChecked(config.query_config.skip_special_ips)
            self.stop_on_success_check.setChecked(config.query_config.stop_on_first_success)

            # 4. 缓存配置
            self.cache_enable_check.setChecked(config.cache_config.enabled)
            self.ttl_spin.setValue(config.cache_config.ttl_seconds)
            self.max_size_spin.setValue(config.cache_config.max_size)

            # 5. 显示配置
            format_string = config.display_config.format_string

            # 检查格式是否在预设中
            preset_formats = ["{country}", "{country}-{region}", "{country}-{region}-{city}"]
            if format_string in preset_formats:
                self.format_combo.setCurrentText(format_string)
            else:
                self.format_combo.setCurrentText("自定义格式")
                self.custom_format_edit.setText(format_string)

            self.show_isp_check.setChecked(config.display_config.show_isp)
            self.show_network_check.setChecked(config.display_config.show_network)
            self.show_asn_check.setChecked(config.display_config.show_asn)

            # 6. 搜索网址
            self.search_group.setChecked(config.search_urls.enabled)

            # 设置搜索网址列表
            if hasattr(self, 'search_list'):
                self.search_list.set_configs(config.search_urls.urls)

            # 7. 更新UI状态
            self._update_ui_state()

            # 8. 延迟重新连接信号
            # QTimer.singleShot(50, self._reconnect_signals_after_load)

        except Exception as e:
            logger.error(f"设置IP地理信息配置失败: {e}", exc_info=True)
            # 出错时使用默认配置
            try:
                self.set_config(IPGeoConfig())
            except Exception as inner_e:
                logger.error(f"回退到默认配置也失败: {inner_e}")
                # 最终回退：禁用功能
                self.enable_check.setChecked(False)
                self._on_enable_changed()
        finally:
            self._is_loading_config = False


    def _update_ui_state(self):
        """更新UI状态"""
        enabled = self.enable_check.isChecked()

        # 启用/禁用所有控件
        widgets_to_toggle = [
            self.db_list.add_btn,  # 现在引用 db_list 内部的按钮
            self.strategy_combo,
            self.concurrent_spin,
            self.skip_private_check,
            self.skip_special_check,
            self.stop_on_success_check,
            self.cache_enable_check,
            self.ttl_spin,
            self.max_size_spin,
            self.format_combo,
            self.show_isp_check,
            self.show_network_check,
            self.show_asn_check,
        ]

        for widget in widgets_to_toggle:
            widget.setEnabled(enabled)

        # 数据库控件
        for widget in self.database_widgets:
            widget.setEnabled(enabled)

        # 根据格式选择显示/隐藏自定义格式输入框
        if self.format_combo.currentText() == "自定义格式":
            self.custom_format_edit.show()
        else:
            self.custom_format_edit.hide()

    # def _reconnect_signals_after_load(self):
    #     """配置加载完成后重新连接信号"""
    #     # 重新连接主控件信号
    #     self._connect_signals()

    #     # 重新连接数据库控件信号
    #     for widget in self.database_widgets:
    #         if hasattr(widget, '_connect_signals'):
    #             widget._connect_signals()
    #         widget.config_modified.connect(self._mark_modified)

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        if not self.enable_check.isChecked():
            return True, "IP地理位置功能已禁用"

        # 检查数据库配置
        if hasattr(self, 'db_list'):
            configs = self.db_list.get_configs()

            # 检查是否有启用的数据库
            has_enabled_db = any(config.enabled for config in configs)
            if not has_enabled_db:
                return False, "请至少启用一个本地数据库"

            # 检查数据库文件是否存在
            for i, config in enumerate(configs, 1):
                if config.enabled and config.path:
                    if not os.path.exists(config.path):
                        return False, f"第{i}个数据库文件不存在: {config.path}"
                elif config.enabled and not config.path:
                    return False, f"第{i}个数据库未设置文件路径"

        # 检查格式字符串
        format_text = self.format_combo.currentText()
        if format_text == "自定义格式":
            custom_format = self.custom_format_edit.text().strip()
            if not custom_format:
                return False, "自定义格式不能为空"
            if '{country}' not in custom_format:
                return False, "自定义格式必须包含 {country} 占位符"

        # 检查搜索网址
        if self.search_group.isChecked() and hasattr(self, 'search_list'):
            urls = self.search_list.get_configs()
            if not urls:
                return False, "请至少添加一个搜索网址"

            for i, url_info in enumerate(urls, 1):
                if not url_info.get('name', '').strip():
                    return False, f"第{i}个搜索网址名称不能为空"
                if not url_info.get('url', '').strip():
                    return False, f"第{i}个搜索网址URL不能为空"

        return True, "配置验证通过"
