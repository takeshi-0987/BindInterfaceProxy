# -*- coding: utf-8 -*-
"""
Module: ban_history_dialog.py
Author: Takeshi
Date: 2025-11-25

Description:
    封禁历史记录对话框 - 显示已过期的封禁记录
"""

import logging
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QMessageBox,
    QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QIcon
from defaults.ui_default import DIALOG_ICOINS, SECURITY_BAN_HISTORY_DIALOG_SIZE

logger = logging.getLogger(__name__)


class BanHistoryDialog(QDialog):
    """封禁历史记录对话框"""

    def __init__(self, security_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.current_history = []
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("BindInterfaceProxy - 封禁历史记录")
        self.resize(*SECURITY_BAN_HISTORY_DIALOG_SIZE)

        # 启用对话框的最小化和最大化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        layout = QVBoxLayout(self)

        # 统计信息
        self.stats_label = QLabel("正在加载...")
        self.stats_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self.stats_label)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(9)
        self.history_table.setHorizontalHeaderLabels([
            "IP地址", "封禁原因", "操作来源", "失败次数",
            "封禁时间", "解封时间", "移除时间", "移除原因", "移除操作"
        ])

        # 设置表格属性：禁止选择和编辑
        self.history_table.setSelectionMode(QTableWidget.NoSelection)  # 禁止选择
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 禁止编辑
        self.history_table.setFocusPolicy(Qt.NoFocus)  # 禁止获得焦点

        # 设置列宽策略
        self.setup_column_resize_modes()

        # 设置表格样式
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f8f9fa;
                gridline-color: #e0e0e0;
                selection-background-color: transparent;  /* 去掉选中背景色 */
                selection-color: black;  /* 选中文本颜色不变 */
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #e0e0e0;
                color: black;
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
            QTableCornerButton::section {
                background-color: #f1f3f4;
                border: 1px solid #dadce0;
            }
        """)

        layout.addWidget(self.history_table)

        # 提示信息
        self.info_label = QLabel("正在加载提示信息...")
        self.info_label.setStyleSheet("color: gray; font-size: 10px; padding: 5px;")
        layout.addWidget(self.info_label)

        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # 打开历史记录文件夹按钮
        self.open_folder_btn = QPushButton("📂 打开历史记录文件夹")
        self.open_folder_btn.setToolTip("打开历史记录文件所在文件夹")
        self.open_folder_btn.clicked.connect(self.open_history_folder)
        button_layout.addWidget(self.open_folder_btn)

        # 清空历史记录的按钮
        self.clear_btn = QPushButton("🗑️ 清空历史记录")
        self.clear_btn.setToolTip("永久删除所有历史记录")
        self.clear_btn.clicked.connect(self.clear_ban_history)
        button_layout.addWidget(self.clear_btn)

        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def setup_column_resize_modes(self):
        """设置列的调整模式"""
        header = self.history_table.horizontalHeader()

        # 设置各列的调整策略
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # IP地址
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # 封禁原因
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 操作来源
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 失败次数
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 封禁时间
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 解封时间
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 移除时间
        header.setSectionResizeMode(7, QHeaderView.Stretch)      # 移除原因
        header.setSectionResizeMode(8, QHeaderView.Stretch)      # 移除操作

        # 设置初始列宽
        self.set_initial_column_widths()

    def set_initial_column_widths(self):
        """设置初始列宽"""
        self.history_table.setColumnWidth(0, 120)  # IP地址
        self.history_table.setColumnWidth(1, 130)  # 封禁原因
        self.history_table.setColumnWidth(2, 150)  # 操作来源
        self.history_table.setColumnWidth(3, 80)   # 失败次数
        self.history_table.setColumnWidth(4, 150)  # 封禁时间
        self.history_table.setColumnWidth(5, 150)  # 解封时间
        self.history_table.setColumnWidth(6, 150)  # 移除时间
        self.history_table.setColumnWidth(7, 150)  # 移除原因
        self.history_table.setColumnWidth(8, 150)  # 移除操作

    def load_data(self):
        """加载历史记录数据"""
        try:
            if not self.security_manager:
                self.stats_label.setText("安全管理器未初始化")
                self.info_label.setText("无法加载历史记录")
                self.history_table.setRowCount(0)
                return

            # 检查历史记录功能是否启用
            if not self.security_manager.config.core.keep_ban_history:
                self.stats_label.setText("历史记录功能未启用")
                self.info_label.setText("请在配置中启用历史记录功能")
                self.history_table.setRowCount(0)
                return

            # 获取历史记录（只显示最近的部分）
            max_history_size = self.security_manager.config.core.max_history_size
            self.current_history = self.security_manager.get_ban_history(max_history_size)

            if not self.current_history:
                self.stats_label.setText("暂无封禁历史记录")
                self.info_label.setText("没有历史记录")
                self.history_table.setRowCount(0)
                return

            # 更新统计信息和提示
            current_count = len(self.current_history)
            max_size = max_history_size

            self.stats_label.setText(f"显示最近 {current_count} 条历史记录")

            # 更新提示信息，显示最大显示条数
            if current_count >= max_size:
                self.info_label.setText(f"已达到最大显示 {max_size} 条记录，旧记录会被自动清理")
            else:
                self.info_label.setText(f"最大显示 {max_size} 条历史记录，当前显示 {current_count} 条")

            # 填充表格
            self.history_table.setRowCount(current_count)

            for row, entry in enumerate(reversed(self.current_history)):  # 倒序显示，最新的在前面
                # IP地址
                ip_item = QTableWidgetItem(entry.get('ip', '未知'))
                ip_item.setFlags(ip_item.flags() & ~Qt.ItemIsEditable)  # 禁止编辑
                ip_item.setFlags(ip_item.flags() | Qt.ItemIsEnabled)    # 启用显示
                self.history_table.setItem(row, 0, ip_item)

                # 封禁原因
                remark_item = QTableWidgetItem(entry.get('remark', '自动封禁'))
                remark_item.setFlags(remark_item.flags() & ~Qt.ItemIsEditable)
                remark_item.setFlags(remark_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 1, remark_item)

                # 操作来源（使用转换后的友好文本）
                created_by = entry.get('created_by', '')
                if self.security_manager and hasattr(self.security_manager, 'get_entry_display_info'):
                    display_info = self.security_manager.get_entry_display_info(entry)
                    source_display = display_info.get('created_by_display', created_by)
                else:
                    source_display = created_by
                source_item = QTableWidgetItem(source_display)
                source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                source_item.setFlags(source_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 2, source_item)

                # 失败次数
                failures_item = QTableWidgetItem(str(entry.get('failed_attempts', 0)))
                failures_item.setFlags(failures_item.flags() & ~Qt.ItemIsEditable)
                failures_item.setFlags(failures_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 3, failures_item)

                # 封禁时间
                created_at = entry.get('created_at', '')
                created_item = QTableWidgetItem(created_at[:19] if created_at else '未知')
                created_item.setFlags(created_item.flags() & ~Qt.ItemIsEditable)
                created_item.setFlags(created_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 4, created_item)

                # 解封时间
                unban_time = entry.get('unban_time', 0)
                if unban_time:
                    unban_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(unban_time))
                else:
                    unban_str = "未知"
                unban_item = QTableWidgetItem(unban_str)
                unban_item.setFlags(unban_item.flags() & ~Qt.ItemIsEditable)
                unban_item.setFlags(unban_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 5, unban_item)

                # 移除时间
                removed_at = entry.get('removed_at', '')
                if removed_at:
                    # 手动移除：显示具体时间
                    removed_time = removed_at[:19] if removed_at else ''
                else:
                    # 自动过期：显示横杠
                    removed_time = "-"
                removed_time_item = QTableWidgetItem(removed_time)
                removed_time_item.setFlags(removed_time_item.flags() & ~Qt.ItemIsEditable)
                removed_time_item.setFlags(removed_time_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 6, removed_time_item)

                # 移除原因
                removed_reason = entry.get('removed_reason', '')
                current_time = time.time()

                # 判断是否已到解封时间
                if not removed_reason and not removed_at:
                    # 如果没有移除原因也没有移除时间
                    if unban_time > 0 and current_time >= unban_time:
                        # 已到解封时间：显示自动移除
                        removed_reason = "自动移除"
                    else:
                        # 未到解封时间：显示横杠
                        removed_reason = "-"
                elif not removed_reason:
                    # 有移除时间但没有移除原因
                    if unban_time > 0 and current_time >= unban_time:
                        # 已到解封时间：显示自动移除
                        removed_reason = "自动移除"
                    else:
                        # 未到解封时间：显示横杠
                        removed_reason = "-"

                removed_reason_item = QTableWidgetItem(removed_reason)
                removed_reason_item.setFlags(removed_reason_item.flags() & ~Qt.ItemIsEditable)
                removed_reason_item.setFlags(removed_reason_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 7, removed_reason_item)

                # 移除操作
                removed_by = entry.get('removed_by', '')
                if removed_by:
                    if self.security_manager and hasattr(self.security_manager, 'get_entry_display_info'):
                        # 为移除操作创建一个临时的字典来获取显示名称
                        removed_entry = {'created_by': removed_by}
                        display_info = self.security_manager.get_entry_display_info(removed_entry)
                        removed_display = display_info.get('created_by_display', removed_by)
                    else:
                        removed_display = removed_by
                else:
                    removed_display = "-"
                removed_by_item = QTableWidgetItem(removed_display)
                removed_by_item.setFlags(removed_by_item.flags() & ~Qt.ItemIsEditable)
                removed_by_item.setFlags(removed_by_item.flags() | Qt.ItemIsEnabled)
                self.history_table.setItem(row, 8, removed_by_item)

        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            self.stats_label.setText(f"加载失败: {str(e)[:50]}...")
            QMessageBox.warning(self, "错误", f"加载历史记录失败: {e}")

    def open_history_folder(self):
        """打开历史记录文件所在文件夹"""
        try:
            if not self.security_manager:
                QMessageBox.warning(self, "错误", "安全管理器未初始化")
                return

            # 获取历史记录文件路径
            if hasattr(self.security_manager, 'ban_history_file'):
                history_file = self.security_manager.ban_history_file
            else:
                # 如果没有ban_history_file属性，使用默认路径
                history_file = Path("data/ban_history.csv")

            config_folder = Path(history_file).parent

            if not config_folder.exists():
                # 尝试创建文件夹
                try:
                    config_folder.mkdir(parents=True, exist_ok=True)
                    logger.info(f"已创建历史记录文件夹: {config_folder}")
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"无法创建历史记录文件夹: {e}")
                    return

            # 打开文件夹
            if config_folder.exists():
                QDesktopServices.openUrl(f"file:///{config_folder.absolute()}")
                logger.info(f"已打开历史记录文件夹: {config_folder.absolute()}")
            else:
                QMessageBox.warning(self, "错误", f"历史记录文件夹不存在: {config_folder}")

        except Exception as e:
            logger.error(f"打开历史记录文件夹失败: {e}")
            QMessageBox.warning(self, "错误", f"打开文件夹失败: {e}")

    def clear_ban_history(self):
        """清空封禁历史记录"""
        try:
            if not self.current_history:
                QMessageBox.information(self, "提示", "当前没有历史记录可清空")
                return

            reply = QMessageBox.question(
                self,
                "确认清空",
                f"确定要清空所有封禁历史记录吗？\n"
                f"共 {len(self.current_history)} 条记录将被永久删除。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 调用安全管理器的清空历史记录方法
                if hasattr(self.security_manager, 'clear_ban_history'):
                    if self.security_manager.clear_ban_history():
                        # 清空表格数据
                        self.current_history = []
                        self.history_table.setRowCount(0)

                        # 更新统计信息
                        self.stats_label.setText("已清空所有历史记录")
                        self.info_label.setText("历史记录已清空")

                        QMessageBox.information(self, "成功", "已清空所有封禁历史记录")
                    else:
                        QMessageBox.warning(self, "错误", "清空历史记录失败")
                else:
                    # 如果安全管理器没有 clear_ban_history 方法，使用备用方案
                    self._clear_ban_history_fallback()

        except Exception as e:
            logger.error(f"清空历史记录失败: {e}")
            QMessageBox.warning(self, "错误", f"清空失败: {e}")

    def _clear_ban_history_fallback(self):
        """备用清空历史记录方法"""
        try:
            # 直接操作配置文件
            if hasattr(self.security_manager, 'ban_history_file'):
                # 清空CSV文件
                ban_history_file = Path(self.security_manager.ban_history_file)

                if ban_history_file.exists():
                    # 清空CSV文件（只保留表头）
                    import csv
                    with open(ban_history_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            'ip', 'failed_attempts', 'unban_time', 'remark', 'created_at',
                            'created_by', 'duration', 'protocol', 'removed_at', 'removed_by', 'removed_reason'
                        ])

                    # 更新界面
                    self.current_history = []
                    self.history_table.setRowCount(0)
                    self.stats_label.setText("已清空所有历史记录")
                    self.info_label.setText("历史记录已清空")

                    QMessageBox.information(self, "成功", "已清空封禁历史记录")
                else:
                    QMessageBox.warning(self, "错误", "未找到封禁历史记录文件")
        except Exception as e:
            logger.error(f"备用清空方法失败: {e}")
            raise
