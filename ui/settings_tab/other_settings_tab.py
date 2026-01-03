# -*- coding: utf-8 -*-
"""
Module: other_settings_tab.py
Author: Takeshi
Date: 2025-12-26

Description:
    其他设置页
"""


from typing import Dict, Any, Tuple
import logging

from PySide6.QtWidgets import (
     QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QMessageBox, QGridLayout,
    QCheckBox, QLineEdit, QComboBox, QFileDialog, QListWidget,
    QScrollArea, QGroupBox,
    QInputDialog, QMenu
)
from PySide6.QtCore import Qt, Signal,  QPoint
from PySide6.QtGui import QIntValidator, QAction

from defaults.stats_default import StatsConfig
from defaults.healthcheck_default import HealthCheckConfig

logger = logging.getLogger(__name__)


# ========== "其他配置"标签页 ==========
class OtherSettingsTab(QWidget):
    """其他配置标签页 - 包含统计设置和健康检查"""

    config_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modified = False
        self.init_ui()
        # 初始化UI状态
        self.health_check_changed()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # === 说明部分 ===
        description = QLabel(
            "其他配置：\n"
            "• 连接统计和流量监控设置, 用于统计连接和流量情况\n"
            "• 网络健康检查服务配置，用于检查网络连通性\n"
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
        content_layout.addWidget(description)

        # ========== 第一部分：统计设置 ==========
        stats_group = QGroupBox("连接统计和流量监控")
        stats_group.setStyleSheet("""
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

        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(8)
        stats_layout.setVerticalSpacing(10)

        # 启用统计
        self.enable_stats_check = QCheckBox("启用连接统计和流量监控")
        self.enable_stats_check.stateChanged.connect(self.mark_modified)
        self.enable_stats_check.stateChanged.connect(self.on_stats_check_changed)
        stats_layout.addWidget(self.enable_stats_check, 0, 0, 1, 3)

        # 保存文件路径
        row = 1
        save_file_layout = QHBoxLayout()
        save_file_layout.setSpacing(5)
        save_file_label = QLabel("保存文件:")
        save_file_label.setMinimumWidth(90)
        save_file_layout.addWidget(save_file_label)
        self.save_file_edit = QLineEdit()
        self.save_file_edit.setPlaceholderText("data/stats.json")
        self.save_file_edit.textChanged.connect(self.mark_modified)
        self.save_file_edit.setMinimumWidth(200)
        save_file_layout.addWidget(self.save_file_edit)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_save_file)
        self.browse_btn.setFixedWidth(70)
        save_file_layout.addWidget(self.browse_btn)
        save_file_layout.addStretch()
        stats_layout.addLayout(save_file_layout, row, 0, 1, 3)

        # 保存间隔（秒）
        row += 1
        save_interval_layout = QHBoxLayout()
        save_interval_layout.setSpacing(5)
        save_interval_label = QLabel("保存间隔:")
        save_interval_label.setMinimumWidth(90)
        save_interval_layout.addWidget(save_interval_label)
        self.save_interval_edit = QLineEdit()
        self.save_interval_edit.setValidator(QIntValidator(10, 3600))
        self.save_interval_edit.setPlaceholderText("60")
        self.save_interval_edit.textChanged.connect(self.mark_modified)
        self.save_interval_edit.setFixedWidth(100)
        save_interval_layout.addWidget(self.save_interval_edit)
        save_interval_layout.addWidget(QLabel("秒"))
        save_interval_layout.addStretch()
        stats_layout.addLayout(save_interval_layout, row, 0, 1, 3)

        # 保留天数
        row += 1
        max_days_layout = QHBoxLayout()
        max_days_layout.setSpacing(5)
        max_days_label = QLabel("保留天数:")
        max_days_label.setMinimumWidth(90)
        max_days_layout.addWidget(max_days_label)
        self.max_days_edit = QLineEdit()
        self.max_days_edit.setValidator(QIntValidator(1, 365))
        self.max_days_edit.setPlaceholderText("30")
        self.max_days_edit.textChanged.connect(self.mark_modified)
        self.max_days_edit.setFixedWidth(100)
        max_days_layout.addWidget(self.max_days_edit)
        max_days_layout.addWidget(QLabel("天"))
        max_days_layout.addStretch()
        stats_layout.addLayout(max_days_layout, row, 0, 1, 3)

        # 监控更新间隔（秒）
        row += 1
        update_interval_layout = QHBoxLayout()
        update_interval_layout.setSpacing(5)
        update_interval_label = QLabel("监控更新间隔:")
        update_interval_label.setMinimumWidth(90)
        update_interval_layout.addWidget(update_interval_label)
        self.update_interval_edit = QLineEdit()
        self.update_interval_edit.setValidator(QIntValidator(1, 60))
        self.update_interval_edit.setPlaceholderText("1")
        self.update_interval_edit.textChanged.connect(self.mark_modified)
        self.update_interval_edit.setFixedWidth(100)
        update_interval_layout.addWidget(self.update_interval_edit)
        update_interval_layout.addWidget(QLabel("秒"))
        update_interval_layout.addStretch()
        stats_layout.addLayout(update_interval_layout, row, 0, 1, 3)

        # 历史数据点数
        row += 1
        history_size_layout = QHBoxLayout()
        history_size_layout.setSpacing(5)
        history_size_label = QLabel("历史数据点数:")
        history_size_label.setMinimumWidth(90)
        history_size_layout.addWidget(history_size_label)
        self.history_size_edit = QLineEdit()
        self.history_size_edit.setValidator(QIntValidator(60, 10000))
        self.history_size_edit.setPlaceholderText("300")
        self.history_size_edit.textChanged.connect(self.mark_modified)
        self.history_size_edit.setFixedWidth(100)
        history_size_layout.addWidget(self.history_size_edit)
        history_size_layout.addWidget(QLabel("个点"))
        history_size_layout.addStretch()
        stats_layout.addLayout(history_size_layout, row, 0, 1, 3)

        stats_group.setLayout(stats_layout)
        content_layout.addWidget(stats_group)

        # ========== 第二部分：健康检查设置 ==========
        health_group = QGroupBox("网络健康检查")
        health_group.setStyleSheet("""
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

        health_layout = QGridLayout()
        health_layout.setHorizontalSpacing(8)
        health_layout.setVerticalSpacing(10)

        # 启用健康检查
        self.enable_health_check = QCheckBox("启用自动健康检查")
        self.enable_health_check.stateChanged.connect(self.mark_modified)
        self.enable_health_check.stateChanged.connect(self.health_check_changed)
        health_layout.addWidget(self.enable_health_check, 0, 0, 1, 3)

        # 检查间隔（秒）
        row = 1
        check_interval_layout = QHBoxLayout()
        check_interval_layout.setSpacing(5)
        check_interval_label = QLabel("检查间隔:")
        check_interval_label.setMinimumWidth(90)
        check_interval_layout.addWidget(check_interval_label)
        self.check_interval_edit = QLineEdit()
        self.check_interval_edit.setValidator(QIntValidator(60, 86400))
        self.check_interval_edit.setPlaceholderText("1800")
        self.check_interval_edit.textChanged.connect(self.mark_modified)
        self.check_interval_edit.setFixedWidth(100)
        check_interval_layout.addWidget(self.check_interval_edit)
        check_interval_layout.addWidget(QLabel("秒"))
        check_interval_layout.addStretch()
        health_layout.addLayout(check_interval_layout, row, 0, 1, 3)

        # === 新增：检查策略 ===
        row += 1
        strategy_layout = QHBoxLayout()
        strategy_layout.setSpacing(5)
        strategy_label = QLabel("检查策略:")
        strategy_label.setMinimumWidth(90)
        strategy_layout.addWidget(strategy_label)
        self.check_strategy_combo = QComboBox()
        self.check_strategy_combo.addItem("串行检查", "serial")
        self.check_strategy_combo.addItem("并行检查", "parallel")
        self.check_strategy_combo.currentIndexChanged.connect(self.mark_modified)
        self.check_strategy_combo.currentIndexChanged.connect(self.on_check_strategy_changed)
        self.check_strategy_combo.setFixedWidth(100)
        strategy_layout.addWidget(self.check_strategy_combo)
        strategy_layout.addStretch()
        health_layout.addLayout(strategy_layout, row, 0, 1, 3)

        # === 新增：并行池大小 ===
        row += 1
        pool_size_layout = QHBoxLayout()
        pool_size_layout.setSpacing(5)
        pool_size_label = QLabel("并行池大小:")
        pool_size_label.setMinimumWidth(90)
        pool_size_layout.addWidget(pool_size_label)
        self.parallel_pool_edit = QLineEdit()
        self.parallel_pool_edit.setValidator(QIntValidator(1, 10))
        self.parallel_pool_edit.setPlaceholderText("3")
        self.parallel_pool_edit.textChanged.connect(self.mark_modified)
        self.parallel_pool_edit.setFixedWidth(100)
        pool_size_layout.addWidget(self.parallel_pool_edit)
        pool_size_layout.addWidget(QLabel("个线程"))
        pool_size_layout.addStretch()
        health_layout.addLayout(pool_size_layout, row, 0, 1, 3)

        # 网络超时
        row += 1
        check_timeout_layout = QHBoxLayout()
        check_timeout_layout.setSpacing(5)
        check_timeout_label = QLabel("网络超时:")
        check_timeout_label.setMinimumWidth(90)
        check_timeout_layout.addWidget(check_timeout_label)
        self.check_timeout_edit = QLineEdit()
        self.check_timeout_edit.setValidator(QIntValidator(1, 30))
        self.check_timeout_edit.setPlaceholderText("5")
        self.check_timeout_edit.textChanged.connect(self.mark_modified)
        self.check_timeout_edit.setFixedWidth(100)
        check_timeout_layout.addWidget(self.check_timeout_edit)
        check_timeout_layout.addWidget(QLabel("秒"))
        check_timeout_layout.addStretch()
        health_layout.addLayout(check_timeout_layout, row, 0, 1, 3)

        # 检查服务列表区域
        row += 1
        services_hbox = QHBoxLayout()
        services_hbox.setSpacing(5)

        # 标签
        services_label = QLabel("检查服务器:")
        services_label.setMinimumWidth(90)
        services_hbox.addWidget(services_label)

        # 服务列表和按钮
        services_widget = QWidget()
        services_layout = QVBoxLayout(services_widget)
        services_layout.setSpacing(5)
        services_layout.setContentsMargins(0, 0, 0, 0)

        # 服务列表
        self.services_list = QListWidget()
        self.services_list.setMinimumHeight(100)
        self.services_list.setMaximumHeight(150)
        self.services_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.services_list.customContextMenuRequested.connect(self.show_context_menu)
        self.services_list.doubleClicked.connect(self.edit_service_item)
        services_layout.addWidget(self.services_list)

        # 添加/删除/编辑服务的按钮
        services_btn_layout = QHBoxLayout()
        services_btn_layout.setSpacing(5)
        self.add_service_btn = QPushButton("添加")
        self.add_service_btn.clicked.connect(self.add_check_service)
        self.add_service_btn.setFixedWidth(70)
        self.edit_service_btn = QPushButton("编辑")
        self.edit_service_btn.clicked.connect(self.edit_service_item)
        self.edit_service_btn.setFixedWidth(70)
        self.remove_service_btn = QPushButton("删除")
        self.remove_service_btn.clicked.connect(self.remove_check_service)
        self.remove_service_btn.setFixedWidth(70)
        services_btn_layout.addWidget(self.add_service_btn)
        services_btn_layout.addWidget(self.edit_service_btn)
        services_btn_layout.addWidget(self.remove_service_btn)
        services_btn_layout.addStretch()
        services_layout.addLayout(services_btn_layout)

        services_hbox.addWidget(services_widget)
        services_hbox.addStretch()
        health_layout.addLayout(services_hbox, row, 0, 1, 3)

        # 添加服务示例按钮
        row += 1
        self.example_btn = QPushButton("添加示例服务")
        self.example_btn.clicked.connect(self.add_example_services)
        self.example_btn.setFixedWidth(100)
        example_btn_layout = QHBoxLayout()
        example_btn_layout.addWidget(self.example_btn)
        example_btn_layout.addStretch()
        health_layout.addLayout(example_btn_layout, row, 0, 1, 3)

        health_group.setLayout(health_layout)
        content_layout.addWidget(health_group)

        content_layout.addStretch()

        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def show_context_menu(self, position: QPoint):
        """显示右键菜单"""
        menu = QMenu()

        # 添加动作
        edit_action = QAction("编辑", self)
        edit_action.triggered.connect(self.edit_service_item)
        menu.addAction(edit_action)

        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self.remove_check_service)
        menu.addAction(delete_action)

        menu.addSeparator()

        add_action = QAction("添加新服务", self)
        add_action.triggered.connect(self.add_check_service)
        menu.addAction(add_action)

        # 显示菜单
        menu.exec(self.services_list.mapToGlobal(position))

    def edit_service_item(self):
        """编辑选中的服务"""
        current_item = self.services_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个要编辑的服务")
            return

        old_text = current_item.text()
        text, ok = QInputDialog.getText(
            self, "编辑检查服务",
            "请输入新的URL地址:",
            text=old_text
        )

        if ok and text:
            if text.strip():
                current_item.setText(text.strip())
                self.mark_modified()
            else:
                QMessageBox.warning(self, "警告", "URL地址不能为空")

    def on_stats_check_changed(self):
        enabled = self.enable_stats_check.isChecked()

        self.save_file_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.save_interval_edit.setEnabled(enabled)
        self.max_days_edit.setEnabled(enabled)
        self.update_interval_edit.setEnabled(enabled)
        self.history_size_edit.setEnabled(enabled)

    def health_check_changed(self):
        """健康检查启用状态改变 - 只控制检查间隔和检查策略"""
        enabled = self.enable_health_check.isChecked()

        # 只有检查间隔和检查策略受启用状态控制
        self.check_interval_edit.setEnabled(enabled)
        self.check_strategy_combo.setEnabled(enabled)

        # 以下控件始终保持可用，不受启用状态影响：
        # - 并行池大小 (self.parallel_pool_edit)
        # - 网络超时 (self.check_timeout_edit)
        # - 服务器列表和所有相关按钮
        # 注意：这些控件默认就是启用的，不需要特别设置

    def on_check_strategy_changed(self):
        """检查策略改变时的处理"""
        # 只有检查策略改变时标记修改，不控制其他控件的启用状态
        self.mark_modified()

    def browse_save_file(self):
        """浏览保存文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择统计文件保存位置",
            self.save_file_edit.text() or "data/stats.json",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        if file_path:
            self.save_file_edit.setText(file_path)
            self.mark_modified()

    def add_check_service(self):
        """添加检查服务"""
        text, ok = QInputDialog.getText(
            self, "添加检查服务",
            "请输入要检查的URL地址:",
            text="https://www.baidu.com/"
        )
        if ok and text:
            if text.strip():
                self.services_list.addItem(text.strip())
                self.mark_modified()
            else:
                QMessageBox.warning(self, "警告", "URL地址不能为空")

    def remove_check_service(self):
        """删除选中的检查服务"""
        current_item = self.services_list.currentItem()
        if current_item:
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除服务 '{current_item.text()}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.services_list.takeItem(self.services_list.row(current_item))
                self.mark_modified()

    def add_example_services(self):
        """添加示例服务"""
        from defaults.ui_default import HEALTHCHECK_SERVICES
        example_services = HEALTHCHECK_SERVICES

        added_count = 0
        for service in example_services:
            # 检查是否已存在
            exists = False
            for i in range(self.services_list.count()):
                if service == self.services_list.item(i).text():
                    exists = True
                    break

            if not exists:
                self.services_list.addItem(service)
                added_count += 1

        if added_count > 0:
            self.mark_modified()
            QMessageBox.information(self, "添加完成", f"已添加 {added_count} 个示例服务")

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

    # ========== 配置获取和设置方法 ==========

    def get_config(self) -> Dict[str, Any]:
        """获取配置 - 返回包含两个dataclass对象的字典"""
        try:
            # 创建StatsConfig对象
            stats_config = StatsConfig(
                enable_stats=self.enable_stats_check.isChecked(),
                save_file=self.save_file_edit.text().strip() or 'data/stats.json',
                save_interval=int(self.save_interval_edit.text()) if self.save_interval_edit.text() else 60,
                max_days=int(self.max_days_edit.text()) if self.max_days_edit.text() else 30,
                update_interval=int(self.update_interval_edit.text()) if self.update_interval_edit.text() else 1,
                history_size=int(self.history_size_edit.text()) if self.history_size_edit.text() else 300
            )

            # 创建HealthCheckConfig对象
            health_services = []
            for i in range(self.services_list.count()):
                service = self.services_list.item(i).text().strip()
                if service:
                    health_services.append(service)

            health_config = HealthCheckConfig(
                enabled=self.enable_health_check.isChecked(),
                check_interval=int(self.check_interval_edit.text()) if self.check_interval_edit.text() else 1800,
                check_services=health_services if health_services else [],
                check_timeout=int(self.check_timeout_edit.text()) if self.check_timeout_edit.text() else 5,
                check_strategy=self.check_strategy_combo.currentData() or 'serial',
                parallel_pool_size=int(self.parallel_pool_edit.text()) if self.parallel_pool_edit.text() else 3
            )

            # 返回包含dataclass对象的字典
            return {
                'STATS_CONFIG': stats_config,
                'HEALTH_CHECK_CONFIG': health_config
            }

        except Exception as e:
            logger.error(f"获取其他配置失败: {e}", exc_info=True)
            # 返回默认配置
            return {
                'STATS_CONFIG': StatsConfig(),
                'HEALTH_CHECK_CONFIG': HealthCheckConfig()
            }

    def set_config(self, config: Dict[str, Any]):
        """设置配置 - 接受包含dataclass对象的字典"""
        try:
            # 阻塞信号
            self.blockSignals(True)

            # 处理统计配置
            stats_config = config.get('STATS_CONFIG')

            # 如果stats_config不是StatsConfig对象，尝试创建它
            if not isinstance(stats_config, StatsConfig):
                if isinstance(stats_config, dict):
                    # 从字典创建StatsConfig
                    stats_config = StatsConfig(**stats_config)
                else:
                    # 使用默认配置
                    stats_config = StatsConfig()

            # 设置统计配置
            self.enable_stats_check.setChecked(stats_config.enable_stats)
            self.save_file_edit.setText(stats_config.save_file)
            self.save_interval_edit.setText(str(stats_config.save_interval))
            self.max_days_edit.setText(str(stats_config.max_days))
            self.update_interval_edit.setText(str(stats_config.update_interval))
            self.history_size_edit.setText(str(stats_config.history_size))

            # 更新UI状态
            stats_enabled = self.enable_stats_check.isChecked()
            self.save_file_edit.setEnabled(stats_enabled)
            self.browse_btn.setEnabled(stats_enabled)
            self.save_interval_edit.setEnabled(stats_enabled)
            self.max_days_edit.setEnabled(stats_enabled)
            self.update_interval_edit.setEnabled(stats_enabled)
            self.history_size_edit.setEnabled(stats_enabled)

            # 处理健康检查配置
            health_config = config.get('HEALTH_CHECK_CONFIG')

            # 如果health_config不是HealthCheckConfig对象，尝试创建它
            if not isinstance(health_config, HealthCheckConfig):
                if isinstance(health_config, dict):
                    # 从字典创建HealthCheckConfig
                    health_config = HealthCheckConfig(**health_config)
                else:
                    # 使用默认配置
                    health_config = HealthCheckConfig()

            # 设置健康检查配置
            self.enable_health_check.setChecked(health_config.enabled)
            self.check_interval_edit.setText(str(health_config.check_interval))
            self.check_timeout_edit.setText(str(health_config.check_timeout))

            # 设置新增的配置项
            # 检查策略
            strategy = getattr(health_config, 'check_strategy', 'serial')
            index = self.check_strategy_combo.findData(strategy)
            if index >= 0:
                self.check_strategy_combo.setCurrentIndex(index)
            else:
                self.check_strategy_combo.setCurrentIndex(0)  # 默认串行

            # 并行池大小
            pool_size = getattr(health_config, 'parallel_pool_size', 3)
            self.parallel_pool_edit.setText(str(pool_size))

            # 清空并设置服务列表
            self.services_list.clear()

            # 安全地处理check_services
            check_services = health_config.check_services
            if check_services is not None:
                try:
                    # 尝试迭代
                    for service in check_services:
                        if isinstance(service, str):
                            self.services_list.addItem(service.strip())
                        else:
                            # 如果不是字符串，转换为字符串
                            self.services_list.addItem(str(service))
                except TypeError:
                    # 如果不能迭代，使用默认服务
                    logger.warning(f"check_services不可迭代，使用默认值: {check_services}")

            # 更新UI状态 - 调用health_check_changed来设置正确的启用状态
            self.health_check_changed()

            self._modified = False

        except Exception as e:
            logger.error(f"设置其他配置失败: {e}", exc_info=True)
            # 出错时使用最小配置
        finally:
            self.blockSignals(False)

    def validate_config(self) -> Tuple[bool, str]:
        """验证配置"""
        # 验证保存间隔
        save_interval = self.save_interval_edit.text()
        if save_interval:
            try:
                interval = int(save_interval)
                if interval < 10 or interval > 3600:
                    return False, "保存间隔应在10-3600秒之间"
            except ValueError:
                return False, "保存间隔必须是数字"

        # 验证保留天数
        max_days = self.max_days_edit.text()
        if max_days:
            try:
                days = int(max_days)
                if days < 1 or days > 365:
                    return False, "保留天数应在1-365天之间"
            except ValueError:
                return False, "保留天数必须是数字"

        # 验证监控更新间隔
        update_interval = self.update_interval_edit.text()
        if update_interval:
            try:
                interval = int(update_interval)
                if interval < 1 or interval > 60:
                    return False, "监控更新间隔应在1-60秒之间"
            except ValueError:
                return False, "监控更新间隔必须是数字"

        # 验证历史数据点数
        history_size = self.history_size_edit.text()
        if history_size:
            try:
                size = int(history_size)
                if size < 60 or size > 10000:
                    return False, "历史数据点数应在60-10000之间"
            except ValueError:
                return False, "历史数据点数必须是数字"

        # 验证健康检查配置
        if self.enable_health_check.isChecked():
            # 验证健康检查间隔
            check_interval = self.check_interval_edit.text()
            if check_interval:
                try:
                    interval = int(check_interval)
                    if interval < 60 or interval > 86400:
                        return False, "健康检查间隔应在60-86400秒之间"
                except ValueError:
                    return False, "健康检查间隔必须是数字"

        # 验证网络超时时间（始终验证，不受启用状态影响）
        timeout = self.check_timeout_edit.text()
        if timeout:
            try:
                t = int(timeout)
                if t < 1 or t > 30:
                    return False, "网络超时时间应在1-30秒之间"
            except ValueError:
                return False, "网络超时时间必须是数字"

        # 验证并行池大小（如果启用并行检查）
        if self.check_strategy_combo.currentData() == "parallel":
            pool_size = self.parallel_pool_edit.text()
            if pool_size:
                try:
                    size = int(pool_size)
                    if size < 1 or size > 10:
                        return False, "并行池大小应在1-10之间"
                except ValueError:
                    return False, "并行池大小必须是数字"

        # 验证至少有一个检查服务（如果启用了健康检查）
        if self.enable_health_check.isChecked() and self.services_list.count() == 0:
            return False, "请至少添加一个健康检查服务"

        return True, "配置验证通过"
