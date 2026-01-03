# -*- coding: utf-8 -*-
"""
Module: ip_detail_dialog.py
Author: Takeshi
Date: 2025-12-26

Description:
    ip地址详细信息
"""



import logging
import time
import ipaddress
from typing import Dict, List, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QScrollArea,
    QWidget, QApplication, QFrame, QMenu
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon

from defaults.ui_default import SECURITY_IP_DETAIL_DIALOG_SIZE, DIALOG_ICOINS
from managers.ip_geo_manager import IPGeoManager
from defaults.config_manager import get_config_manager
from defaults.ip_geo_default import IPGeoConfig, DatabaseConfig

logger = logging.getLogger(__name__)


class IPDetailDialog(QDialog):
    """IP详情对话框 - 默认显示所有启用的数据库信息"""

    def __init__(self, ip: str, ip_geo_manager: IPGeoManager, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.ip_geo_manager = ip_geo_manager

        # 从配置管理器获取配置
        self.config = self._load_config()

        # 查询结果
        self.all_databases_results: List[Dict[str, Any]] = []

        self.setup_ui()
        # 对话框一打开就直接查询所有数据库
        QTimer.singleShot(100, self.load_data)

    def _load_config(self) -> IPGeoConfig:
        """从配置管理器加载配置"""
        try:
            config_manager = get_config_manager()
            # 直接获取 IPGeoConfig 对象
            config = config_manager.get_config('IP_GEO_CONFIG')

            if isinstance(config, IPGeoConfig):
                return config
            else:
                # 如果返回的不是 IPGeoConfig 对象，创建默认配置
                logger.warning(f"配置类型错误，期望 IPGeoConfig，实际得到 {type(config)}")
                return IPGeoConfig()

        except Exception as e:
            logger.error(f"加载IP地理位置配置失败: {e}")
            return IPGeoConfig()

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle(f"BindInterfaceProxy - IP详情：{self.ip}")
        self.resize(*SECURITY_IP_DETAIL_DIALOG_SIZE)
        self.setModal(False)

        # 启用对话框的最小化和最大化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 1. 顶部工具栏
        toolbar_layout = QHBoxLayout()

        # IP地址显示
        self.ip_label = QLabel(f"🔍 IP: <b>{self.ip}</b>")
        self.ip_label.setStyleSheet("""
            font-size: 13pt;
            padding: 4px 8px;
            background: #f0f8ff;
            border-radius: 4px;
            border: 1px solid #d0e0ff;
        """)
        toolbar_layout.addWidget(self.ip_label)

        # IP类型标签
        self.ip_type_label = QLabel("类型: 识别中...")
        self.ip_type_label.setStyleSheet("""
            color: #666;
            padding: 4px 8px;
            background: #f8f9fa;
            border-radius: 4px;
            border: 1px solid #eee;
        """)
        toolbar_layout.addWidget(self.ip_type_label)

        toolbar_layout.addStretch()

        # 数据库统计
        self.db_stats_label = QLabel("")
        self.db_stats_label.setStyleSheet("color: #007acc; padding: 4px 8px;")
        toolbar_layout.addWidget(self.db_stats_label)

        # 在线查询按钮 - 替换原来的设置按钮
        self.online_search_btn = QPushButton("🌐 在线查询")
        self.online_search_btn.setToolTip("打开在线查询菜单")
        self.online_search_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                border: 1px solid #17a2b8;
                border-radius: 4px;
                background: #17a2b8;
                color: white;
            }
            QPushButton:hover {
                background: #138496;
            }
        """)
        self.online_search_btn.clicked.connect(self.show_online_search_menu)
        toolbar_layout.addWidget(self.online_search_btn)

        main_layout.addLayout(toolbar_layout)

        # 2. 查询状态栏
        status_layout = QHBoxLayout()

        self.status_label = QLabel("正在查询所有数据库...")
        self.status_label.setStyleSheet("color: #666; padding: 2px 8px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # 查询耗时
        self.query_time_label = QLabel("")
        self.query_time_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px 8px;")
        status_layout.addWidget(self.query_time_label)

        main_layout.addLayout(status_layout)

        # 3. 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #dee2e6; margin: 5px 0;")
        main_layout.addWidget(separator)

        # 4. 表格区域
        self.create_table_area()
        main_layout.addWidget(self.table_scroll_area, 1)

        # 5. 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.copy_btn = QPushButton("📋 复制结果")
        self.copy_btn.setToolTip("复制所有数据库查询结果到剪贴板")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #28a745;
                border-radius: 4px;
                background: #28a745;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #218838;
            }
            QPushButton:disabled {
                background: #6c757d;
                border-color: #6c757d;
            }
        """)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.copy_btn.setEnabled(False)
        button_layout.addWidget(self.copy_btn)

        # 刷新按钮
        self.refresh_btn = QPushButton("🔄 刷新查询")
        self.refresh_btn.setToolTip("重新查询所有数据库")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #007bff;
                border-radius: 4px;
                background: #007bff;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #0056b3;
            }
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("✕ 关闭")
        self.close_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #dc3545;
                border-radius: 4px;
                background: #dc3545;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #c82333;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        main_layout.addLayout(button_layout)

    def create_table_area(self):
        """创建表格显示区域"""
        # 滚动区域
        self.table_scroll_area = QScrollArea()
        self.table_scroll_area.setWidgetResizable(True)
        self.table_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background: white;
            }
        """)

    def show_online_search_menu(self):
        """显示在线查询菜单"""
        if not self.ip_geo_manager:
            logger.warning("IP地理管理器未初始化")
            return

        # 创建菜单
        menu = QMenu(self)

        # 获取所有可用的搜索网址
        search_urls = self.ip_geo_manager.get_search_urls()

        if not search_urls:
            # 没有配置网址
            no_urls_action = QAction("⚠ 未配置搜索网址", self)
            no_urls_action.setEnabled(False)
            menu.addAction(no_urls_action)
        else:
            # 为每个网址创建菜单项
            for url_info in search_urls:
                action_name = f"🌐 {url_info.get('name', '未知网站')}"
                action = QAction(action_name, self)

                # 使用lambda捕获当前url_info的name
                url_name = url_info.get('name')
                action.triggered.connect(lambda checked, name=url_name:
                                        self.open_online_search(self.ip, name))
                menu.addAction(action)

        # 显示菜单
        menu.exec_(self.online_search_btn.mapToGlobal(
            self.online_search_btn.rect().bottomLeft()
        ))

    def open_online_search(self, ip_address: str, url_name: str):
        """打开在线查询网站"""
        if not self.ip_geo_manager:
            logger.warning("IP地理管理器未初始化")
            return

        try:
            # 使用IP地理管理器的在线搜索功能
            success = self.ip_geo_manager.search_ip_online(ip_address, url_name)

            if success:
                self.status_label.setText(f"🌐 正在打开 {url_name} 查询 {ip_address}...")
                logger.info(f"在线查询 {ip_address} - {url_name}")

                # 3秒后恢复状态
                QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))
            else:
                self.status_label.setText(f"⚠ 无法打开 {url_name}")

        except Exception as e:
            logger.error(f"打开在线查询失败: {e}")
            self.status_label.setText("⚠ 打开在线查询失败")

    def load_data(self):
        """加载数据 - 查询所有启用的数据库"""
        self.status_label.setText("正在查询所有数据库...")
        self.copy_btn.setEnabled(False)
        start_time = time.time()

        # 获取IP类型
        ip_type_info = self._get_ip_type_info(self.ip)
        self.ip_type_label.setText(f"类型: {ip_type_info}")

        # 检查配置是否启用
        if not self.config or not self.config.enabled:
            self._show_error("IP地理位置功能未启用")
            return

        # 检查管理器
        if not self.ip_geo_manager:
            self._show_error("IP地理位置管理器未初始化")
            return

        try:
            # 获取所有启用的数据库
            enabled_databases = self._get_all_enabled_databases()
            if not enabled_databases:
                self._show_error("没有启用的数据库")
                return

            # 查询每个数据库
            self.all_databases_results = []

            for db_config in enabled_databases:
                try:
                    # 直接查询单个数据库
                    result = self._query_single_database(db_config, self.ip)
                    if result:
                        self.all_databases_results.append(result)
                except Exception as e:
                    logger.error(f"查询数据库 {db_config.name} 失败: {e}")
                    # 记录失败信息
                    error_result = {
                        'source_name': db_config.name,
                        'source_path': db_config.path,
                        'source_type': db_config.db_type,
                        'success': False,
                        'error': str(e),
                        'response_time': 0,
                        'country': '查询失败',
                        'region': '',
                        'city': '',
                        'isp': '',
                        'is_special': False
                    }
                    self.all_databases_results.append(error_result)

            # 更新统计信息
            db_count = len(enabled_databases)
            success_count = sum(1 for r in self.all_databases_results if r.get('success', False))
            self.db_stats_label.setText(f"数据库: {success_count}/{db_count}个成功")

            # 计算查询耗时
            query_time = int((time.time() - start_time) * 1000)
            self.query_time_label.setText(f"查询耗时: {query_time}ms")

            # 更新表格显示
            self.update_table()

            self.copy_btn.setEnabled(True)
            self.status_label.setText("查询完成")

        except Exception as e:
            logger.error(f"查询所有数据库失败: {e}", exc_info=True)
            self._show_error(f"查询失败: {str(e)[:50]}")

    def _get_all_enabled_databases(self) -> List[DatabaseConfig]:
        """获取所有启用的数据库配置"""
        if not self.config:
            return []

        try:
            # 从配置中获取启用的数据库
            enabled_dbs = []
            for db_config in self.config.databases:
                if db_config.enabled:
                    enabled_dbs.append(db_config)

            # 按优先级排序
            enabled_dbs.sort(key=lambda db: db.priority)
            return enabled_dbs

        except Exception as e:
            logger.error(f"获取启用的数据库失败: {e}")
            return []

    def _query_single_database(self, db_config: DatabaseConfig, ip: str) -> Optional[Dict[str, Any]]:
        """查询单个数据库"""
        # 记录开始时间
        start_time = time.time()

        if not self.ip_geo_manager:
            return None

        try:
            # 使用IPGeoManager的查询方法
            result = self.ip_geo_manager._query_single_database(db_config, ip)

            # 转换为字典格式
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
            elif isinstance(result, dict):
                result_dict = result
            elif hasattr(result, '__dict__'):
                result_dict = vars(result)
            else:
                result_dict = {'success': False, 'error': '结果格式错误'}

            # 计算响应时间
            result_dict['response_time'] = int((time.time() - start_time) * 1000)

            return result_dict

        except Exception as e:
            logger.error(f"查询数据库 {db_config.name} 异常: {e}")
            return {
                'source_name': db_config.name,
                'source_path': db_config.path,
                'source_type': db_config.db_type,
                'success': False,
                'error': str(e),
                'response_time': int((time.time() - start_time) * 1000),
                'country': '查询异常',
                'region': '',
                'city': '',
                'isp': '',
                'is_special': False
            }

    def _get_ip_type_info(self, ip: str) -> str:
        """获取IP类型信息"""
        try:
            ip_str = ip.split('/')[0] if '/' in ip else ip
            ip_obj = ipaddress.ip_address(ip_str)

            ip_type = "IPv4" if ip_obj.version == 4 else "IPv6"

            special_types = []
            if ip_obj.is_private:
                special_types.append("内网")
            if ip_obj.is_loopback:
                special_types.append("本机")
            if ip_obj.is_multicast:
                special_types.append("组播")
            if ip_obj.is_reserved:
                special_types.append("保留")
            if ip_obj.is_link_local:
                special_types.append("链路本地")
            if ip_obj.is_global:
                special_types.append("公网")

            if special_types:
                return f"{ip_type} ({'、'.join(special_types)})"
            return ip_type

        except Exception as e:
            logger.debug(f"识别IP类型失败: {e}")
            return "未知格式"

    def update_table(self):
        """更新表格显示"""
        # 清空现有内容
        table_widget = QWidget()
        table_layout = QGridLayout(table_widget)
        table_layout.setSpacing(0)
        table_layout.setContentsMargins(0, 0, 0, 0)

        # 设置滚动区域的内容
        self.table_scroll_area.setWidget(table_widget)

        if not self.all_databases_results:
            self._show_no_data(table_layout)
            return

        # 过滤结果：分离普通数据库结果和特殊IP结果
        valid_results = []
        special_results = []

        for result in self.all_databases_results:
            if result.get('is_special', False):
                special_results.append(result)
            else:
                valid_results.append(result)

        # 如果没有有效的数据库结果，显示特殊IP
        if not valid_results and special_results:
            self._show_special_ip(table_layout, special_results[0])
            return

        # ========== 表头（第一行） ==========
        row = 0

        # 字段名列（第一列，占第一行）
        field_header = QLabel("字段")
        field_header.setStyleSheet("""
            background: #495057;
            color: white;
            font-weight: bold;
            padding: 12px;
            border: 1px solid #343a40;
            border-right: 2px solid #6c757d;
        """)
        field_header.setAlignment(Qt.AlignCenter)  # 居中
        table_layout.addWidget(field_header, row, 0)

        # 数据库列（表头）
        for col_idx, result in enumerate(valid_results, 1):
            db_name = result.get('source_name', f"数据库{col_idx}")
            db_type = result.get('source_type', 'unknown').upper()
            priority = col_idx

            # 数据库头
            db_header = QLabel(f"[{priority}] {db_name}\n({db_type})")
            success = result.get('success', False)

            # 根据成功状态设置不同颜色
            if success:
                bg_color = "#28a745"  # 成功-绿色
            else:
                bg_color = "#dc3545"  # 失败-红色

            db_header.setStyleSheet(f"""
                background: {bg_color};
                color: white;
                font-weight: bold;
                padding: 12px 8px;
                border: 1px solid #343a40;
                border-left: none;
            """)
            db_header.setAlignment(Qt.AlignCenter)  # 居中
            db_header.setWordWrap(True)
            table_layout.addWidget(db_header, row, col_idx)

        # 设置列宽
        table_layout.setColumnMinimumWidth(0, 100)  # 字段列

        # ========== 数据行 ==========
        row += 1

        # 根据配置确定要显示的字段
        fields_to_show = self._get_fields_to_show()

        # 添加数据行
        for field_idx, (field_key, display_name) in enumerate(fields_to_show):
            # 字段名单元格（第一列）
            field_cell = QLabel(f"{display_name}:")
            field_cell.setStyleSheet(f"""
                font-weight: bold;
                color: #212529;
                padding: 10px;
                background: {'#f8f9fa' if field_idx % 2 == 0 else '#e9ecef'};
                border: 1px solid #dee2e6;
                border-right: 2px solid #ced4da;
            """)
            field_cell.setAlignment(Qt.AlignCenter)  # 居中
            table_layout.addWidget(field_cell, row, 0)

            # 数据单元格（数据库列）
            for col_idx, result in enumerate(valid_results, 1):
                value = self._format_field_value(result.get(field_key, ''))

                value_cell = QLabel(value)
                value_cell.setStyleSheet(f"""
                    padding: 10px;
                    background: {'white' if field_idx % 2 == 0 else '#f8f9fa'};
                    border: 1px solid #dee2e6;
                    border-left: none;
                """)
                value_cell.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value_cell.setWordWrap(True)
                value_cell.setAlignment(Qt.AlignCenter)  # 居中
                table_layout.addWidget(value_cell, row, col_idx)

            row += 1

        # ========== 额外信息行 ==========

        # 响应时间行
        time_cell = QLabel("响应时间:")
        time_cell.setStyleSheet("""
            font-weight: bold;
            color: #212529;
            padding: 10px;
            background: #e9ecef;
            border: 1px solid #dee2e6;
            border-right: 2px solid #ced4da;
        """)
        time_cell.setAlignment(Qt.AlignCenter)  # 居中
        table_layout.addWidget(time_cell, row, 0)

        for col_idx, result in enumerate(valid_results, 1):
            response_time = result.get('response_time', 0)
            time_text = f"{response_time}ms" if response_time >= 0 else "-"

            time_value = QLabel(time_text)
            time_value.setStyleSheet(f"""
                padding: 10px;
                color: #6c757d;
                background: white;
                border: 1px solid #dee2e6;
                border-left: none;
            """)
            time_value.setAlignment(Qt.AlignCenter)  # 居中
            table_layout.addWidget(time_value, row, col_idx)

        row += 1

        # 状态行
        status_cell = QLabel("查询状态:")
        status_cell.setStyleSheet("""
            font-weight: bold;
            color: #212529;
            padding: 10px;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-right: 2px solid #ced4da;
        """)
        status_cell.setAlignment(Qt.AlignCenter)  # 居中
        table_layout.addWidget(status_cell, row, 0)

        for col_idx, result in enumerate(valid_results, 1):
            success = result.get('success', False)
            status_text = "✓ 成功" if success else "✗ 失败"
            error = result.get('error', '')
            if error and not success:
                # 缩短错误信息显示
                short_error = error[:15] + "..." if len(error) > 15 else error
                status_text += f"\n({short_error})"

            status_value = QLabel(status_text)
            status_color = "#28a745" if success else "#dc3545"
            status_value.setStyleSheet(f"""
                padding: 10px;
                font-weight: bold;
                color: {status_color};
                background: {'white' if row % 2 == 0 else '#f8f9fa'};
                border: 1px solid #dee2e6;
                border-left: none;
            """)
            status_value.setAlignment(Qt.AlignCenter)  # 居中
            status_value.setWordWrap(True)
            table_layout.addWidget(status_value, row, col_idx)

        # 文件路径行（作为提示）
        row += 1
        path_cell = QLabel("文件路径:")
        path_cell.setStyleSheet("""
            font-weight: bold;
            color: #212529;
            padding: 8px;
            background: #e9ecef;
            border: 1px solid #dee2e6;
            border-right: 2px solid #ced4da;
        """)
        path_cell.setAlignment(Qt.AlignCenter)  # 居中
        table_layout.addWidget(path_cell, row, 0)

        for col_idx, result in enumerate(valid_results, 1):
            file_path = result.get('source_path', '')
            if file_path:
                # 只显示文件名
                import os
                filename = os.path.basename(file_path)
                if len(filename) > 20:
                    filename = filename[:17] + "..."
                path_text = filename
            else:
                path_text = "-"

            path_value = QLabel(path_text)
            path_value.setStyleSheet(f"""
                padding: 8px;
                color: #6c757d;
                font-size: 11px;
                background: white;
                border: 1px solid #dee2e6;
                border-left: none;
            """)
            path_value.setAlignment(Qt.AlignCenter)  # 居中
            path_value.setToolTip(file_path if file_path else "")
            table_layout.addWidget(path_value, row, col_idx)

    def _get_fields_to_show(self):
        """根据配置确定要显示的字段"""
        fields_to_show = []

        # 前三个固定字段
        fields_to_show.append(('country', '国家'))
        fields_to_show.append(('region', '地区'))
        fields_to_show.append(('city', '城市'))

        # 根据显示配置添加其他字段
        if self.config and hasattr(self.config, 'display_config'):
            display_config = self.config.display_config

            if display_config.show_isp:
                fields_to_show.append(('isp', 'ISP服务商'))

            if display_config.show_asn:
                fields_to_show.append(('asn', 'ASN号码'))
                fields_to_show.append(('as_organization', 'AS组织'))

            if display_config.show_network:
                fields_to_show.append(('organization', '所属组织'))
                fields_to_show.append(('network_cidr', '网络CIDR'))
                fields_to_show.append(('ip_range', 'IP范围'))

        # 其他可能的信息字段（如果有数据就显示）
        other_fields = [
            ('country_code', '国家代码'),
            ('latitude', '纬度'),
            ('longitude', '经度'),
            ('timezone', '时区'),
        ]

        # 检查每个字段是否有数据，有就添加到显示列表
        for field_key, display_name in other_fields:
            for result in self.all_databases_results:
                if result.get('success', False):
                    value = result.get(field_key)
                    if value and str(value).strip() not in ['', '-', '未知', 'N/A', 'None']:
                        if (field_key, display_name) not in fields_to_show:
                            fields_to_show.append((field_key, display_name))
                        break

        return fields_to_show

    def _format_field_value(self, value) -> str:
        """格式化字段值"""
        if not value:
            return "-"

        value_str = str(value).strip()

        if value_str in ['', '-', 'None', 'N/A', '未知', 'NONE', 'null']:
            return "-"

        # 特殊格式化
        if isinstance(value, (int, float)):
            return str(value)

        return value_str

    def _show_no_data(self, layout):
        """显示无数据提示"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignCenter)
        container_layout.setContentsMargins(40, 60, 40, 60)

        icon = QLabel("📭")
        icon.setStyleSheet("font-size: 48pt; color: #95a5a6;")
        icon.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(icon)

        message = QLabel("无查询结果")
        message.setStyleSheet("font-size: 14pt; color: #7f8c8d; margin-top: 20px;")
        message.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(message)

        if not self.ip_geo_manager:
            tip = QLabel("IP地理位置管理器未初始化")
            tip.setStyleSheet("color: #e74c3c; margin-top: 10px; font-size: 11px;")
            tip.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(tip)

        layout.addWidget(container)

    def _show_special_ip(self, layout, special_result):
        """显示特殊IP信息"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignCenter)
        container_layout.setContentsMargins(40, 60, 40, 60)

        icon = QLabel("🔒")
        icon.setStyleSheet("font-size: 48pt; color: #3498db;")
        icon.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(icon)

        ip_type = special_result.get('country', '特殊IP')
        message = QLabel(f"{ip_type}")
        message.setStyleSheet("font-size: 16pt; color: #2c3e50; margin-top: 20px; font-weight: bold;")
        message.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(message)

        details = QLabel(f"{special_result.get('region', '')}")
        details.setStyleSheet("color: #7f8c8d; margin-top: 10px; font-size: 12px;")
        details.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(details)

        layout.addWidget(container)

    def _show_error(self, message):
        """显示错误信息"""
        self.status_label.setText(message)
        self.copy_btn.setEnabled(False)
        self.query_time_label.setText("")

    def copy_to_clipboard(self):
        """复制所有数据库结果到剪贴板"""
        try:
            if not self.all_databases_results:
                self.status_label.setText("无数据可复制")
                return

            # 构建文本
            lines = [
                f"IP地理位置查询报告",
                f"IP地址: {self.ip}",
                f"查询时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"IP类型: {self.ip_type_label.text().replace('类型: ', '')}",
                ""
            ]

            # 分组结果
            valid_results = [r for r in self.all_databases_results if not r.get('is_special', False)]
            special_results = [r for r in self.all_databases_results if r.get('is_special', False)]

            # 特殊IP结果
            if special_results:
                lines.append("=== 系统识别 ===")
                for result in special_results:
                    lines.append(f"类型: {result.get('country', '特殊IP')}")
                    lines.append(f"描述: {result.get('region', '')}")
                    if result.get('isp'):
                        lines.append(f"网络: {result.get('isp', '')}")
                    lines.append("")

            # 数据库结果
            if valid_results:
                success_count = sum(1 for r in valid_results if r.get('success', False))
                lines.append(f"=== 数据库查询结果 ({success_count}/{len(valid_results)}个成功) ===")

                for i, result in enumerate(valid_results, 1):
                    lines.append(f"\n[{i}] {result.get('source_name', '未知数据库')}")
                    lines.append(f"  类型: {result.get('source_type', 'unknown').upper()}")
                    lines.append(f"  状态: {'✓ 成功' if result.get('success') else '✗ 失败'}")

                    if result.get('response_time'):
                        lines.append(f"  响应时间: {result.get('response_time')}ms")

                    if not result.get('success'):
                        error = result.get('error', '未知错误')
                        lines.append(f"  错误: {error}")
                        continue

                    # 根据配置显示字段
                    fields_to_show = self._get_fields_to_show()

                    for field_key, display_name in fields_to_show:
                        value = result.get(field_key)
                        if value and str(value).strip() not in ['', '-', '未知', 'N/A']:
                            lines.append(f"  {display_name}: {value}")

            text = "\n".join(lines)

            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

            self.status_label.setText("已复制到剪贴板")

            # 3秒后恢复状态
            QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))

        except Exception as e:
            logger.error(f"复制失败: {e}")
            self.status_label.setText("复制失败")
