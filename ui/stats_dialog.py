# -*- coding: utf-8 -*-
"""
Module: stats_dialog.py
Author: Takeshi
Date: 2025-12-26

Description:
    连接流量对话框
"""


from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QFrame, QGridLayout, QComboBox, QMessageBox, QFileDialog,
    QAbstractItemView, QHeaderView
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QIcon

from managers.stats_manager import StatsManager, DailyStats
from defaults.ui_default import STATS_DIALOG_SIZE, STATS_REFRESH_INTERVAL, DIALOG_ICOINS

import logging
import csv

logger = logging.getLogger(__name__)


class MonitorDialog(QDialog):
    """连接流量对话框"""

    def __init__(self, stats_manager: StatsManager, parent=None):
        super().__init__(parent)

        self.stats_manager = stats_manager

        # 当前日期
        self.current_day = datetime.now().strftime("%Y-%m-%d")

        # 设置窗口
        self.setWindowTitle("BindInterfaceProxy - 连接流量统计")
        self.resize(*STATS_DIALOG_SIZE)

        # 非模态
        self.setModal(False)

        # 启用对话框的最小化和最大化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        # 初始化数据
        self.filter_type = "总体"
        self.time_range = "今日"

        # 实时筛选条件
        self.realtime_filter_type = "全部连接"
        self.realtime_filter_value = "全部"

        # 缓存数据
        self.summary_data_cache = None
        self.active_counts_cache = None

        # 创建UI
        self.create_ui()

        # 立即加载数据
        self.load_data()

        self.update_date_range_label()
        self.remark_label.setText("📢 流量统计为代理与客户端之间的流量 \n发送=向客户端发送 | 接收=从客户端接收")

        # 定时刷新
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(STATS_REFRESH_INTERVAL)


    def create_ui(self):
        """创建UI"""
        layout = QVBoxLayout(self)

        # 1. 筛选区
        self.create_filter_area(layout)

        # 2. 中部：标签页
        self.create_tabs(layout)

        # 3. 底部：控制栏
        self.create_control_bar(layout)

    def create_filter_area(self, parent_layout):
        """创建筛选区域"""
        frame = QFrame()

        # 使用网格布局，第一行是筛选控件，第二行是新加的日期和备注
        main_layout = QVBoxLayout(frame)
        main_layout.setContentsMargins(10, 5, 10, 5)

        # 第一行：筛选控件
        filter_row_layout = QHBoxLayout()

        # 时间筛选（汇总页用）
        filter_row_layout.addWidget(QLabel("时间范围:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(["今日", "昨日", "最近7天", "最近30天", "全部"])
        self.time_combo.setCurrentText("今日")
        self.time_combo.currentTextChanged.connect(self.on_time_filter_changed)
        filter_row_layout.addWidget(self.time_combo)

        filter_row_layout.addSpacing(20)

        # 分组方式（汇总页用）
        filter_row_layout.addWidget(QLabel("分组方式:"))
        self.group_combo = QComboBox()
        self.group_combo.addItems(["总体", "代理名称", "代理类型", "IP", "地理信息", "用户"])
        self.group_combo.setCurrentText("总体")
        self.group_combo.currentTextChanged.connect(self.on_group_changed)
        filter_row_layout.addWidget(self.group_combo)

        filter_row_layout.addSpacing(20)

        # 实时连接筛选（实时监控页用）
        filter_row_layout.addWidget(QLabel("实时筛选:"))
        self.realtime_filter_combo = QComboBox()
        self.realtime_filter_combo.addItems(["全部连接", "按代理", "按IP", "按地理信息", "按用户", "按协议"])
        self.realtime_filter_combo.setCurrentText("全部连接")
        self.realtime_filter_combo.currentTextChanged.connect(self.on_realtime_filter_changed)
        self.realtime_filter_combo.setEnabled(False)  # 默认在汇总页，禁用
        filter_row_layout.addWidget(self.realtime_filter_combo)

        # 实时筛选值
        self.realtime_filter_value_combo = QComboBox()
        self.realtime_filter_value_combo.addItem("全部")
        self.realtime_filter_value_combo.setEnabled(False)
        self.realtime_filter_value_combo.setMinimumWidth(200)  # 增加最小宽度
        self.realtime_filter_value_combo.currentTextChanged.connect(self.on_realtime_filter_value_changed)
        filter_row_layout.addWidget(self.realtime_filter_value_combo)

        # 在右侧添加日期范围和备注的容器
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # 第一行：日期范围
        self.date_range_label = QLabel("日期范围: 今日")
        self.date_range_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.date_range_label.setStyleSheet("color: #2980b9; font-weight: bold; font-size: 12px;")
        info_layout.addWidget(self.date_range_label)

        # 第二行：备注说明
        self.remark_label = QLabel("📢 流量统计为代理与客户端之间流量")
        self.remark_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.remark_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        info_layout.addWidget(self.remark_label)

        # 设置容器的最小宽度以确保完整显示
        info_container.setMinimumWidth(350)
        filter_row_layout.addWidget(info_container)

        filter_row_layout.addStretch()

        # 将第一行添加到主布局
        main_layout.addLayout(filter_row_layout)

        parent_layout.addWidget(frame)

    def create_tabs(self, parent_layout):
        """创建标签页"""
        self.tab_widget = QTabWidget()

        # Tab 1: 汇总信息
        self.summary_widget = self.create_summary_tab()
        self.tab_widget.addTab(self.summary_widget, "汇总信息")

        # Tab 2: 实时监控
        self.monitor_widget = self.create_monitor_tab()
        self.tab_widget.addTab(self.monitor_widget, "实时连接")

        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        parent_layout.addWidget(self.tab_widget, 1)


    def create_summary_tab(self):
        """创建汇总信息标签页 - 使用混合模式列宽管理"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ========== 汇总信息表格 ==========
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(12)

        # 禁用选中高亮
        self.summary_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.summary_table.setFocusPolicy(Qt.NoFocus)

        # 修改表头顺序：发送数据量在接收数据量前面
        headers = [
            "序号", "代理名称", "代理类型", "IP", "地理信息", "用户",
            "总连接数", "活跃连接", "发送数据量", "接收数据量", "总数据量", "最后活跃"
        ]
        self.summary_table.setHorizontalHeaderLabels(headers)

        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setSortingEnabled(True)

        # 设置列宽策略 - 混合模式
        self.setup_summary_column_resize_modes()

        # 设置初始列宽（延迟执行，确保表格已显示）
        QTimer.singleShot(100, self.set_summary_initial_column_widths)

        # 启用排序功能
        self.summary_table.setSortingEnabled(True)

        # 设置表格样式
        self.summary_table.setStyleSheet("""
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

        layout.addWidget(self.summary_table, 1)

        # ========== 汇总统计信息区域 ==========
        summary_frame = QFrame()
        summary_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        summary_layout = QGridLayout(summary_frame)
        summary_layout.setSpacing(8)

        # 汇总标题
        summary_title = QLabel("📊 统计信息")
        summary_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        summary_layout.addWidget(summary_title, 0, 0, 1, 6)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        summary_layout.addWidget(separator, 1, 0, 1, 6)

        # 连接统计（第2行）
        self.summary_total_connections_label = QLabel("总连接数: 0")
        self.summary_active_connections_label = QLabel("活跃连接: 0")
        self.summary_today_connections_label = QLabel("今日连接: 0")
        self.summary_failed_connections_label = QLabel("失败连接: 0")

        summary_layout.addWidget(QLabel("🔗 连接统计:"), 2, 0)
        summary_layout.addWidget(self.summary_total_connections_label, 2, 1)
        summary_layout.addWidget(self.summary_active_connections_label, 2, 2)
        summary_layout.addWidget(self.summary_today_connections_label, 2, 3)
        summary_layout.addWidget(self.summary_failed_connections_label, 2, 4)

        # 流量统计（第3行）- 修改顺序：发送在前，接收在后
        self.summary_total_sent_label = QLabel("总发送: 0 B")
        self.summary_total_received_label = QLabel("总接收: 0 B")
        self.summary_total_traffic_label = QLabel("总流量: 0 B")
        self.summary_today_traffic_label = QLabel("今日流量: 0 B")

        summary_layout.addWidget(QLabel("📈 流量统计:"), 3, 0)
        summary_layout.addWidget(self.summary_total_sent_label, 3, 1)
        summary_layout.addWidget(self.summary_total_received_label, 3, 2)
        summary_layout.addWidget(self.summary_total_traffic_label, 3, 3)
        summary_layout.addWidget(self.summary_today_traffic_label, 3, 4)

        # 维度统计（第4行）
        self.summary_unique_ips_label = QLabel("唯一IP: 0")
        self.summary_unique_proxies_label = QLabel("唯一代理: 0")
        self.summary_unique_users_label = QLabel("唯一用户: 0")
        self.summary_unique_countries_label = QLabel("唯一位置: 0")

        summary_layout.addWidget(QLabel("🌐 维度统计:"), 4, 0)
        summary_layout.addWidget(self.summary_unique_ips_label, 4, 1)
        summary_layout.addWidget(self.summary_unique_proxies_label, 4, 2)
        summary_layout.addWidget(self.summary_unique_users_label, 4, 3)
        summary_layout.addWidget(self.summary_unique_countries_label, 4, 4)

        # 时间范围显示（第5行）
        self.summary_time_range_label = QLabel("时间范围: 今日")
        self.summary_time_range_label.setStyleSheet("color: #7f8c8d; font-style: italic; padding-top: 5px;")
        summary_layout.addWidget(self.summary_time_range_label, 5, 0, 1, 6)

        layout.addWidget(summary_frame)

        return widget

    def setup_summary_column_resize_modes(self):
        """设置汇总表格的调整模式 - 混合模式"""
        header = self.summary_table.horizontalHeader()

        # 第0列（序号）：Fixed模式，固定宽度
        header.setSectionResizeMode(0, QHeaderView.Interactive)

        # 第1列（代理名称）：Interactive模式，可拖动调整
        header.setSectionResizeMode(1, QHeaderView.Interactive)

        # 第2列（代理类型）：Interactive模式，可拖动调整
        header.setSectionResizeMode(2, QHeaderView.Interactive)

        # 第3列（IP）：Interactive模式，可拖动调整
        header.setSectionResizeMode(3, QHeaderView.Interactive)

        # 第4列（地理信息）：Interactive模式，可拖动调整
        header.setSectionResizeMode(4, QHeaderView.Interactive)

        # 第5列（用户）：Interactive模式，可拖动调整
        header.setSectionResizeMode(5, QHeaderView.Interactive)

        # 第6列（总连接数）：Fixed模式，固定宽度
        header.setSectionResizeMode(6, QHeaderView.Interactive)

        # 第7列（活跃连接）：Fixed模式，固定宽度
        header.setSectionResizeMode(7, QHeaderView.Interactive)

        # 第8列（发送数据量）：Interactive模式，可拖动调整
        header.setSectionResizeMode(8, QHeaderView.Interactive)

        # 第9列（接收数据量）：Interactive模式，可拖动调整
        header.setSectionResizeMode(9, QHeaderView.Interactive)

        # 第10列（总数据量）：Interactive模式，可拖动调整
        header.setSectionResizeMode(10, QHeaderView.Interactive)

        # 第11列（最后活跃）：Interactive模式，可拖动调整
        header.setSectionResizeMode(11, QHeaderView.Interactive)

        # 设置最小宽度，防止列被压缩得太小
        for col in range(self.summary_table.columnCount()):
            header.setMinimumSectionSize(60)

    def set_summary_initial_column_widths(self):
        """设置汇总表格初始列宽，使表格看起来更美观"""
        try:
            # 获取表格当前宽度
            table_width = self.summary_table.viewport().width() if self.summary_table.viewport() else self.summary_table.width()

            if table_width <= 0:
                # 如果表格还未显示，使用默认宽度
                table_width = 1200  # 默认宽度

            # # 为固定列预留宽度
            # fixed_width = 50 + 80 + 80  # 序号(50) + 总连接数(80) + 活跃连接(80)

            # 剩余宽度分配给其他可调整的列
            # remaining_width = table_width - fixed_width - 30  # 减去一些边距
            remaining_width = table_width - 30

            if remaining_width <= 0:
                # 如果窗口太小，使用最小宽度
                remaining_width = 900


            # 计算宽度
            number_width = int(remaining_width * 0.04)
            proxy_name_width = int(remaining_width * 0.08)
            protocol_width = int(remaining_width * 0.06)
            ip_width = int(remaining_width * 0.11)
            country_width = int(remaining_width * 0.13)
            user_width = int(remaining_width * 0.07)
            connection_width = int(remaining_width * 0.06)
            received_width = int(remaining_width * 0.08)
            sent_width = int(remaining_width * 0.08)
            total_width = int(remaining_width * 0.08)
            last_active_width = remaining_width - (number_width + proxy_name_width + protocol_width + ip_width +
                                                country_width + user_width + connection_width*2 + received_width +
                                                sent_width + total_width)

            # 设置宽度（确保最小宽度）
            self.summary_table.setColumnWidth(0, max(40, number_width))  # 序号
            self.summary_table.setColumnWidth(1, max(90, proxy_name_width))    # 代理名称
            self.summary_table.setColumnWidth(2, max(60, protocol_width))       # 代理类型
            self.summary_table.setColumnWidth(3, max(100, ip_width))            # IP
            self.summary_table.setColumnWidth(4, max(120, country_width))        # 地理信息
            self.summary_table.setColumnWidth(5, max(70, user_width))           # 用户
            self.summary_table.setColumnWidth(6, max(60, connection_width))  # 总连接数
            self.summary_table.setColumnWidth(7, max(60, connection_width))  # 活跃连接
            self.summary_table.setColumnWidth(8, max(100, sent_width))      # 发送数据量
            self.summary_table.setColumnWidth(9, max(100, received_width))     # 接收数据量
            self.summary_table.setColumnWidth(10, max(100, total_width))        # 总数据量
            self.summary_table.setColumnWidth(11, max(110, last_active_width))  # 最后活跃

        except Exception as e:
            logger.error(f"设置汇总表格初始列宽失败: {e}")
            # 设置备用的固定宽度
            self.summary_table.setColumnWidth(0, 50)   # 序号
            self.summary_table.setColumnWidth(1, 200)  # 代理名称
            self.summary_table.setColumnWidth(2, 80)   # 代理类型
            self.summary_table.setColumnWidth(3, 150)  # IP
            self.summary_table.setColumnWidth(4, 100)  # 地理信息
            self.summary_table.setColumnWidth(5, 100)  # 用户
            self.summary_table.setColumnWidth(6, 80)   # 总连接数
            self.summary_table.setColumnWidth(7, 80)   # 活跃连接
            self.summary_table.setColumnWidth(8, 120)  # 接收数据量
            self.summary_table.setColumnWidth(9, 120)  # 发送数据量
            self.summary_table.setColumnWidth(10, 120) # 总数据量
            self.summary_table.setColumnWidth(11, 150) # 最后活跃

    def create_monitor_tab(self):
        """创建实时监控标签页 - 使用混合模式列宽管理"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ========== 实时连接表格 ==========
        self.monitor_table = QTableWidget()
        self.monitor_table.setColumnCount(12)

        # 禁用选中高亮
        self.monitor_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.monitor_table.setFocusPolicy(Qt.NoFocus)

        headers = [
            "连接ID", "时间", "代理", "IP", "地理信息",
            "用户", "协议", "时长(s)", "发送流量", "接收流量", "发送速度", "接收速度"
        ]
        self.monitor_table.setHorizontalHeaderLabels(headers)

        self.monitor_table.verticalHeader().setVisible(False)
        self.monitor_table.setAlternatingRowColors(True)
        self.monitor_table.setSortingEnabled(True)

        # 设置列宽策略 - 混合模式
        self.setup_monitor_column_resize_modes()

        # 设置初始列宽（延迟执行，确保表格已显示）
        QTimer.singleShot(100, self.set_monitor_initial_column_widths)

        # 启用排序功能
        self.monitor_table.setSortingEnabled(True)

        # 设置表格样式
        self.monitor_table.setStyleSheet("""
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

        layout.addWidget(self.monitor_table, 1)

        # ========== 筛选汇总信息区域 ==========
        summary_frame = QFrame()
        summary_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        summary_layout = QGridLayout(summary_frame)
        summary_layout.setSpacing(10)
        summary_layout.setContentsMargins(10, 10, 10, 10)

        # 汇总标题
        summary_title = QLabel("📊 筛选汇总信息")
        summary_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        summary_layout.addWidget(summary_title, 0, 0, 1, 5)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        summary_layout.addWidget(separator, 1, 0, 1, 5)

        # 第1行：连接统计（4项 + 标签，共5项，分布在5列）
        row = 2
        summary_layout.addWidget(QLabel("🔗 连接统计:"), row, 0)

        self.realtime_connections_label = QLabel("连接数: 0")
        self.realtime_connections_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_connections_label, row, 1)

        self.realtime_avg_duration_label = QLabel("平均时长: 0.0s")
        self.realtime_avg_duration_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_avg_duration_label, row, 2)

        self.realtime_min_duration_label = QLabel("最短时长: 0.0s")
        self.realtime_min_duration_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_min_duration_label, row, 3)

        self.realtime_max_duration_label = QLabel("最长时长: 0.0s")
        self.realtime_max_duration_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_max_duration_label, row, 4)

        # 第2行：流量统计（4项 + 标签，共5项，分布在5列）
        row += 1
        summary_layout.addWidget(QLabel("📈 流量统计:"), row, 0)

        self.realtime_sent_label = QLabel("发送总量: 0 B")
        self.realtime_sent_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_sent_label, row, 1)

        self.realtime_received_label = QLabel("接收总量: 0 B")
        self.realtime_received_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_received_label, row, 2)

        self.realtime_total_traffic_label = QLabel("总流量: 0 B")
        self.realtime_total_traffic_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_total_traffic_label, row, 3)

        # 第4列留空，让第4项显示在第4列
        summary_layout.addWidget(QLabel(""), row, 4)

        # 第3行：速度统计（4项 + 标签，共5项，分布在5列）
        row += 1
        summary_layout.addWidget(QLabel("⚡ 速度统计:"), row, 0)

        self.realtime_avg_send_speed_label = QLabel("平均发送: 0 B/s")
        self.realtime_avg_send_speed_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_avg_send_speed_label, row, 1)

        self.realtime_avg_receive_speed_label = QLabel("平均接收: 0 B/s")
        self.realtime_avg_receive_speed_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_avg_receive_speed_label, row, 2)

        self.realtime_max_send_speed_label = QLabel("最高发送: 0 B/s")
        self.realtime_max_send_speed_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_max_send_speed_label, row, 3)

        self.realtime_max_receive_speed_label = QLabel("最高接收: 0 B/s")
        self.realtime_max_receive_speed_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        summary_layout.addWidget(self.realtime_max_receive_speed_label, row, 4)

        # 第4行：筛选信息（1项，占第1列）
        row += 1
        # summary_layout.addWidget(QLabel("🔍 筛选条件:"), row, 0)

        self.realtime_filter_label = QLabel("筛选条件: 无筛选")
        self.realtime_filter_label.setStyleSheet("color: #7f8c8d; font-style: italic; font-size: 12px;")
        summary_layout.addWidget(self.realtime_filter_label, row, 0, 1, 4)  # 跨4列

        # 添加弹性空间使布局更均匀
        for col in range(5):
            summary_layout.setColumnStretch(col, 1)

        layout.addWidget(summary_frame)

        return widget


    def setup_monitor_column_resize_modes(self):
        """设置监控表格的调整模式 - 混合模式"""
        header = self.monitor_table.horizontalHeader()

        # 第0列（连接ID）：Interactive模式，可拖动调整
        header.setSectionResizeMode(0, QHeaderView.Interactive)

        # 第1列（时间）：Fixed模式，固定宽度
        header.setSectionResizeMode(1, QHeaderView.Interactive)

        # 第2列（代理）：Interactive模式，可拖动调整
        header.setSectionResizeMode(2, QHeaderView.Interactive)

        # 第3列（IP）：Interactive模式，可拖动调整
        header.setSectionResizeMode(3, QHeaderView.Interactive)

        # 第4列（地理信息）：Fixed模式，固定宽度
        header.setSectionResizeMode(4, QHeaderView.Interactive)

        # 第5列（用户）：Interactive模式，可拖动调整
        header.setSectionResizeMode(5, QHeaderView.Interactive)

        # 第6列（协议）：Fixed模式，固定宽度
        header.setSectionResizeMode(6, QHeaderView.Interactive)

        # 第7列（时长）：Fixed模式，固定宽度
        header.setSectionResizeMode(7, QHeaderView.Interactive)

        # 第8列（发送流量）：Interactive模式，可拖动调整
        header.setSectionResizeMode(8, QHeaderView.Interactive)

        # 第9列（接收流量）：Interactive模式，可拖动调整
        header.setSectionResizeMode(9, QHeaderView.Interactive)

        # 第10列（发送速度）：Interactive模式，可拖动调整
        header.setSectionResizeMode(10, QHeaderView.Interactive)

        # 第11列（接收速度）：Interactive模式，可拖动调整
        header.setSectionResizeMode(11, QHeaderView.Interactive)

        # 设置最小宽度，防止列被压缩得太小
        for col in range(self.monitor_table.columnCount()):
            header.setMinimumSectionSize(60)

    def set_monitor_initial_column_widths(self):
        """设置监控表格初始列宽，使表格看起来更美观"""
        try:
            # 获取表格当前宽度
            table_width = self.monitor_table.viewport().width() if self.monitor_table.viewport() else self.monitor_table.width()

            if table_width <= 0:
                # 如果表格还未显示，使用默认宽度
                table_width = 1200  # 默认宽度

            # 剩余宽度分配给其他可调整的列
            remaining_width = table_width - 30

            if remaining_width <= 0:
                # 如果窗口太小，使用最小宽度
                remaining_width = 900


            # 计算宽度
            time_width = int(remaining_width * 0.08)
            proxy_width = int(remaining_width * 0.06)
            ip_width = int(remaining_width * 0.11)
            country_width = int(remaining_width * 0.12)
            user_width = int(remaining_width * 0.07)
            protocol_width = int(remaining_width * 0.06)
            time_length_width = int(remaining_width * 0.06)
            sent_width = int(remaining_width * 0.07)
            received_width = int(remaining_width * 0.07)
            send_speed_width = int(remaining_width * 0.07)
            receive_speed_width = int(remaining_width * 0.07)
            conn_id_width = remaining_width - ( time_width + proxy_width + ip_width + country_width +
                                                user_width + protocol_width + time_length_width + sent_width + received_width +
                                                send_speed_width + receive_speed_width)

            # 设置宽度（确保最小宽度）
            self.monitor_table.setColumnWidth(0, max(130, conn_id_width))      # 连接ID
            self.monitor_table.setColumnWidth(1, max(90, time_width))    # 时间
            self.monitor_table.setColumnWidth(2, max(90, proxy_width))        # 代理
            self.monitor_table.setColumnWidth(3, max(120, ip_width))          # IP
            self.monitor_table.setColumnWidth(4, max(130, country_width))     # 地理信息
            self.monitor_table.setColumnWidth(5, max(90, user_width))        # 用户
            self.monitor_table.setColumnWidth(6, max(70, protocol_width))     # 协议
            self.monitor_table.setColumnWidth(7, max(80, time_length_width))   # 时长
            self.monitor_table.setColumnWidth(8, max(90, sent_width))         # 发送流量
            self.monitor_table.setColumnWidth(9, max(90, received_width))     # 接收流量
            self.monitor_table.setColumnWidth(10, max(90, send_speed_width))   # 发送速度
            self.monitor_table.setColumnWidth(11, max(90, receive_speed_width))# 接收速度

        except Exception as e:
            logger.error(f"设置监控表格初始列宽失败: {e}")
            # 设置备用的固定宽度
            self.monitor_table.setColumnWidth(0, 120)  # 连接ID
            self.monitor_table.setColumnWidth(1, 100)  # 时间
            self.monitor_table.setColumnWidth(2, 200)  # 代理
            self.monitor_table.setColumnWidth(3, 150)  # IP
            self.monitor_table.setColumnWidth(4, 80)   # 地理信息
            self.monitor_table.setColumnWidth(5, 100)  # 用户
            self.monitor_table.setColumnWidth(6, 80)   # 协议
            self.monitor_table.setColumnWidth(7, 80)   # 时长
            self.monitor_table.setColumnWidth(8, 120)  # 发送流量
            self.monitor_table.setColumnWidth(9, 120)  # 接收流量
            self.monitor_table.setColumnWidth(10, 100) # 发送速度
            self.monitor_table.setColumnWidth(11, 100) # 接收速度

    def resizeEvent(self, event):
        """窗口大小改变时重新调整列宽"""
        super().resizeEvent(event)

        # 延迟重新计算列宽，确保表格已更新
        if hasattr(self, 'summary_table'):
            QTimer.singleShot(50, self.set_summary_initial_column_widths)

        if hasattr(self, 'monitor_table'):
            QTimer.singleShot(50, self.set_monitor_initial_column_widths)

    def create_control_bar(self, parent_layout):
        """创建控制栏"""
        frame = QFrame()
        layout = QHBoxLayout(frame)

        # 状态信息
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_data)
        layout.addWidget(self.refresh_btn)

        # 导出按钮
        self.export_btn = QPushButton("导出")
        self.export_btn.clicked.connect(self.export_data)
        layout.addWidget(self.export_btn)

        # 清空按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_data)
        layout.addWidget(self.clear_btn)

        parent_layout.addWidget(frame)

    # ========== 标签页切换事件 ==========

    def on_tab_changed(self, index):
        """标签页切换事件"""
        if index == 0:  # 汇总信息标签
            # 启用汇总页筛选，禁用实时筛选
            self.time_combo.setEnabled(True)
            self.group_combo.setEnabled(True)
            self.realtime_filter_combo.setEnabled(False)
            self.realtime_filter_value_combo.setEnabled(False)

            # 显示日期范围标签
            self.date_range_label.setVisible(True)
            self.update_date_range_label()
            self.remark_label.setText("📢 流量统计为代理与客户端之间的流量 \n发送=向客户端发送 | 接收=从客户端接收")

            self.status_label.setText("已启用时间范围和分组筛选")
            self.load_summary_table()

        elif index == 1:  # 实时连接标签
            # 启用实时筛选
            self.time_combo.setEnabled(False)
            self.group_combo.setEnabled(False)
            self.realtime_filter_combo.setEnabled(True)
            self.realtime_filter_value_combo.setEnabled(True)

            # 隐藏日期范围标签，更新备注文本
            self.date_range_label.setText(" ")  # 用空格占位，保持布局稳定
            self.remark_label.setText("📢 流量统计为代理与客户端之间的流量 \n发送=向客户端发送 | 接收=从客户端接收")

            # 更新实时筛选的值列表
            self.update_realtime_filter_values()

            self.status_label.setText("实时连接显示当前活跃连接")
            self.load_monitor_table()

    # ========== 筛选事件处理 ==========

    def on_time_filter_changed(self, text: str):
        """时间筛选改变"""
        self.time_range = text

        if self.tab_widget.currentIndex() == 0:
            # 更新日期范围显示
            self.update_date_range_label()

            # 清空缓存，重新加载
            self.summary_data_cache = None
            self.active_counts_cache = None
            self.load_summary_table()

    def on_group_changed(self, text: str):
        """分组方式改变"""
        self.filter_type = text
        if self.tab_widget.currentIndex() == 0:
            # 清空缓存，重新加载
            self.summary_data_cache = None
            self.load_summary_table()

            # 更新右上角日期范围显示
            self.update_date_range_label()

    def on_realtime_filter_changed(self, text: str):
        """实时筛选方式改变"""
        self.realtime_filter_type = text

        # 更新筛选值下拉框
        self.update_realtime_filter_values()

        # 刷新表格
        if self.tab_widget.currentIndex() == 1:
            self.load_monitor_table()

    def on_realtime_filter_value_changed(self, text: str):
        """实时筛选值改变"""
        self.realtime_filter_value = text
        if self.tab_widget.currentIndex() == 1:
            self.load_monitor_table()

    def update_realtime_filter_values(self):
        """更新实时筛选的值列表"""
        if self.realtime_filter_type == "全部连接":
            self.realtime_filter_value_combo.blockSignals(True)
            self.realtime_filter_value_combo.clear()
            self.realtime_filter_value_combo.addItem("全部")
            self.realtime_filter_value_combo.setCurrentText("全部")
            self.realtime_filter_value_combo.blockSignals(False)
            return

        try:
            connections = self.stats_manager.get_active_connection_details()
            if not connections:
                self.realtime_filter_value_combo.blockSignals(True)
                self.realtime_filter_value_combo.clear()
                self.realtime_filter_value_combo.addItem("全部")
                self.realtime_filter_value_combo.setCurrentText("全部")
                self.realtime_filter_value_combo.blockSignals(False)
                return

            values = set()
            for conn in connections:
                if self.realtime_filter_type == "按代理":
                    value = conn.get('proxy', '未命名代理')
                elif self.realtime_filter_type == "按IP":
                    value = conn.get('ip', '未知')
                elif self.realtime_filter_type == "按地理信息":
                    value = conn.get('country', '未知')
                elif self.realtime_filter_type == "按用户":
                    value = conn.get('user', '匿名')
                elif self.realtime_filter_type == "按协议":
                    value = conn.get('protocol', '未知')
                else:
                    value = ""

                if value and value != '-':
                    values.add(value)

            all_items = ["全部"] + sorted(values)
            current_value = self.realtime_filter_value_combo.currentText()

            if current_value not in all_items:
                current_value = "全部"
                self.realtime_filter_value = "全部"

            self.realtime_filter_value_combo.blockSignals(True)
            self.realtime_filter_value_combo.clear()
            for item in all_items:
                self.realtime_filter_value_combo.addItem(item)

            self.realtime_filter_value_combo.setCurrentText(current_value)

            # 根据内容调整下拉框宽度
            if values:
                max_length = max(len(str(item)) for item in values)
                # 设置一个合适的宽度，每个字符大约6-8像素
                self.realtime_filter_value_combo.setMinimumWidth(min(max_length * 8 + 40, 400))

            self.realtime_filter_value_combo.blockSignals(False)

        except Exception as e:
            logger.error(f"更新实时筛选值失败: {e}")
            self.realtime_filter_value_combo.blockSignals(True)
            self.realtime_filter_value_combo.clear()
            self.realtime_filter_value_combo.addItem("全部")
            self.realtime_filter_value_combo.setCurrentText("全部")
            self.realtime_filter_value = "全部"
            self.realtime_filter_value_combo.blockSignals(False)

    def update_date_range_label(self):
        """更新日期范围标签"""
        try:
            today = datetime.now()

            if self.time_range == "今日":
                date_str = today.strftime("%Y-%m-%d")
                self.date_range_label.setText(f"日期范围: {date_str}")

            elif self.time_range == "昨日":
                yesterday = today - timedelta(days=1)
                date_str = yesterday.strftime("%Y-%m-%d")
                self.date_range_label.setText(f"日期范围: {date_str}")

            elif self.time_range == "最近7天":
                start_date = today - timedelta(days=6)  # 最近7天包括今天
                start_str = start_date.strftime("%Y-%m-%d")
                today_str = today.strftime("%Y-%m-%d")
                self.date_range_label.setText(f"日期范围: {start_str} 至 {today_str}")

            elif self.time_range == "最近30天":
                start_date = today - timedelta(days=29)  # 最近30天包括今天
                start_str = start_date.strftime("%Y-%m-%d")
                today_str = today.strftime("%Y-%m-%d")
                self.date_range_label.setText(f"日期范围: {start_str} 至 {today_str}")

            elif self.time_range == "全部":
                # 获取所有有记录的日期
                all_dates = self.stats_manager.get_all_dates()
                if all_dates:
                    all_dates.sort()  # 按日期排序
                    earliest = all_dates[0]
                    latest = all_dates[-1]
                    self.date_range_label.setText(f"日期范围: {earliest} 至 {latest}")
                else:
                    self.date_range_label.setText("日期范围: 无记录")

        except Exception as e:
            logger.error(f"更新日期范围标签失败: {e}")
            self.date_range_label.setText("日期范围: 未知")

    # ========== 数据处理方法 ==========

    def load_data(self):
        """加载数据"""
        try:
            self.load_summary_table()
            self.load_monitor_table()
            self.status_label.setText("数据加载完成")
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            self.status_label.setText(f"错误: {str(e)}")

    def load_summary_table(self):
        """加载汇总表格并更新统计信息"""
        try:
            # 获取活跃连接详情和活跃计数
            active_connections = self.stats_manager.get_active_connection_details()
            self.active_counts_cache = self._count_active_connections(active_connections)

            # 加载表格数据
            data = self.get_summary_data()

            # 保存滚动位置
            scroll_value = self.summary_table.verticalScrollBar().value()

            # 禁用排序防止自动排序
            self.summary_table.setSortingEnabled(False)

            self.summary_table.setRowCount(len(data))

            for i, item in enumerate(data):
                # 序号
                index_item = QTableWidgetItem(str(i + 1))
                index_item.setTextAlignment(Qt.AlignCenter)
                index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 0, index_item)

                # 代理名称
                proxy_name = item.get('proxy_name', '-')
                proxy_item = QTableWidgetItem(proxy_name)
                proxy_item.setFlags(proxy_item.flags() & ~Qt.ItemIsEditable)
                proxy_item.setToolTip(proxy_name)
                self.summary_table.setItem(i, 1, proxy_item)

                # 代理类型
                protocol = item.get('protocol', '-')
                protocol_item = QTableWidgetItem(protocol)
                protocol_item.setFlags(protocol_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 2, protocol_item)

                # IP
                ip = item.get('ip', '-')
                ip_item = QTableWidgetItem(ip)
                ip_item.setFlags(ip_item.flags() & ~Qt.ItemIsEditable)
                ip_item.setToolTip(ip)
                self.summary_table.setItem(i, 3, ip_item)

                # 地理信息
                country = item.get('country', '-')
                country_item = QTableWidgetItem(country)
                country_item.setFlags(country_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 4, country_item)

                # 用户
                user = item.get('user', '-')
                user_item = QTableWidgetItem(user)
                user_item.setFlags(user_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 5, user_item)

                # 总连接数
                connections = item.get('connections', 0)
                connections_item = QTableWidgetItem(str(connections))
                connections_item.setFlags(connections_item.flags() & ~Qt.ItemIsEditable)
                connections_item.setTextAlignment(Qt.AlignRight)
                self.summary_table.setItem(i, 6, connections_item)

                # 活跃连接数
                if self.time_range == "今日":
                    active_count = self._get_item_active_count(item)
                    active_item = QTableWidgetItem(str(active_count))
                    active_item.setFlags(active_item.flags() & ~Qt.ItemIsEditable)
                    active_item.setTextAlignment(Qt.AlignRight)
                    if active_count > 0:
                        active_item.setForeground(QColor("#d32f2f"))
                    self.summary_table.setItem(i, 7, active_item)
                else:
                    self.summary_table.setItem(i, 7, QTableWidgetItem("-"))

                # 第8列：发送数据量
                bytes_sent = item.get('bytes_sent', 0)
                sent_item = QTableWidgetItem(self.format_bytes(bytes_sent))
                sent_item.setFlags(sent_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 8, sent_item)

                # 第9列：接收数据量
                bytes_received = item.get('bytes_received', 0)
                received_item = QTableWidgetItem(self.format_bytes(bytes_received))
                received_item.setFlags(received_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 9, received_item)
                # ==== 修改结束 ====

                # 总数据量（不变）
                total_bytes = bytes_sent + bytes_received
                total_item = QTableWidgetItem(self.format_bytes(total_bytes))
                total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 10, total_item)

                # 最后活跃时间
                last_active = item.get('last_active', '-')
                if isinstance(last_active, (int, float)) and last_active > 0:
                    last_active_str = datetime.fromtimestamp(last_active).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_active_str = "-"

                last_item = QTableWidgetItem(last_active_str)
                last_item.setFlags(last_item.flags() & ~Qt.ItemIsEditable)
                self.summary_table.setItem(i, 11, last_item)

            # 恢复滚动位置
            self.summary_table.verticalScrollBar().setValue(scroll_value)

            # 重新启用排序
            self.summary_table.setSortingEnabled(True)

            # 更新统计信息区域
            self.update_summary_stats()

        except Exception as e:
            logger.error(f"加载汇总表格失败: {e}")

    def update_summary_stats(self):
        """更新汇总页的统计信息"""
        try:
            # 获取当前筛选的数据
            data = self.get_summary_data()

            if not data:
                self.clear_summary_stats()
                return

            # 获取当前活跃连接数
            active_connections = self.stats_manager.get_active_connection_details()
            active_count = len(active_connections)

            # 计算汇总数据
            total_connections = 0
            total_sent = 0
            total_received = 0
            total_failed = 0

            all_ips = set()
            all_proxies = set()
            all_users = set()
            all_countries = set()

            for item in data:
                total_connections += item.get('connections', 0)
                total_sent += item.get('bytes_sent', 0)
                total_received += item.get('bytes_received', 0)

                # 收集唯一值
                ip = item.get('ip', '')
                if ip and ip != '-':
                    all_ips.add(ip)

                proxy = item.get('proxy_name', '')
                if proxy and proxy != '-':
                    all_proxies.add(proxy)

                user = item.get('user', '')
                if user and user != '-':
                    all_users.add(user)

                country = item.get('country', '')
                if country and country != '-':
                    all_countries.add(country)

            # 获取今日统计 - 直接从StatsManager获取
            today_stats = self.stats_manager.get_realtime_stats()
            today_connections = today_stats.get('today_connections', 0) if today_stats else 0
            today_sent = today_stats.get('today_bytes_sent', 0) if today_stats else 0
            today_received = today_stats.get('today_bytes_received', 0) if today_stats else 0
            today_traffic = today_sent + today_received

            # 计算失败连接数 - 需要从每日统计中获取
            stats_dict = self._get_stats_by_time_range()
            for stats in stats_dict.values():
                total_failed += stats.failed_connections

            # 更新显示
            self.summary_total_connections_label.setText(f"总连接数: {total_connections}")
            self.summary_active_connections_label.setText(f"活跃连接: {active_count}")
            self.summary_today_connections_label.setText(f"今日连接: {today_connections}")
            self.summary_failed_connections_label.setText(f"失败连接: {total_failed}")

            self.summary_total_sent_label.setText(f"总发送: {self.format_bytes(total_sent)}")
            self.summary_total_received_label.setText(f"总接收: {self.format_bytes(total_received)}")
            self.summary_total_traffic_label.setText(f"总流量: {self.format_bytes(total_sent + total_received)}")
            self.summary_today_traffic_label.setText(f"今日流量: {self.format_bytes(today_traffic)}")

            self.summary_unique_ips_label.setText(f"唯一IP: {len(all_ips)}")
            self.summary_unique_proxies_label.setText(f"唯一代理: {len(all_proxies)}")
            self.summary_unique_users_label.setText(f"唯一用户: {len(all_users)}")
            self.summary_unique_countries_label.setText(f"唯一位置: {len(all_countries)}")

            self.summary_time_range_label.setText(f"时间范围: {self.time_range} | 数据条数: {len(data)}")

        except Exception as e:
            logger.error(f"更新汇总统计失败: {e}")

    def clear_summary_stats(self):
        """清空汇总统计信息"""
        self.summary_total_connections_label.setText("总连接数: 0")
        self.summary_active_connections_label.setText("活跃连接: 0")
        self.summary_today_connections_label.setText("今日连接: 0")
        self.summary_failed_connections_label.setText("失败连接: 0")

        self.summary_total_sent_label.setText("总发送: 0 B")
        self.summary_total_received_label.setText("总接收: 0 B")
        self.summary_total_traffic_label.setText("总流量: 0 B")
        self.summary_today_traffic_label.setText("今日流量: 0 B")

        self.summary_unique_ips_label.setText("唯一IP: 0")
        self.summary_unique_proxies_label.setText("唯一代理: 0")
        self.summary_unique_users_label.setText("唯一用户: 0")
        self.summary_unique_countries_label.setText("唯一位置: 0")

        self.summary_time_range_label.setText(f"时间范围: {self.time_range} | 数据条数: 0")

    def _count_active_connections(self, connections):
        """统计活跃连接"""
        counts = {
            'by_proxy': defaultdict(int),
            'by_ip': defaultdict(int),
            'by_country': defaultdict(int),
            'by_user': defaultdict(int),
            'by_protocol': defaultdict(int),
            'by_combined': defaultdict(int)
        }

        for conn in connections:
            proxy = conn.get('proxy', '未命名代理')
            ip = conn.get('ip', '未知')
            country = conn.get('country', '未知')
            user = conn.get('user', '无认证')
            protocol = conn.get('protocol', '未知').lower()
            combined_key = f"{proxy}|{ip}|{user}|{protocol}|{country}"

            counts['by_proxy'][proxy] += 1
            counts['by_ip'][ip] += 1
            counts['by_country'][country] += 1
            counts['by_user'][user] += 1
            counts['by_protocol'][protocol] += 1
            counts['by_combined'][combined_key] += 1

        return counts

    def _get_item_active_count(self, item):
        """获取项目的活跃连接数"""
        if not self.active_counts_cache:
            return 0

        try:
            if self.filter_type == "总体":
                proxy_name = item.get('proxy_name', '')
                ip = item.get('ip', '')
                user = item.get('user', '')
                protocol = item.get('protocol', '').lower()
                country = item.get('country', '')
                combined_key = f"{proxy_name}|{ip}|{user}|{protocol}|{country}"
                return self.active_counts_cache['by_combined'].get(combined_key, 0)
            elif self.filter_type == "代理名称":
                proxy_name = item.get('proxy_name', '')
                return self.active_counts_cache['by_proxy'].get(proxy_name, 0)
            elif self.filter_type == "代理类型":
                protocol = item.get('protocol', '').lower()
                return self.active_counts_cache['by_protocol'].get(protocol, 0)
            elif self.filter_type == "IP":
                ip = item.get('ip', '')
                return self.active_counts_cache['by_ip'].get(ip, 0)
            elif self.filter_type == "地理信息":
                country = item.get('country', '')
                return self.active_counts_cache['by_country'].get(country, 0)
            elif self.filter_type == "用户":
                user = item.get('user', '')
                return self.active_counts_cache['by_user'].get(user, 0)

        except Exception as e:
            logger.error(f"获取活跃连接数失败: {e}")

        return 0

    def load_monitor_table(self):
        """加载监控表格 - 支持筛选并显示汇总信息"""
        try:
            all_connections = self.stats_manager.get_active_connection_details()
            filtered_connections = self.filter_realtime_connections(all_connections)

            # 保存滚动位置
            scroll_value = self.monitor_table.verticalScrollBar().value()

            # 禁用排序防止自动排序
            self.monitor_table.setSortingEnabled(False)

            self.monitor_table.setRowCount(len(filtered_connections))

            for i, conn in enumerate(filtered_connections):
                # 连接ID
                conn_id = conn.get('id', '-')
                id_item = QTableWidgetItem(conn_id[:20])
                id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
                id_item.setToolTip(conn_id)
                self.monitor_table.setItem(i, 0, id_item)

                # 时间
                time_str = conn.get('time', '-')
                time_item = QTableWidgetItem(time_str)
                time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 1, time_item)

                # 代理
                proxy = conn.get('proxy', '-')
                proxy_item = QTableWidgetItem(proxy)
                proxy_item.setFlags(proxy_item.flags() & ~Qt.ItemIsEditable)
                proxy_item.setToolTip(proxy)
                self.monitor_table.setItem(i, 2, proxy_item)

                # IP
                ip = conn.get('ip', '-')
                ip_item = QTableWidgetItem(ip)
                ip_item.setFlags(ip_item.flags() & ~Qt.ItemIsEditable)
                ip_item.setToolTip(ip)
                self.monitor_table.setItem(i, 3, ip_item)

                # 地理信息
                country = conn.get('country', '-')
                country_item = QTableWidgetItem(country)
                country_item.setFlags(country_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 4, country_item)

                # 用户
                user = conn.get('user', '匿名')
                user_item = QTableWidgetItem(user)
                user_item.setFlags(user_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 5, user_item)

                # 协议
                protocol = conn.get('protocol', '-')
                protocol_item = QTableWidgetItem(protocol)
                protocol_item.setFlags(protocol_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 6, protocol_item)

                # 时长
                duration = conn.get('duration', 0)
                duration_item = QTableWidgetItem(f"{duration:.1f}")
                duration_item.setFlags(duration_item.flags() & ~Qt.ItemIsEditable)
                duration_item.setTextAlignment(Qt.AlignRight)
                self.monitor_table.setItem(i, 7, duration_item)

                # 发送流量
                bytes_sent = conn.get('bytes_sent', 0)
                sent_item = QTableWidgetItem(self.format_bytes(bytes_sent))
                sent_item.setFlags(sent_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 8, sent_item)

                # 接收流量
                bytes_received = conn.get('bytes_received', 0)
                received_item = QTableWidgetItem(self.format_bytes(bytes_received))
                received_item.setFlags(received_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 9, received_item)

                # 发送速度
                send_speed = conn.get('send_speed', 0)
                send_speed_item = QTableWidgetItem(f"{self.format_bytes(send_speed)}/s")
                send_speed_item.setFlags(send_speed_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 10, send_speed_item)

                # 接收速度
                receive_speed = conn.get('receive_speed', 0)
                receive_speed_item = QTableWidgetItem(f"{self.format_bytes(receive_speed)}/s")
                receive_speed_item.setFlags(receive_speed_item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, 11, receive_speed_item)

            # 恢复滚动位置
            self.monitor_table.verticalScrollBar().setValue(scroll_value)

            # 重新启用排序
            self.monitor_table.setSortingEnabled(True)

            self.update_realtime_summary(filtered_connections, all_connections)

        except Exception as e:
            logger.error(f"加载监控表格失败: {e}")
            self.monitor_table.setRowCount(0)
            self.clear_realtime_summary()

    def filter_realtime_connections(self, connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """筛选实时连接"""
        if not connections:
            return []

        if self.realtime_filter_type == "全部连接" or self.realtime_filter_value == "全部":
            return connections

        filtered = []
        filter_value = self.realtime_filter_value

        for conn in connections:
            match = False

            if self.realtime_filter_type == "按代理":
                if conn.get('proxy', '未命名代理') == filter_value:
                    match = True
            elif self.realtime_filter_type == "按IP":
                if conn.get('ip', '未知') == filter_value:
                    match = True
            elif self.realtime_filter_type == "按地理信息":
                if conn.get('country', '未知') == filter_value:
                    match = True
            elif self.realtime_filter_type == "按用户":
                if conn.get('user', '匿名') == filter_value:
                    match = True
            elif self.realtime_filter_type == "按协议":
                if conn.get('protocol', '未知') == filter_value:
                    match = True

            if match:
                filtered.append(conn)

        return filtered

    def calculate_realtime_summary(self, connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算实时连接汇总信息 - 修复错误：使用正确的字段名"""
        if not connections:
            return {
                'connection_count': 0,
                'avg_duration': 0,
                'max_duration': 0,
                'min_duration': 0,
                'total_sent': 0,
                'total_received': 0,
                'avg_send_speed': 0,
                'avg_receive_speed': 0,
                'max_send_speed': 0,
                'max_receive_speed': 0,
                'filter_condition': "无"
            }

        total_sent = 0
        total_received = 0
        durations = []
        send_speeds = []
        receive_speeds = []
        max_send_speed = 0
        max_receive_speed = 0

        for conn in connections:
            sent = conn.get('bytes_sent', 0)
            received = conn.get('bytes_received', 0)
            total_sent += sent
            total_received += received

            duration = conn.get('duration', 0)
            if duration > 0:
                durations.append(duration)

            send_speed = conn.get('send_speed', 0)
            receive_speed = conn.get('receive_speed', 0)

            if send_speed > 0:
                send_speeds.append(send_speed)
                max_send_speed = max(max_send_speed, send_speed)

            if receive_speed > 0:
                receive_speeds.append(receive_speed)
                max_receive_speed = max(max_receive_speed, receive_speed)

        avg_duration = sum(durations) / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        min_duration = min(durations) if durations else 0

        avg_send_speed = sum(send_speeds) / len(send_speeds) if send_speeds else 0
        avg_receive_speed = sum(receive_speeds) / len(receive_speeds) if receive_speeds else 0

        filter_condition = "无筛选"
        if self.realtime_filter_type != "全部连接" and self.realtime_filter_value != "全部":
            filter_condition = f"{self.realtime_filter_type} - {self.realtime_filter_value}"

        return {
            'connection_count': len(connections),
            'avg_duration': avg_duration,
            'max_duration': max_duration,
            'min_duration': min_duration,
            'total_sent': total_sent,
            'total_received': total_received,
            'avg_send_speed': avg_send_speed,
            'avg_receive_speed': avg_receive_speed,
            'max_send_speed': max_send_speed,
            'max_receive_speed': max_receive_speed,
            'filter_condition': filter_condition
        }

    def update_realtime_summary(self, filtered_connections: List[Dict[str, Any]], all_connections: List[Dict[str, Any]]):
        """更新实时连接汇总信息"""
        try:
            summary = self.calculate_realtime_summary(filtered_connections)
            total_connections = len(all_connections)
            filtered_count = len(filtered_connections)

            # 连接统计
            self.realtime_connections_label.setText(f"连接数: {filtered_count}")
            self.realtime_avg_duration_label.setText(f"平均时长: {summary['avg_duration']:.1f}s")
            self.realtime_min_duration_label.setText(f"最短时长: {summary['min_duration']:.1f}s")
            self.realtime_max_duration_label.setText(f"最长时长: {summary['max_duration']:.1f}s")

            # 流量统计
            self.realtime_sent_label.setText(f"发送总量: {self.format_bytes(summary['total_sent'])}")
            self.realtime_received_label.setText(f"接收总量: {self.format_bytes(summary['total_received'])}")

            total_traffic = summary['total_sent'] + summary['total_received']
            self.realtime_total_traffic_label.setText(f"总流量: {self.format_bytes(total_traffic)}")

            # 速度统计
            self.realtime_avg_send_speed_label.setText(f"平均发送: {self.format_bytes(summary['avg_send_speed'])}/s")
            self.realtime_avg_receive_speed_label.setText(f"平均接收: {self.format_bytes(summary['avg_receive_speed'])}/s")
            self.realtime_max_send_speed_label.setText(f"最高发送: {self.format_bytes(summary['max_send_speed'])}/s")
            self.realtime_max_receive_speed_label.setText(f"最高接收: {self.format_bytes(summary['max_receive_speed'])}/s")

            # 筛选信息
            filter_text = f"筛选条件: {summary['filter_condition']}"
            if summary['filter_condition'] != "无筛选":
                filter_text += f" | 筛选出 {filtered_count}/{total_connections} 连接"
            self.realtime_filter_label.setText(filter_text)

            # 更新状态栏
            status_text = f"实时连接: {filtered_count} 个 (总计: {total_connections})"
            if summary['filter_condition'] != "无筛选":
                status_text += f" | {summary['filter_condition']}"
            self.status_label.setText(status_text)

        except Exception as e:
            logger.error(f"更新实时汇总信息失败: {e}")
            self.clear_realtime_summary()

    def clear_realtime_summary(self):
        """清空实时连接汇总信息"""
        # 连接统计
        self.realtime_connections_label.setText("连接数: 0")
        self.realtime_avg_duration_label.setText("平均时长: 0.0s")
        self.realtime_min_duration_label.setText("最短时长: 0.0s")
        self.realtime_max_duration_label.setText("最长时长: 0.0s")

        # 流量统计
        self.realtime_sent_label.setText("发送总量: 0 B")
        self.realtime_received_label.setText("接收总量: 0 B")
        self.realtime_total_traffic_label.setText("总流量: 0 B")

        # 速度统计
        self.realtime_avg_send_speed_label.setText("平均发送: 0 B/s")
        self.realtime_avg_receive_speed_label.setText("平均接收: 0 B/s")
        self.realtime_max_send_speed_label.setText("最高发送: 0 B/s")
        self.realtime_max_receive_speed_label.setText("最高接收: 0 B/s")

        # 筛选信息
        self.realtime_filter_label.setText("无筛选")

    # ========== 数据获取方法 ==========

    def get_summary_data(self) -> List[Dict[str, Any]]:
        """获取汇总数据 - 修复版"""
        # 使用缓存
        if self.summary_data_cache is not None:
            return self.summary_data_cache

        try:
            # 获取时间范围内的统计数据
            stats_dict = self._get_stats_by_time_range()
            if not stats_dict:
                self.summary_data_cache = []
                return self.summary_data_cache

            # 根据分组方式处理数据
            if self.filter_type == "总体":
                data = self._get_combined_data(stats_dict)
            elif self.filter_type == "代理名称":
                data = self._get_grouped_data(stats_dict, "proxy_name")
            elif self.filter_type == "代理类型":
                data = self._get_grouped_data(stats_dict, "protocol")
            elif self.filter_type == "IP":
                data = self._get_grouped_data(stats_dict, "ip")
            elif self.filter_type == "地理信息":
                data = self._get_grouped_data(stats_dict, "country")
            elif self.filter_type == "用户":
                data = self._get_grouped_data(stats_dict, "user")
            else:
                data = self._get_combined_data(stats_dict)

            # 排序：按连接数降序
            data.sort(key=lambda x: x.get('connections', 0), reverse=True)

            self.summary_data_cache = data
            return data

        except Exception as e:
            logger.error(f"获取汇总数据失败: {e}")
            self.summary_data_cache = []
            return self.summary_data_cache

    def _get_stats_by_time_range(self) -> Dict[str, DailyStats]:
        """根据时间范围获取统计 - 直接使用StatsManager的daily_stats数据"""
        try:
            if not hasattr(self.stats_manager, 'daily_stats'):
                logger.error("StatsManager没有daily_stats属性")
                return {}

            # 获取所有可用的日期
            all_dates = list(self.stats_manager.daily_stats.keys())
            if not all_dates:
                return {}

            # 按日期排序（最新的在前面）
            all_dates.sort(reverse=True)

            today = datetime.now().strftime("%Y-%m-%d")
            stats_dict = {}

            if self.time_range == "今日":
                if today in self.stats_manager.daily_stats:
                    stats_dict[today] = self.stats_manager.daily_stats[today]

            elif self.time_range == "昨日":
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                if yesterday in self.stats_manager.daily_stats:
                    stats_dict[yesterday] = self.stats_manager.daily_stats[yesterday]

            elif self.time_range == "最近7天":
                for i in range(7):
                    date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                    if date in self.stats_manager.daily_stats:
                        stats_dict[date] = self.stats_manager.daily_stats[date]

            elif self.time_range == "最近30天":
                for i in range(30):
                    date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                    if date in self.stats_manager.daily_stats:
                        stats_dict[date] = self.stats_manager.daily_stats[date]

            elif self.time_range == "全部":
                # 使用所有数据
                stats_dict = self.stats_manager.daily_stats.copy()

            # logger.debug(f"获取到 {len(stats_dict)} 天的统计数据，时间范围: {self.time_range}")
            return stats_dict

        except Exception as e:
            logger.error(f"获取时间范围统计失败: {e}")
            return {}

    def _get_combined_data(self, stats_dict: Dict[str, DailyStats]) -> List[Dict[str, Any]]:
        """获取组合数据 - 修复版，基于DailyStats数据结构"""
        data = []

        try:
            # 汇总所有combined_stats
            combined_map = {}

            for date_str, stats in stats_dict.items():
                if not hasattr(stats, 'combined_stats') or not stats.combined_stats:
                    continue

                for combined_key, item_stats in stats.combined_stats.items():
                    if combined_key not in combined_map:
                        combined_map[combined_key] = {
                            'proxy_name': item_stats.get('proxy_name', '未命名代理'),
                            'protocol': item_stats.get('protocol', '未知').upper(),
                            'ip': item_stats.get('ip', '未知'),
                            'country': item_stats.get('country', '未知'),
                            'user': item_stats.get('user', '无认证'),
                            'connections': 0,
                            'bytes_received': 0,
                            'bytes_sent': 0,
                            'last_active': 0
                        }

                    # 累加统计数据
                    combined_map[combined_key]['connections'] += item_stats.get('connections', 0)
                    combined_map[combined_key]['bytes_received'] += item_stats.get('bytes_received', 0)
                    combined_map[combined_key]['bytes_sent'] += item_stats.get('bytes_sent', 0)
                    combined_map[combined_key]['last_active'] = max(
                        combined_map[combined_key]['last_active'],
                        item_stats.get('last_active', 0)
                    )

            # 转换为列表
            data = list(combined_map.values())

        except Exception as e:
            logger.error(f"获取组合数据失败: {e}")

        return data

    def _get_grouped_data(self, stats_dict: Dict[str, DailyStats], group_by: str) -> List[Dict[str, Any]]:
        """获取分组数据 - 修复版"""
        data = []

        try:
            grouped_map = {}

            for date_str, stats in stats_dict.items():
                if not hasattr(stats, 'combined_stats') or not stats.combined_stats:
                    continue

                for combined_key, item_stats in stats.combined_stats.items():
                    # 获取分组键
                    if group_by == "proxy_name":
                        group_key = item_stats.get('proxy_name', '未命名代理')
                    elif group_by == "protocol":
                        protocol = item_stats.get('protocol', 'unknown').lower()
                        if protocol in ['socks5', 'socks']:
                            group_key = 'SOCKS5'
                        elif protocol in ['http', 'https']:
                            group_key = protocol.upper()
                        else:
                            group_key = protocol.upper() if protocol else "未知"
                    elif group_by == "ip":
                        group_key = item_stats.get('ip', '未知')
                    elif group_by == "country":
                        group_key = item_stats.get('country', '未知')
                    elif group_by == "user":
                        group_key = item_stats.get('user', '无认证')
                    else:
                        group_key = "未知"

                    if group_key not in grouped_map:
                        grouped_map[group_key] = {
                            'connections': 0,
                            'bytes_received': 0,
                            'bytes_sent': 0,
                            'last_active': 0
                        }

                    # 累加统计数据
                    grouped_map[group_key]['connections'] += item_stats.get('connections', 0)
                    grouped_map[group_key]['bytes_received'] += item_stats.get('bytes_received', 0)
                    grouped_map[group_key]['bytes_sent'] += item_stats.get('bytes_sent', 0)
                    grouped_map[group_key]['last_active'] = max(
                        grouped_map[group_key]['last_active'],
                        item_stats.get('last_active', 0)
                    )

            # 转换为列表并添加分组键信息
            for group_key, stats in grouped_map.items():
                item = {
                    'connections': stats['connections'],
                    'bytes_received': stats['bytes_received'],
                    'bytes_sent': stats['bytes_sent'],
                    'last_active': stats['last_active']
                }

                # 根据分组类型设置相应字段
                if group_by == "proxy_name":
                    item['proxy_name'] = group_key
                    item['protocol'] = '-'
                    item['ip'] = '-'
                    item['country'] = '-'
                    item['user'] = '-'
                elif group_by == "protocol":
                    item['proxy_name'] = '-'
                    item['protocol'] = group_key
                    item['ip'] = '-'
                    item['country'] = '-'
                    item['user'] = '-'
                elif group_by == "ip":
                    item['proxy_name'] = '-'
                    item['protocol'] = '-'
                    item['ip'] = group_key
                    item['country'] = '-'
                    item['user'] = '-'
                elif group_by == "country":
                    item['proxy_name'] = '-'
                    item['protocol'] = '-'
                    item['ip'] = '-'
                    item['country'] = group_key
                    item['user'] = '-'
                elif group_by == "user":
                    item['proxy_name'] = '-'
                    item['protocol'] = '-'
                    item['ip'] = '-'
                    item['country'] = '-'
                    item['user'] = group_key

                data.append(item)

        except Exception as e:
            logger.error(f"获取分组数据失败: {e}")

        return data

    # ========== 其他功能 ==========

    def refresh_data(self):
        """刷新数据"""
        try:
            now = datetime.now()
            current_tab = self.tab_widget.currentIndex()

            if current_tab == 0:  # 汇总页
                # 清空缓存，重新加载
                self.summary_data_cache = None
                self.active_counts_cache = None
                self.load_summary_table()
            elif current_tab == 1:  # 实时监控页
                self.update_realtime_filter_values()
                self.load_monitor_table()

            self.status_label.setText(f"最后更新: {now.strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"刷新数据失败: {e}")

    def export_data(self):
        """导出数据"""
        try:
            current_tab = self.tab_widget.currentIndex()
            file_name, _ = QFileDialog.getSaveFileName(
                self, "导出数据", "", "CSV文件 (*.csv);;所有文件 (*)"
            )

            if not file_name:
                return

            if current_tab == 0:  # 汇总数据
                data = self.get_summary_data()
                headers = ["代理名称", "代理类型", "IP", "地理信息", "用户",
                          "总连接数", "活跃连接", "接收数据量", "发送数据量", "总数据量", "最后活跃时间"]

                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for item in data:
                        last_active = item.get('last_active', '-')
                        if isinstance(last_active, (int, float)):
                            last_active = datetime.fromtimestamp(last_active).strftime("%Y-%m-%d %H:%M:%S")

                        writer.writerow([
                            item.get('proxy_name', '-'),
                            item.get('protocol', '-'),
                            item.get('ip', '-'),
                            item.get('country', '-'),
                            item.get('user', '-'),
                            item.get('connections', 0),
                            self._get_item_active_count(item),
                            item.get('bytes_received', 0),
                            item.get('bytes_sent', 0),
                            item.get('bytes_received', 0) + item.get('bytes_sent', 0),
                            last_active
                        ])

                self.status_label.setText(f"汇总数据已导出到: {file_name}")

            else:  # 实时连接数据
                connections = self.stats_manager.get_active_connection_details()
                headers = ["连接ID", "时间", "代理", "IP", "地理信息", "用户", "协议",
                          "时长(s)", "发送流量", "接收流量", "发送速度", "接收速度"]

                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for conn in connections:
                        writer.writerow([
                            conn.get('id', '-')[:20],
                            conn.get('time', '-'),
                            conn.get('proxy', '-'),
                            conn.get('ip', '-'),
                            conn.get('country', '-'),
                            conn.get('user', '匿名'),
                            conn.get('protocol', '-'),
                            f"{conn.get('duration', 0):.1f}",
                            conn.get('bytes_sent', 0),
                            conn.get('bytes_received', 0),
                            f"{conn.get('send_speed', 0):.1f}",
                            f"{conn.get('receive_speed', 0):.1f}"
                        ])

                self.status_label.setText(f"连接数据已导出到: {file_name}")

        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            self.status_label.setText(f"导出失败: {str(e)}")

    def clear_data(self):
        """清空数据"""
        try:
            reply = QMessageBox.question(
                self, '确认清空',
                '确定要清空所有统计信息吗？此操作不可恢复！',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.stats_manager.clear_stats()
                # 清空缓存
                self.summary_data_cache = None
                self.active_counts_cache = None
                self.load_data()
                self.status_label.setText("所有统计信息已清空")
                logger.info("用户清空了所有统计信息")

        except Exception as e:
            logger.error(f"清空数据失败: {e}")
            self.status_label.setText(f"清空失败: {str(e)}")

    def format_bytes(self, bytes_num: float) -> str:
        """格式化字节显示"""
        if bytes_num < 1024:
            return f"{int(bytes_num)} B"
        elif bytes_num < 1024 * 1024:
            return f"{bytes_num / 1024:.1f} KB"
        elif bytes_num < 1024 * 1024 * 1024:
            return f"{bytes_num / (1024 * 1024):.2f} MB"
        elif bytes_num < 1024 * 1024 * 1024 * 1024:
            return f"{bytes_num / (1024 * 1024 * 1024):.2f} GB"
        else:
            return f"{bytes_num / (1024 * 1024 * 1024 * 1024):.2f} TB"

    def closeEvent(self, event):
        """关闭事件"""
        self.timer.stop()
        super().closeEvent(event)
