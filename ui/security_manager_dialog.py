# -*- coding: utf-8 -*-
"""
Module: security_manager_dialog.py
Author: Takeshi
Date: 2025-11-25

Description:
    安全管理对话框
"""

import logging
import time
from typing import List, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QLabel, QMessageBox, QHeaderView,
    QWidget, QAbstractItemView, QToolTip
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QStandardItemModel, QFont, QColor, QCursor, QIcon

from .ip_detail_dialog import IPDetailDialog
from .ban_history_dialog import BanHistoryDialog

logger = logging.getLogger(__name__)

from defaults.ui_default import (SECURITY_MANAGER_WINDOW_SIZE,
                                 SECURITY_MANAGER_WINDOW_REFRESH_INTERVAL,
                                 DIALOG_ICOINS
                                 )

class SecurityManagerDialog(QDialog):
    """安全管理主对话框"""

    def __init__(self, security_manager, ip_geo_manger, signals, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.ip_geo_manager = ip_geo_manger
        self.setup_ui()
        self.load_data()
        self.signals = signals
        from defaults.user_default import USER_CONFIG_FILE
        self.config_file = USER_CONFIG_FILE

        # 设置定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_data)
        self.refresh_timer.start(SECURITY_MANAGER_WINDOW_REFRESH_INTERVAL)

    def show_ip_detail(self, ip: str):
        """显示IP详情对话框"""
        dialog = IPDetailDialog(ip, self.ip_geo_manager, self)
        dialog.exec()

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("BindInterfaceProxy - 安全管理")
        self.resize(*SECURITY_MANAGER_WINDOW_SIZE) # 使用可变大小

        self.setModal(False)

        # 启用对话框的最小化和最大化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        layout = QVBoxLayout(self)

        # 创建标签页 - 按新顺序：临时封禁、黑名单、白名单
        self.tab_widget = QTabWidget()

        # 简单设置标签页颜色，保持原有样式
        self.tab_widget.setStyleSheet("""
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: white;
            }
            QTabBar::tab:!selected {
                background-color: #F0F0F0;
                color: #666666;
            }
        """)

        # 临时封禁标签页
        self.temp_ban_tab = TempBanManagerTab(self.security_manager, self.ip_geo_manager)
        self.tab_widget.addTab(self.temp_ban_tab, "临时封禁")

        # 黑名单标签页
        self.blacklist_tab = BlacklistManagerTab(self.security_manager, self.ip_geo_manager)
        self.tab_widget.addTab(self.blacklist_tab, "黑名单")

        # 白名单标签页
        self.whitelist_tab = WhitelistManagerTab(self.security_manager, self.ip_geo_manager)
        self.tab_widget.addTab(self.whitelist_tab, "白名单")

        layout.addWidget(self.tab_widget)

        # 底部按钮 - 重新布局
        button_layout = QHBoxLayout()

        # 左边：模式切换按钮
        mode_layout = QHBoxLayout()

        self.mixed_mode_btn = QPushButton("混合模式")
        self.mixed_mode_btn.setCheckable(True)
        self.mixed_mode_btn.clicked.connect(lambda: self.set_security_mode('mixed'))
        mode_layout.addWidget(self.mixed_mode_btn)

        self.blacklist_mode_btn = QPushButton("黑名单模式")
        self.blacklist_mode_btn.setCheckable(True)
        self.blacklist_mode_btn.clicked.connect(lambda: self.set_security_mode('blacklist'))
        mode_layout.addWidget(self.blacklist_mode_btn)

        self.whitelist_mode_btn = QPushButton("白名单模式")
        self.whitelist_mode_btn.setCheckable(True)
        self.whitelist_mode_btn.clicked.connect(lambda: self.set_security_mode('whitelist'))
        mode_layout.addWidget(self.whitelist_mode_btn)

        # 更新按钮状态
        self.update_mode_buttons()

        button_layout.addLayout(mode_layout)
        button_layout.addStretch()  # 中间弹性空间

        # 右边：刷新和关闭按钮
        right_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_data)
        right_layout.addWidget(self.refresh_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        right_layout.addWidget(self.close_btn)

        button_layout.addLayout(right_layout)

        layout.addLayout(button_layout)

    def set_security_mode(self, mode: str):
        """设置安全模式并保存到配置文件"""
        if not self.security_manager:
            QMessageBox.warning(self, "错误", "安全管理器未初始化")
            return

        try:
            # 更新内存中的配置
            self.security_manager.config.core.mode = mode

            # 保存到配置文件
            self._save_security_mode_to_config(mode)

            # 更新按钮状态
            self.update_mode_buttons()

            mode_names = {
                'mixed': '混合模式',
                'blacklist': '黑名单模式',
                'whitelist': '白名单模式'
            }

            QMessageBox.information(self, "成功", f"已切换到 {mode_names.get(mode, mode)}")
            logger.info(f"安全模式已切换为: {mode}")
            self.signals.security_changed.emit(f"{mode}")

        except Exception as e:
            logger.error(f"切换安全模式失败: {e}")
            QMessageBox.warning(self, "错误", f"切换模式失败: {e}")

    def _save_security_mode_to_config(self, mode: str):
        """将安全模式保存到配置文件"""
        if not self.config_file:
            logger.warning("未指定配置文件路径，无法保存安全模式设置")
            return False

        try:
            import json
            from pathlib import Path

            config_path = Path(self.config_file)

            # 确保配置文件存在
            if not config_path.exists():
                logger.error(f"配置文件不存在: {config_path}")
                return False

            # 读取现有配置
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 更新安全模式配置
            if 'SECURITY_MANAGER_CONFIG' in config_data:
                if 'core' in config_data['SECURITY_MANAGER_CONFIG']:
                    config_data['SECURITY_MANAGER_CONFIG']['core']['mode'] = mode
                else:
                    # 如果core不存在，创建它
                    config_data['SECURITY_MANAGER_CONFIG']['core'] = {'mode': mode}
            else:
                # 如果SECURITY_MANAGER_CONFIG不存在，创建完整结构
                config_data['SECURITY_MANAGER_CONFIG'] = {
                    'core': {
                        'mode': mode,
                        'blacklist_file': 'data/blacklist.json',
                        'whitelist_file': 'data/whitelist.json',
                        'temp_bans_file': 'data/temp_bans.json',
                        'cleanup_interval': 360,
                        'keep_ban_history': True,
                        'max_history_size': 1000
                    }
                }

            # 保存回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            logger.info(f"已将安全模式 '{mode}' 保存到配置文件: {config_path}")
            return True

        except Exception as e:
            logger.error(f"保存安全模式到配置文件失败: {e}")
            return False

    def update_mode_buttons(self):
        """更新模式按钮的选中状态"""
        if not self.security_manager:
            return

        current_mode = self.security_manager.config.core.mode

        # 重置所有按钮状态
        self.mixed_mode_btn.setChecked(False)
        self.blacklist_mode_btn.setChecked(False)
        self.whitelist_mode_btn.setChecked(False)

        # 设置当前模式的按钮为选中状态
        if current_mode == 'mixed':
            self.mixed_mode_btn.setChecked(True)
            self.mixed_mode_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        elif current_mode == 'blacklist':
            self.blacklist_mode_btn.setChecked(True)
            self.blacklist_mode_btn.setStyleSheet("background-color: #F44336; color: white;")
        elif current_mode == 'whitelist':
            self.whitelist_mode_btn.setChecked(True)
            self.whitelist_mode_btn.setStyleSheet("background-color: #2196F3; color: white;")

        # 设置未选中按钮的默认样式
        default_style = "background-color: #F0F0F0; color: #666666;"
        if not self.mixed_mode_btn.isChecked():
            self.mixed_mode_btn.setStyleSheet(default_style)
        if not self.blacklist_mode_btn.isChecked():
            self.blacklist_mode_btn.setStyleSheet(default_style)
        if not self.whitelist_mode_btn.isChecked():
            self.whitelist_mode_btn.setStyleSheet(default_style)

    def load_data(self):
        """加载所有数据"""
        try:
            self.whitelist_tab.load_data()
            self.blacklist_tab.load_data()
            self.temp_ban_tab.load_data()

            # 更新标签页标题显示条目数
            whitelist_count = len(self.whitelist_tab.get_entries())
            blacklist_count = len(self.blacklist_tab.get_entries())
            temp_ban_count = len(self.temp_ban_tab.get_entries())

            self.tab_widget.setTabText(0, f"临时封禁({temp_ban_count})")
            self.tab_widget.setTabText(1, f"黑名单({blacklist_count})")
            self.tab_widget.setTabText(2, f"白名单({whitelist_count})")

            # 更新模式按钮状态
            self.update_mode_buttons()

        except Exception as e:
            logger.error(f"加载安全数据失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().closeEvent(event)


class WhitelistManagerTab(QWidget):
    """白名单管理标签页"""

    def __init__(self, security_manager, ip_geo_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.ip_geo_manager = ip_geo_manager
        self.setup_ui()
        # 初始化排序状态
        self.sort_column = 0
        self.sort_order = Qt.AscendingOrder

    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)

        # 添加白名单区域
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("IP/IP段:"))

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("支持格式: 192.168.1.1, 192.168.1.0/24, 192.168.1.1-192.168.1.100")
        add_layout.addWidget(self.ip_input)

        add_layout.addWidget(QLabel("备注:"))

        self.remark_input = QLineEdit()
        self.remark_input.setPlaceholderText("可选，描述此IP的用途")
        add_layout.addWidget(self.remark_input)

        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.add_entry)
        add_layout.addWidget(self.add_btn)

        layout.addLayout(add_layout)

        # 白名单表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["IP/IP段", "备注", "创建时间", "操作来源", "操作", "IP详情"])

        # 禁用选中高亮
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)

        # 设置列宽策略
        header = self.table.horizontalHeader()

        # 设置每列的调整策略
        # 第0列（IP）：初始拉伸，可拖动调整
        header.setSectionResizeMode(0, QHeaderView.Interactive)

        # 第1列（备注）：初始拉伸，可拖动调整
        header.setSectionResizeMode(1, QHeaderView.Interactive)

        # 第2列（创建时间）：根据内容调整，可拖动调整
        header.setSectionResizeMode(2, QHeaderView.Interactive)

        # 第3列（操作来源）：根据内容调整，可拖动调整
        header.setSectionResizeMode(3, QHeaderView.Interactive)

        # 第4列（操作）：固定宽度
        header.setSectionResizeMode(4, QHeaderView.Fixed)

        # 第5列（IP详情）：固定宽度
        header.setSectionResizeMode(5, QHeaderView.Fixed)

        # 设置初始宽度（根据窗口大小动态调整）
        self.set_initial_column_widths()

        # 启用排序功能
        self.table.setSortingEnabled(True)

        # 连接表头点击事件
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)

        # 设置表格样式
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f8f9fa;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #e0e0e0;
            }
            QTableWidget::item:hover {
                background-color: #f5f5f5;
            }
            QHeaderView::section {
                background-color: #f1f3f4;
                padding: 8px 5px;
                border: 1px solid #dadce0;
                font-weight: bold;
                font-size: 12px;
            }
            QHeaderView::section:active {
                background-color: #e0e0e0;
            }
            QTableCornerButton::section {
                background-color: #f1f3f4;
                border: 1px solid #dadce0;
            }
        """)

        layout.addWidget(self.table)

        # 说明文本
        help_text = QLabel("""支持格式: 单个IP: 192.168.1.1
                CIDR网段: 192.168.1.0/24
                IP范围: 192.168.1.1-192.168.1.100""")
        help_text.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(help_text)

    def set_initial_column_widths(self):
        """设置初始列宽"""
        # 获取表格宽度
        table_width = self.table.width()

        # 为固定列预留宽度
        fixed_width = 70 + 80  # 操作列 + IP详情列

        # 剩余宽度分配给其他列
        remaining_width = table_width - fixed_width - 50  # 减去一些边距

        # 计算其他列的初始宽度
        ip_width = int(remaining_width * 0.25)  # IP列占25%
        remark_width = int(remaining_width * 0.30)  # 备注列占30%
        time_width = int(remaining_width * 0.30)  # 时间列占30%
        source_width = remaining_width - ip_width - remark_width - time_width  # 剩余给来源列

        # 设置宽度
        self.table.setColumnWidth(0, max(100, ip_width))
        self.table.setColumnWidth(1, max(100, remark_width))
        self.table.setColumnWidth(2, max(120, time_width))
        self.table.setColumnWidth(3, max(100, source_width))
        self.table.setColumnWidth(4, 70)  # 操作列
        self.table.setColumnWidth(5, 80)  # IP详情列

    def resizeEvent(self, event):
        """窗口大小改变时重新调整列宽"""
        super().resizeEvent(event)
        if hasattr(self, 'table') and self.table.rowCount() > 0:
            QTimer.singleShot(50, self.set_initial_column_widths)

    def on_header_clicked(self, column):
        """表头点击事件处理"""
        if column in [0, 1, 2, 3]:  # 只对IP、备注、创建时间、操作来源列进行排序
            if self.sort_column == column:
                # 点击同一列，切换排序顺序
                self.sort_order = Qt.DescendingOrder if self.sort_order == Qt.AscendingOrder else Qt.AscendingOrder
            else:
                # 点击不同列，默认升序
                self.sort_order = Qt.AscendingOrder
                self.sort_column = column

            # 执行排序
            self.table.sortItems(column, self.sort_order)

    def load_data(self):
        """加载白名单数据"""
        try:
            entries = self.get_entries()

            # 先禁用排序，防止在填充数据时自动排序
            self.table.setSortingEnabled(False)

            # 保存当前滚动位置
            scroll_value = self.table.verticalScrollBar().value()

            self.table.setRowCount(len(entries))

            for row, entry in enumerate(entries):
                ip_spec = entry['ip']

                # IP条目
                ip_item = QTableWidgetItem(ip_spec)
                ip_item.setFlags(ip_item.flags() & ~Qt.ItemIsEditable)
                ip_item.setFlags(ip_item.flags() | Qt.ItemIsEnabled)
                ip_item.setToolTip(ip_spec)  # 添加提示，鼠标悬停显示完整IP
                self.table.setItem(row, 0, ip_item)

                # 备注
                remark = entry.get('remark', '')
                remark_item = QTableWidgetItem(remark)
                remark_item.setFlags(remark_item.flags() & ~Qt.ItemIsEditable)
                remark_item.setFlags(remark_item.flags() | Qt.ItemIsEnabled)
                if remark:
                    remark_item.setToolTip(remark)  # 添加提示
                self.table.setItem(row, 1, remark_item)

                # 创建时间 - 完整显示
                created_at = entry.get('created_at', '')
                if created_at:
                    try:
                        # 尝试解析和格式化时间
                        if 'T' in created_at:
                            date_part = created_at.split('T')[0]
                            time_part = created_at.split('T')[1].split('.')[0]
                            if len(time_part) > 8:
                                time_part = time_part[:8]
                            created_str = f"{date_part} {time_part}"
                        else:
                            created_str = created_at[:19] if len(created_at) >= 19 else created_at
                    except:
                        created_str = created_at[:19] if len(created_at) >= 19 else created_at
                else:
                    created_str = "未知"

                time_item = QTableWidgetItem(created_str)
                time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
                time_item.setFlags(time_item.flags() | Qt.ItemIsEnabled)
                # 设置一个隐藏的数据用于排序
                time_item.setData(Qt.UserRole, created_at)  # 存储原始时间字符串用于排序
                self.table.setItem(row, 2, time_item)

                # 操作来源
                created_by = entry.get('created_by', '')
                if self.security_manager and hasattr(self.security_manager, 'get_entry_display_info'):
                    display_info = self.security_manager.get_entry_display_info(entry)
                    source_display = display_info.get('created_by_display', created_by)
                else:
                    source_display = created_by

                source_item = QTableWidgetItem(source_display)
                source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                source_item.setFlags(source_item.flags() | Qt.ItemIsEnabled)
                source_item.setToolTip(source_display)  # 添加提示
                self.table.setItem(row, 3, source_item)

                # 删除按钮
                delete_btn = QPushButton("删除")
                delete_btn.setStyleSheet("""
                    QPushButton {
                        padding: 3px 8px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #c82333;
                    }
                """)
                delete_btn.clicked.connect(lambda checked, ip=ip_spec: self.delete_entry(ip))
                self.table.setCellWidget(row, 4, delete_btn)

                # IP详情按钮
                detail_btn = QPushButton("IP详情")
                detail_btn.setStyleSheet("""
                    QPushButton {
                        padding: 3px 8px;
                        background: #17a2b8;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #138496;
                    }
                """)
                detail_btn.clicked.connect(lambda checked, ip=ip_spec: self.show_ip_detail(ip))
                self.table.setCellWidget(row, 5, detail_btn)

            # 恢复滚动位置
            self.table.verticalScrollBar().setValue(scroll_value)

            # 重新启用排序
            self.table.setSortingEnabled(True)

            # 如果之前有排序状态，恢复排序
            if hasattr(self, 'sort_column'):
                self.table.sortItems(self.sort_column, self.sort_order)

        except Exception as e:
            logger.error(f"加载白名单失败: {e}")

    def get_entries(self) -> List[Dict]:
        """获取白名单条目"""
        if self.security_manager:
            return self.security_manager.get_whitelist_entries()
        return []

    def add_entry(self):
        """添加白名单条目"""
        ip_spec = self.ip_input.text().strip()
        remark = self.remark_input.text().strip()

        if not ip_spec:
            QMessageBox.warning(self, "输入错误", "请输入IP或IP段")
            return

        if not self.security_manager:
            QMessageBox.warning(self, "错误", "安全管理器未初始化")
            return

        if self.security_manager.add_to_whitelist(ip_spec, remark, "user"):
            QMessageBox.information(self, "成功", f"已添加到白名单: {ip_spec}")
            self.ip_input.clear()
            self.remark_input.clear()
            self.load_data()
        else:
            QMessageBox.warning(self, "添加失败", "IP格式无效或已存在")

    def delete_entry(self, ip_spec: str):
        """删除白名单条目"""
        reply = QMessageBox.question(self, "确认删除",
                                   f"确定要从白名单中删除 {ip_spec} 吗？")
        if reply == QMessageBox.Yes:
            if self.security_manager:
                if self.security_manager.remove_from_whitelist(ip_spec):
                    QMessageBox.information(self, "成功", f"已从白名单删除: {ip_spec}")
                    self.load_data()
                else:
                    QMessageBox.warning(self, "删除失败", "删除失败，条目可能不存在")

    def show_ip_detail(self, ip: str):
        """显示IP详情对话框"""
        dialog = IPDetailDialog(ip, self.ip_geo_manager, self)
        dialog.exec()


class BlacklistManagerTab(QWidget):
    """黑名单管理标签页"""

    def __init__(self, security_manager, ip_geo_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.ip_geo_manager = ip_geo_manager
        self.sort_column = 0
        self.sort_order = Qt.AscendingOrder
        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)

        # 添加黑名单区域
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("IP/IP段:"))

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("支持格式: 192.168.1.1, 192.168.1.0/24, 192.168.1.1-192.168.1.100")
        add_layout.addWidget(self.ip_input)

        add_layout.addWidget(QLabel("备注:"))

        self.remark_input = QLineEdit()
        self.remark_input.setPlaceholderText("可选，描述封禁原因")
        add_layout.addWidget(self.remark_input)

        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.add_entry)
        add_layout.addWidget(self.add_btn)

        layout.addLayout(add_layout)

        # 黑名单表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["IP/IP段", "备注", "创建时间", "操作来源", "操作", "IP详情"])

        # 禁用选中高亮
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)

        # 设置列宽策略
        header = self.table.horizontalHeader()

        # 设置每列的调整策略
        # 第0列（IP）：初始拉伸，可拖动调整
        header.setSectionResizeMode(0, QHeaderView.Interactive)

        # 第1列（备注）：初始拉伸，可拖动调整
        header.setSectionResizeMode(1, QHeaderView.Interactive)

        # 第2列（创建时间）：根据内容调整，可拖动调整
        header.setSectionResizeMode(2, QHeaderView.Interactive)

        # 第3列（操作来源）：根据内容调整，可拖动调整
        header.setSectionResizeMode(3, QHeaderView.Interactive)

        # 第4列（操作）：固定宽度
        header.setSectionResizeMode(4, QHeaderView.Fixed)

        # 第5列（IP详情）：固定宽度
        header.setSectionResizeMode(5, QHeaderView.Fixed)

        # 设置初始宽度（根据窗口大小动态调整）
        self.set_initial_column_widths()

        # 启用排序功能
        self.table.setSortingEnabled(True)

        # 连接表头点击事件
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)

        # 设置表格样式
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f8f9fa;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #e0e0e0;
            }
            QTableWidget::item:hover {
                background-color: #f5f5f5;
            }
            QHeaderView::section {
                background-color: #f1f3f4;
                padding: 8px 5px;
                border: 1px solid #dadce0;
                font-weight: bold;
                font-size: 12px;
            }
            QHeaderView::section:active {
                background-color: #e0e0e0;
            }
            QTableCornerButton::section {
                background-color: #f1f3f4;
                border: 1px solid #dadce0;
            }
        """)

        layout.addWidget(self.table)

        # 说明文本
        help_text = QLabel("""支持格式: 单个IP: 192.168.1.1
                CIDR网段: 192.168.1.0/24
                IP范围: 192.168.1.1-192.168.1.100""")
        help_text.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(help_text)

    def set_initial_column_widths(self):
        """设置初始列宽"""
        # 获取表格宽度
        table_width = self.table.width()

        # 为固定列预留宽度
        fixed_width = 70 + 80  # 操作列 + IP详情列

        # 剩余宽度分配给其他列
        remaining_width = table_width - fixed_width - 50  # 减去一些边距

        # 计算其他列的初始宽度
        ip_width = int(remaining_width * 0.25)  # IP列占25%
        remark_width = int(remaining_width * 0.30)  # 备注列占30%
        time_width = int(remaining_width * 0.30)  # 时间列占30%
        source_width = remaining_width - ip_width - remark_width - time_width  # 剩余给来源列

        # 设置宽度
        self.table.setColumnWidth(0, max(100, ip_width))
        self.table.setColumnWidth(1, max(100, remark_width))
        self.table.setColumnWidth(2, max(120, time_width))
        self.table.setColumnWidth(3, max(100, source_width))
        self.table.setColumnWidth(4, 70)  # 操作列
        self.table.setColumnWidth(5, 80)  # IP详情列

    def resizeEvent(self, event):
        """窗口大小改变时重新调整列宽"""
        super().resizeEvent(event)
        if hasattr(self, 'table') and self.table.rowCount() > 0:
            QTimer.singleShot(50, self.set_initial_column_widths)

    def on_header_clicked(self, column):
        """表头点击事件处理"""
        if column in [0, 1, 2, 3]:  # 只对IP、备注、创建时间、操作来源列进行排序
            if self.sort_column == column:
                # 点击同一列，切换排序顺序
                self.sort_order = Qt.DescendingOrder if self.sort_order == Qt.AscendingOrder else Qt.AscendingOrder
            else:
                # 点击不同列，默认升序
                self.sort_order = Qt.AscendingOrder
                self.sort_column = column

            # 执行排序
            self.table.sortItems(column, self.sort_order)

    def load_data(self):
        """加载黑名单数据"""
        try:
            entries = self.get_entries()

            # 先禁用排序，防止在填充数据时自动排序
            self.table.setSortingEnabled(False)

            # 保存当前滚动位置
            scroll_value = self.table.verticalScrollBar().value()

            self.table.setRowCount(len(entries))

            for row, entry in enumerate(entries):
                ip_spec = entry['ip']

                # IP条目 - 设置为可选择和复制
                ip_item = QTableWidgetItem(ip_spec)
                ip_item.setFlags(ip_item.flags() & ~Qt.ItemIsEditable)
                ip_item.setFlags(ip_item.flags() | Qt.ItemIsEnabled)
                ip_item.setToolTip(ip_spec)  # 添加提示，鼠标悬停显示完整IP
                self.table.setItem(row, 0, ip_item)

                # 备注
                remark = entry.get('remark', '')
                remark_item = QTableWidgetItem(remark)
                remark_item.setFlags(remark_item.flags() & ~Qt.ItemIsEditable)
                remark_item.setFlags(remark_item.flags() | Qt.ItemIsEnabled)
                if remark:
                    remark_item.setToolTip(remark)  # 添加提示
                self.table.setItem(row, 1, remark_item)

                # 创建时间 - 完整显示（包含时分秒）
                created_at = entry.get('created_at', '')
                if created_at:
                    try:
                        # 尝试解析和格式化时间
                        if 'T' in created_at:
                            date_part = created_at.split('T')[0]
                            time_part = created_at.split('T')[1].split('.')[0]
                            if len(time_part) > 8:
                                time_part = time_part[:8]
                            created_str = f"{date_part} {time_part}"
                        else:
                            created_str = created_at[:19] if len(created_at) >= 19 else created_at
                    except:
                        created_str = created_at[:19] if len(created_at) >= 19 else created_at
                else:
                    created_str = "未知"

                time_item = QTableWidgetItem(created_str)
                time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
                time_item.setFlags(time_item.flags() | Qt.ItemIsEnabled)
                # 设置一个隐藏的数据用于排序
                time_item.setData(Qt.UserRole, created_at)  # 存储原始时间字符串用于排序
                self.table.setItem(row, 2, time_item)

                # 操作来源
                created_by = entry.get('created_by', '')
                if self.security_manager and hasattr(self.security_manager, 'get_entry_display_info'):
                    display_info = self.security_manager.get_entry_display_info(entry)
                    source_display = display_info.get('created_by_display', created_by)
                else:
                    source_display = created_by

                source_item = QTableWidgetItem(source_display)
                source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                source_item.setFlags(source_item.flags() | Qt.ItemIsEnabled)
                source_item.setToolTip(source_display)  # 添加提示
                self.table.setItem(row, 3, source_item)

                # 删除按钮
                delete_btn = QPushButton("删除")
                delete_btn.setStyleSheet("""
                    QPushButton {
                        padding: 3px 8px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #c82333;
                    }
                """)
                delete_btn.clicked.connect(lambda checked, ip=ip_spec: self.delete_entry(ip))
                self.table.setCellWidget(row, 4, delete_btn)

                # IP详情按钮
                detail_btn = QPushButton("IP详情")
                detail_btn.setStyleSheet("""
                    QPushButton {
                        padding: 3px 8px;
                        background: #17a2b8;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #138496;
                    }
                """)
                detail_btn.clicked.connect(lambda checked, ip=ip_spec: self.show_ip_detail(ip))
                self.table.setCellWidget(row, 5, detail_btn)

            # 恢复滚动位置
            self.table.verticalScrollBar().setValue(scroll_value)

            # 重新启用排序
            self.table.setSortingEnabled(True)

            # 如果之前有排序状态，恢复排序
            if hasattr(self, 'sort_column'):
                self.table.sortItems(self.sort_column, self.sort_order)

        except Exception as e:
            logger.error(f"加载黑名单失败: {e}")

    def get_entries(self) -> List[Dict]:
        """获取黑名单条目"""
        if self.security_manager:
            return self.security_manager.get_blacklist_entries()
        return []

    def add_entry(self):
        """添加黑名单条目"""
        ip_spec = self.ip_input.text().strip()
        remark = self.remark_input.text().strip()

        if not ip_spec:
            QMessageBox.warning(self, "输入错误", "请输入IP或IP段")
            return

        if not self.security_manager:
            QMessageBox.warning(self, "错误", "安全管理器未初始化")
            return

        if self.security_manager.add_to_blacklist(ip_spec, remark, "user"):
            QMessageBox.information(self, "成功", f"已添加到黑名单: {ip_spec}")
            self.ip_input.clear()
            self.remark_input.clear()
            self.load_data()
        else:
            QMessageBox.warning(self, "添加失败", "IP格式无效或已存在")

    def delete_entry(self, ip_spec: str):
        """删除黑名单条目"""
        reply = QMessageBox.question(self, "确认删除",
                                   f"确定要从黑名单中删除 {ip_spec} 吗？")
        if reply == QMessageBox.Yes:
            if self.security_manager:
                if self.security_manager.remove_from_blacklist(ip_spec):
                    QMessageBox.information(self, "成功", f"已从黑名单删除: {ip_spec}")
                    self.load_data()
                else:
                    QMessageBox.warning(self, "删除失败", "删除失败，条目可能不存在")

    def show_ip_detail(self, ip: str):
        """显示IP详情对话框"""
        dialog = IPDetailDialog(ip, self.ip_geo_manager, self)
        dialog.exec()


class TempBanManagerTab(QWidget):
    """临时封禁管理标签页"""

    def __init__(self, security_manager, ip_geo_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.ip_geo_manager = ip_geo_manager
        self.sort_column = 0
        self.sort_order = Qt.AscendingOrder

        # 用于跟踪鼠标悬停的单元格
        self.last_hover_row = -1
        self.last_hover_column = -1
        self.last_tooltip_time = 0

        self.setup_ui()
        # 启用鼠标跟踪
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)

    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)

        # 统计信息和工具栏
        toolbar_layout = QHBoxLayout()

        # 统计信息标签
        self.stats_label = QLabel("正在加载...")
        toolbar_layout.addWidget(self.stats_label)

        toolbar_layout.addStretch()  # 中间弹性空间

        # 历史记录按钮
        self.history_btn = QPushButton("📜 历史记录")
        self.history_btn.setToolTip("查看已过期的封禁记录")
        self.history_btn.clicked.connect(self.show_ban_history)
        self.history_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #5a6268;
            }
        """)
        toolbar_layout.addWidget(self.history_btn)

        layout.addLayout(toolbar_layout)

        # 临时封禁表格 - 使用混合模式列宽管理
        self.table = QTableWidget()
        self.table.setColumnCount(8)  # 增加到8列，包含操作来源
        self.table.setHorizontalHeaderLabels([
            "IP地址", "封禁原因", "操作来源", "失败次数",
            "解封时间", "剩余时间", "操作", "IP详情"
        ])

        # 禁用选中高亮
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)

        # 设置列宽策略 - 混合模式
        self.setup_column_resize_modes()

        # 设置初始列宽（延迟执行，确保表格已显示）
        QTimer.singleShot(100, self.set_initial_column_widths)

        # 启用排序功能
        self.table.setSortingEnabled(True)

        # 连接表头点击事件
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)

        # 启用鼠标悬停事件
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)

        # 连接鼠标移动事件
        self.table.entered.connect(self.on_table_cell_entered)

        # 设置表格样式 - 移除选中样式
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f8f9fa;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #e0e0e0;
            }
            QTableWidget::item:hover {
                background-color: #f5f5f5;
            }
            QHeaderView::section {
                background-color: #f1f3f4;
                padding: 8px 5px;
                border: 1px solid #dadce0;
                font-weight: bold;
                font-size: 12px;
            }
            QHeaderView::section:active {
                background-color: #e0e0e0;
            }
            QTableCornerButton::section {
                background-color: #f1f3f4;
                border: 1px solid #dadce0;
            }
        """)

        layout.addWidget(self.table)

        # 说明文本
        help_text = QLabel("说明: 临时封禁是由于认证失败次数过多或扫描攻击自动触发的")
        help_text.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(help_text)

    def setup_column_resize_modes(self):
        """设置列的调整模式 - 混合模式"""
        header = self.table.horizontalHeader()

        # 第0列（IP地址）：Interactive模式，可拖动调整
        header.setSectionResizeMode(0, QHeaderView.Interactive)

        # 第1列（封禁原因）：Interactive模式，可拖动调整
        header.setSectionResizeMode(1, QHeaderView.Interactive)

        # 第2列（操作来源）：ResizeToContents模式，根据内容调整，但可拖动
        header.setSectionResizeMode(2, QHeaderView.Interactive)

        # 第3列（失败次数）：ResizeToContents模式，根据内容调整，但可拖动
        header.setSectionResizeMode(3, QHeaderView.Interactive)

        # 第4列（解封时间）：ResizeToContents模式，根据内容调整，但可拖动
        header.setSectionResizeMode(4, QHeaderView.Interactive)

        # 第5列（剩余时间）：ResizeToContents模式，根据内容调整，但可拖动
        header.setSectionResizeMode(5, QHeaderView.Interactive)

        # 第6列（操作）：Fixed模式，固定宽度（包含两个按钮）
        header.setSectionResizeMode(6, QHeaderView.Fixed)

        # 第7列（IP详情）：Fixed模式，固定宽度
        header.setSectionResizeMode(7, QHeaderView.Fixed)

        # 设置最小宽度，防止列被压缩得太小
        for col in range(self.table.columnCount()):
            header.setMinimumSectionSize(60)

    def set_initial_column_widths(self):
        """设置初始列宽，使表格看起来更美观"""
        try:
            # 获取表格当前宽度
            table_width = self.table.viewport().width() if self.table.viewport() else self.table.width()

            if table_width <= 0:
                # 如果表格还未显示，使用默认宽度
                table_width = 800  # 默认宽度

            # 为固定列预留宽度
            fixed_width = 170 + 80  # 操作列(170) + IP详情列(80)

            # 剩余宽度分配给其他可调整的列
            remaining_width = table_width - fixed_width - 30  # 减去一些边距

            if remaining_width <= 0:
                # 如果窗口太小，使用最小宽度
                remaining_width = 500

            # 计算各列的分配比例
            # IP地址列：17%
            # 封禁原因列：20%
            # 操作来源列：20%
            # 失败次数列：5%
            # 解封时间列：25%
            # 剩余时间列：根据内容自动调整

            # 计算宽度
            ip_width = int(remaining_width * 0.17)
            reason_width = int(remaining_width * 0.20)
            source_width = int(remaining_width * 0.20)
            failures_width = int(remaining_width * 0.05)
            unban_width = int(remaining_width * 0.25)
            remaining_time_width = remaining_width - (ip_width + reason_width + source_width +
                                                      failures_width + unban_width)

            # 设置宽度（确保最小宽度）
            self.table.setColumnWidth(0, max(90, ip_width))      # IP地址
            self.table.setColumnWidth(1, max(120, reason_width))  # 封禁原因
            self.table.setColumnWidth(2, max(100, source_width))  # 操作来源
            self.table.setColumnWidth(3, max(60, failures_width)) # 失败次数
            self.table.setColumnWidth(4, max(155, unban_width))   # 解封时间

            # 剩余时间列根据内容自动调整，设置一个初始值
            self.table.setColumnWidth(5, max(80, remaining_time_width))  # 剩余时间

            # 固定列宽度
            self.table.setColumnWidth(6, 170)  # 操作列
            self.table.setColumnWidth(7, 80)   # IP详情列

        except Exception as e:
            logger.error(f"设置初始列宽失败: {e}")
            # 设置备用的固定宽度
            self.table.setColumnWidth(0, 150)  # IP地址
            self.table.setColumnWidth(1, 200)  # 封禁原因
            self.table.setColumnWidth(2, 120)  # 操作来源
            self.table.setColumnWidth(3, 80)   # 失败次数
            self.table.setColumnWidth(4, 150)  # 解封时间
            self.table.setColumnWidth(5, 100)  # 剩余时间
            self.table.setColumnWidth(6, 170)  # 操作列
            self.table.setColumnWidth(7, 80)   # IP详情列

    def resizeEvent(self, event):
        """窗口大小改变时重新调整列宽"""
        super().resizeEvent(event)
        # 延迟重新计算列宽，确保表格已更新
        if hasattr(self, 'table'):
            QTimer.singleShot(50, self.set_initial_column_widths)

    def load_data(self):
        """加载临时封禁数据"""
        try:
            entries = self.get_entries()

            # 先禁用排序
            self.table.setSortingEnabled(False)

            # 保存当前滚动位置
            scroll_value = self.table.verticalScrollBar().value()

            self.table.setRowCount(len(entries))

            for row, entry in enumerate(entries):
                ip_address = entry.get('ip', '未知')

                # IP地址
                ip_item = QTableWidgetItem(ip_address)
                ip_item.setFlags(ip_item.flags() & ~Qt.ItemIsEditable)
                ip_item.setFlags(ip_item.flags() | Qt.ItemIsEnabled)
                ip_item.setToolTip(ip_address)  # 添加提示
                self.table.setItem(row, 0, ip_item)

                # 封禁原因
                remark = entry.get('remark', '自动封禁')
                remark_item = QTableWidgetItem(remark)
                remark_item.setFlags(remark_item.flags() & ~Qt.ItemIsEditable)
                remark_item.setFlags(remark_item.flags() | Qt.ItemIsEnabled)
                if remark:
                    remark_item.setToolTip(remark)  # 添加提示
                self.table.setItem(row, 1, remark_item)

                # 操作来源
                created_by = entry.get('created_by', '')
                if self.security_manager and hasattr(self.security_manager, 'get_entry_display_info'):
                    display_info = self.security_manager.get_entry_display_info(entry)
                    source_display = display_info.get('created_by_display', created_by)
                else:
                    source_display = created_by

                source_item = QTableWidgetItem(source_display)
                source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                source_item.setFlags(source_item.flags() | Qt.ItemIsEnabled)
                source_item.setToolTip(source_display)  # 添加提示
                self.table.setItem(row, 2, source_item)

                # 失败次数
                failures = entry.get('failed_attempts', 0)
                failures_item = QTableWidgetItem(str(failures))
                failures_item.setFlags(failures_item.flags() & ~Qt.ItemIsEditable)
                failures_item.setFlags(failures_item.flags() | Qt.ItemIsEnabled)
                self.table.setItem(row, 3, failures_item)

                # 解封时间
                unban_time = entry.get('unban_time', 0)
                if unban_time:
                    unban_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(unban_time))
                    unban_item = QTableWidgetItem(unban_str)
                    unban_item.setData(Qt.UserRole, unban_time)
                else:
                    unban_str = "未知"
                    unban_item = QTableWidgetItem(unban_str)

                unban_item.setFlags(unban_item.flags() & ~Qt.ItemIsEditable)
                unban_item.setFlags(unban_item.flags() | Qt.ItemIsEnabled)
                self.table.setItem(row, 4, unban_item)

                # 剩余时间
                current_time = time.time()
                remaining = int(unban_time - current_time) if unban_time > current_time else 0
                remaining_str = self._format_remaining_time(remaining)
                remaining_item = QTableWidgetItem(remaining_str)
                remaining_item.setFlags(remaining_item.flags() & ~Qt.ItemIsEditable)
                remaining_item.setFlags(remaining_item.flags() | Qt.ItemIsEnabled)
                remaining_item.setData(Qt.UserRole, remaining)
                self.table.setItem(row, 5, remaining_item)

                # 操作按钮
                button_widget = QWidget()
                button_layout = QHBoxLayout(button_widget)
                button_layout.setContentsMargins(2, 2, 2, 2)
                button_layout.setSpacing(2)

                remove_btn = QPushButton("移除")
                remove_btn.setFixedWidth(60)
                remove_btn.setStyleSheet("""
                    QPushButton {
                        padding: 2px 6px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #c82333;
                    }
                """)
                remove_btn.clicked.connect(lambda checked, ip=ip_address: self.remove_ban(ip))
                button_layout.addWidget(remove_btn)

                move_btn = QPushButton("移至黑名单")
                move_btn.setFixedWidth(90)
                move_btn.setStyleSheet("""
                    QPushButton {
                        padding: 2px 6px;
                        background: #6c757d;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #5a6268;
                    }
                """)
                move_btn.clicked.connect(lambda checked, ip=ip_address: self.move_to_blacklist(ip))
                button_layout.addWidget(move_btn)

                self.table.setCellWidget(row, 6, button_widget)

                # IP详情按钮
                detail_btn = QPushButton("IP详情")
                detail_btn.setFixedWidth(70)
                detail_btn.setStyleSheet("""
                    QPushButton {
                        padding: 2px 6px;
                        background: #17a2b8;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #138496;
                    }
                """)
                detail_btn.clicked.connect(lambda checked, ip=ip_address: self.show_ip_detail(ip))
                self.table.setCellWidget(row, 7, detail_btn)

            # 恢复滚动位置
            self.table.verticalScrollBar().setValue(scroll_value)

            # 重新启用排序
            self.table.setSortingEnabled(True)

            # 恢复之前的排序状态
            if hasattr(self, 'sort_column'):
                self.table.sortItems(self.sort_column, self.sort_order)

            # 更新统计信息
            total_entries = len(entries)
            history_count = 0

            if self.security_manager and hasattr(self.security_manager, 'get_ban_history'):
                try:
                    history = self.security_manager.get_ban_history()
                    history_count = len(history) if history else 0
                except Exception as e:
                    logger.error(f"获取历史记录失败: {e}")

            self.stats_label.setText(f"活跃封禁: {total_entries} 个 | 历史记录: {history_count} 条")

        except Exception as e:
            logger.error(f"加载临时封禁数据失败: {e}")


    def show_ban_history(self):
        """显示封禁历史记录对话框"""
        if not self.security_manager:
            QMessageBox.warning(self, "错误", "安全管理器未初始化")
            return

        try:
            # 创建历史记录对话框
            dialog = BanHistoryDialog(self.security_manager, self)
            dialog.show()

        except Exception as e:
            logger.error(f"显示历史记录失败: {e}")
            QMessageBox.warning(self, "错误", f"显示历史记录失败: {e}")

    def clear_ban_history(self, history, parent_dialog, history_table):
        """清空封禁历史记录"""
        try:
            if not history:
                QMessageBox.information(parent_dialog, "提示", "当前没有历史记录可清空")
                return

            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                parent_dialog,
                "确认清空",
                f"确定要清空所有封禁历史记录吗？\n"
                f"共 {len(history)} 条记录将被永久删除。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 调用安全管理器的清空历史记录方法
                if hasattr(self.security_manager, 'clear_ban_history'):
                    if self.security_manager.clear_ban_history():
                        # 清空表格数据
                        history_table.setRowCount(0)

                        # 更新统计信息
                        stats_label = parent_dialog.findChild(QLabel)
                        if stats_label:
                            stats_label.setText("总计 0 条历史记录")

                        QMessageBox.information(parent_dialog, "成功", "已清空所有封禁历史记录")

                        # 重新加载临时封禁标签页的数据，更新统计信息
                        self.load_data()
                    else:
                        QMessageBox.warning(parent_dialog, "错误", "清空历史记录失败")
                else:
                    # 如果安全管理器没有 clear_ban_history 方法，使用备用方案
                    self._clear_ban_history_fallback(parent_dialog)

        except Exception as e:
            logger.error(f"清空历史记录失败: {e}")
            QMessageBox.warning(parent_dialog, "错误", f"清空失败: {e}")

    def _clear_ban_history_fallback(self, parent_dialog):
        """备用清空历史记录方法"""
        try:
            from PySide6.QtWidgets import QMessageBox

            # 直接操作配置文件
            if hasattr(self.security_manager, 'temp_bans_file'):
                import json
                from pathlib import Path
                from datetime import datetime

                temp_bans_file = Path(self.security_manager.temp_bans_file)

                if temp_bans_file.exists():
                    with open(temp_bans_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 只保留活跃封禁，清空历史记录
                    data['ban_history'] = []
                    data['metadata']['updated_at'] = datetime.now().isoformat()
                    data['metadata']['history_entries'] = 0

                    with open(temp_bans_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    QMessageBox.information(parent_dialog, "成功", "已清空封禁历史记录")

                    # 重新加载数据
                    if hasattr(self.security_manager, '_load_temp_bans'):
                        self.security_manager._load_temp_bans()

                    # 刷新对话框（如果对话框仍打开）
                    parent_dialog.close()
                else:
                    QMessageBox.warning(parent_dialog, "错误", "未找到封禁记录文件")
        except Exception as e:
            logger.error(f"备用清空方法失败: {e}")
            raise

    def export_history_to_csv(self, history, parent_dialog):
        """导出历史记录为CSV文件"""
        try:
            from PySide6.QtWidgets import QFileDialog

            # 选择保存位置
            filename, _ = QFileDialog.getSaveFileName(
                parent_dialog,
                "保存历史记录",
                f"ban_history_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV文件 (*.csv)"
            )

            if not filename:
                return

            import csv

            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    'IP地址', '封禁原因', '操作来源', '失败次数',
                    '封禁时间', '解封时间', '移除时间', '移除原因', '移除操作'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for entry in reversed(history):
                    # 格式化操作来源
                    created_by = entry.get('created_by', '')
                    if self.security_manager and hasattr(self.security_manager, 'get_entry_display_info'):
                        display_info = self.security_manager.get_entry_display_info(entry)
                        source_display = display_info.get('created_by_display', created_by)
                    else:
                        source_display = created_by

                    # 格式化封禁时间
                    created_at = entry.get('created_at', '')
                    created_time = created_at[:19] if created_at else '未知'

                    # 格式化解封时间
                    unban_time = entry.get('unban_time', 0)
                    if unban_time:
                        unban_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(unban_time))
                    else:
                        unban_str = "未知"

                    # 移除时间
                    removed_at = entry.get('removed_at', '')
                    if removed_at:
                        removed_time = removed_at[:19] if removed_at else ''
                    else:
                        removed_time = "-"  # 自动解封：横杠

                    # 移除原因
                    removed_reason = entry.get('removed_reason', '')
                    if not removed_reason and not removed_at:
                        removed_reason = "自动过期"

                    # 移除操作
                    removed_by = entry.get('removed_by', '')
                    if removed_by:
                        if self.security_manager and hasattr(self.security_manager, 'get_entry_display_info'):
                            removed_entry = {'created_by': removed_by}
                            display_info = self.security_manager.get_entry_display_info(removed_entry)
                            removed_display = display_info.get('created_by_display', removed_by)
                        else:
                            removed_display = removed_by
                    else:
                        removed_display = "-"

                    writer.writerow({
                        'IP地址': entry.get('ip', '未知'),
                        '封禁原因': entry.get('remark', '自动封禁'),
                        '操作来源': source_display,
                        '失败次数': entry.get('failed_attempts', 0),
                        '封禁时间': created_time,
                        '解封时间': unban_str,
                        '移除时间': removed_time,
                        '移除原因': removed_reason,
                        '移除操作': removed_display
                    })

            QMessageBox.information(parent_dialog, "成功", f"历史记录已导出到: {filename}")

        except Exception as e:
            logger.error(f"导出历史记录失败: {e}")
            QMessageBox.warning(parent_dialog, "错误", f"导出失败: {e}")

    def get_entries(self) -> List[Dict]:
        """获取临时封禁条目"""
        if not self.security_manager:  # 现在可以使用 self.security_manager 了
            return []

        return self.security_manager.get_temp_ban_entries()

    def on_header_clicked(self, column):
        """表头点击事件处理"""
        if column in [0, 1, 2, 3, 4, 5]:  # 对前6列进行排序
            if self.sort_column == column:
                self.sort_order = Qt.DescendingOrder if self.sort_order == Qt.AscendingOrder else Qt.AscendingOrder
            else:
                self.sort_order = Qt.AscendingOrder
                self.sort_column = column

            # 执行排序
            self.table.sortItems(column, self.sort_order)

    def on_table_cell_entered(self, index):
        """表格单元格鼠标进入事件 - 显示工具提示"""
        if not index.isValid():
            return

        current_time = time.time()
        # 防止过于频繁的提示
        if current_time - self.last_tooltip_time < 0.1:
            return

        row = index.row()
        column = index.column()

        # 如果鼠标还在同一个单元格，不重复显示
        if row == self.last_hover_row and column == self.last_hover_column:
            return

        self.last_hover_row = row
        self.last_hover_column = column
        self.last_tooltip_time = current_time

        # 只对前6列显示提示（操作按钮列不需要）
        if column >= 6:
            return

        item = self.table.item(row, column)
        if not item:
            return

        # 获取单元格文本
        text = item.text()
        if not text or text == "未知":
            return

        # 获取单元格矩形
        rect = self.table.visualRect(index)

        # 计算单元格内文本是否被截断
        font_metrics = self.table.fontMetrics()
        text_width = font_metrics.horizontalAdvance(text)
        cell_width = rect.width() - 10  # 减去一些边距

        # 只有当文本宽度大于单元格宽度时才显示工具提示
        if text_width > cell_width:
            # 获取鼠标位置
            pos = QCursor.pos()
            # 显示工具提示
            QToolTip.showText(pos, text, self.table)
        else:
            QToolTip.hideText()


    def _format_remaining_time(self, seconds: int) -> str:
        """格式化剩余时间显示"""
        if seconds <= 0:
            return "已过期"
        elif seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}分{secs}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}时{minutes}分{secs}秒"

    def remove_ban(self, ip: str):
        """移除临时封禁"""
        if ip == '未知':
            QMessageBox.warning(self, "错误", "无法移除未知IP的封禁")
            return

        reply = QMessageBox.question(self, "确认移除",
                                   f"确定要移除 {ip} 的临时封禁吗？")
        if reply == QMessageBox.Yes:
            if self.security_manager and hasattr(self.security_manager, 'remove_temp_ban'):
                try:
                    if self.security_manager.remove_temp_ban(ip):
                        QMessageBox.information(self, "成功", f"已移除 {ip} 的临时封禁")
                        self.load_data()
                    else:
                        QMessageBox.warning(self, "错误", f"未找到 {ip} 的封禁记录")
                except Exception as e:
                    logger.error(f"移除封禁失败: {e}")
                    QMessageBox.warning(self, "错误", f"移除封禁失败: {e}")

    def move_to_blacklist(self, ip: str):
        """将临时封禁移到黑名单"""
        if ip == '未知':
            QMessageBox.warning(self, "错误", "无法处理未知IP")
            return

        reply = QMessageBox.question(self, "确认移动",
                                   f"确定要将 {ip} 移到黑名单吗？")

        if reply == QMessageBox.Yes:
            if self.security_manager and hasattr(self.security_manager, 'move_to_blacklist'):
                try:
                    # 询问备注
                    from PySide6.QtWidgets import QInputDialog
                    remark, ok = QInputDialog.getText(
                        self, "添加备注",
                        "请输入添加到黑名单的备注（可选）:",
                        text=""
                    )

                    if self.security_manager.move_to_blacklist(ip, remark if ok else ""):
                        QMessageBox.information(self, "成功", f"已将 {ip} 移到黑名单")
                        self.load_data()
                    else:
                        QMessageBox.warning(self, "错误", "移动到黑名单失败")
                except Exception as e:
                    logger.error(f"移动到黑名单失败: {e}")
                    QMessageBox.warning(self, "错误", f"移动到黑名单失败: {e}")

    def show_ip_detail(self, ip: str):
        """显示IP详情对话框"""
        dialog = IPDetailDialog(ip, self.ip_geo_manager, self)
        dialog.exec()
