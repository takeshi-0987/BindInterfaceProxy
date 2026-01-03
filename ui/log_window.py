# -*- coding: utf-8 -*-
"""
Module: log_window.py
Author: Takeshi
Date: 2025-12-20

Description:
    日志窗口模块
"""

from datetime import datetime
import logging
import re
import ipaddress
from PySide6.QtWidgets import (
    QMainWindow, QTextEdit, QVBoxLayout, QWidget,
    QPushButton, QHBoxLayout, QLabel, QMessageBox,
    QFileDialog, QApplication, QMenu, QInputDialog
)
from PySide6.QtGui import QFont, QTextCursor, QAction, QIcon
from PySide6.QtCore import Qt, Signal, Slot

from defaults.ui_default import LOG_WINDOW_SIZE, DIALOG_ICOINS
from defaults.log_default import UILogConfig
from defaults.config_manager import get_config_manager
from ui.ip_detail_dialog import IPDetailDialog


logger = logging.getLogger(__name__)


class IPContextMenu(QMenu):
    """IP右键菜单"""

    # 定义信号
    view_details = Signal(str)      # 查看详情
    temp_ban = Signal(str)          # 临时封禁
    add_blacklist = Signal(str)     # 加入黑名单
    add_whitelist = Signal(str)     # 加入白名单
    copy_ip = Signal(str)           # 复制IP
    lookup_security = Signal(str)   # 查询安全状态
    online_search = Signal(str, str)  # 在线查询(IP, 网址名称)

    def __init__(self, ip_address: str, security_manager=None, ip_geo_manager=None, parent=None):
        super().__init__(parent)
        self.ip_address = ip_address
        self.security_manager = security_manager
        self.ip_geo_manager = ip_geo_manager

        self._setup_ui()

    def _setup_ui(self):
        """设置菜单项"""

        if get_config_manager().get_config('IP_GEO_CONFIG').enabled:
            # 查看详情
            view_action = QAction("🌍 查看IP详情", self)
            view_action.triggered.connect(lambda: self.view_details.emit(self.ip_address))
            self.addAction(view_action)

            self.addSeparator()

        # 临时封禁
        temp_ban_action = QAction("🚫 加入临时封禁", self)
        temp_ban_action.triggered.connect(lambda: self.temp_ban.emit(self.ip_address))
        self.addAction(temp_ban_action)

        # 加入黑名单
        blacklist_action = QAction("⛔ 加入黑名单", self)
        blacklist_action.triggered.connect(lambda: self.add_blacklist.emit(self.ip_address))
        self.addAction(blacklist_action)

        # 加入白名单
        whitelist_action = QAction("✅ 加入白名单", self)
        whitelist_action.triggered.connect(lambda: self.add_whitelist.emit(self.ip_address))
        self.addAction(whitelist_action)

        # 查看安全状态
        security_action = QAction("🛡️ 查询安全状态", self)
        security_action.triggered.connect(lambda: self.lookup_security.emit(self.ip_address))
        self.addAction(security_action)

        self.addSeparator()

        # 复制IP
        copy_action = QAction("📋 复制IP地址", self)
        copy_action.triggered.connect(lambda: self.copy_ip.emit(self.ip_address))
        self.addAction(copy_action)

        # 在线查询子菜单（如果IP地理功能启用）
        if self.ip_geo_manager and get_config_manager().get_config('IP_GEO_CONFIG').search_urls.enabled:
            self.addSeparator()
            self._setup_online_search_menu()

    def _setup_online_search_menu(self):
        """设置在线查询子菜单"""
        # 创建在线查询子菜单
        online_menu = QMenu("🛜 在线查询", self)

        # 获取所有可用的搜索网址
        search_urls = self.ip_geo_manager.get_search_urls()

        if search_urls:
            for url_info in search_urls:
                # 为每个网址创建菜单项
                action_name = f"🌐 {url_info.get('name', '未知网站')}"
                action = QAction(action_name, self)

                # 使用lambda捕获当前url_info的name
                url_name = url_info.get('name')
                action.triggered.connect(lambda checked, name=url_name:
                                       self._open_online_search(self.ip_address, name))
                online_menu.addAction(action)
        else:
            # 如果没有配置网址，添加一个禁用项
            no_urls_action = QAction("⚠ 未配置搜索网址", self)
            no_urls_action.setEnabled(False)
            online_menu.addAction(no_urls_action)

        self.addMenu(online_menu)

    def _open_online_search(self, ip_address: str, url_name: str):
        """打开在线查询网站"""
        # 发送信号，由主窗口处理
        self.online_search.emit(ip_address, url_name)

    def update_menu_state(self):
        """根据IP状态更新菜单项状态"""
        if not self.security_manager:
            return

        try:
            # 获取IP的安全状态
            status = self.security_manager.get_security_status(self.ip_address)

            # 查找菜单项并更新状态
            for action in self.actions():
                text = action.text()

                # 如果在黑名单中，禁用"加入黑名单"选项
                if status.get('in_blacklist', False) and "加入黑名单" in text:
                    action.setEnabled(False)
                    action.setText("⛔ 已在黑名单中")

                # 如果在白名单中，禁用"加入白名单"选项
                elif status.get('in_whitelist', False) and "加入白名单" in text:
                    action.setEnabled(False)
                    action.setText("✅ 已在白名单中")

                # 如果已被临时封禁，更新菜单项
                elif status.get('temp_banned', False) and "加入临时封禁" in text:
                    action.setEnabled(False)
                    action.setText("🚫 已临时封禁")

        except Exception as e:
            logger.debug(f"更新菜单状态失败: {e}")

class LogWindow(QMainWindow):
    """日志窗口 - 完全使用系统字体，支持IP右键菜单和字体滚轮缩放"""
    def __init__(self, ui_config: UILogConfig, security_manager=None, ip_geo_manager=None):
        super().__init__()

        self.setWindowTitle("BindInterFace - 日志查看器")
        self.resize(*LOG_WINDOW_SIZE)
        self.center_on_screen()

        # 启用对话框的最小化和最大化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        self.ui_config = ui_config
        self.security_manager = security_manager
        self.ip_geo_manager = ip_geo_manager

        # IP正则表达式
        self.ip_pattern = re.compile(
            r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 日志显示区域 - 完全使用系统字体
        self.log_text = QTextEdit()

        # 使用应用程序的系统字体
        app_font = QApplication.font()
        self.base_font = app_font  # 保存基础字体用于重置

        self.log_text.setFont(app_font)
        self.log_text.setReadOnly(True)
        self.log_text.setAcceptRichText(True)
        self.log_text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_text.customContextMenuRequested.connect(self._show_context_menu)

        # 启用滚轮缩放功能
        self.log_text.wheelEvent = self._handle_wheel_event

        layout.addWidget(self.log_text)

        # 状态
        self.auto_scroll = self.ui_config.auto_scroll
        self.log_count = 0
        self.selected_ip = None

        # 状态栏
        self.setup_status_bar()
        self.update_status()

        # 添加快捷键
        self.setup_zoom_shortcuts()

    def set_security_manager(self, security_manager):
        """设置安全管理器"""
        self.security_manager = security_manager

    def set_ip_geo_manager(self, ip_geo_manager):
        """设置IP地理管理器"""
        self.ip_geo_manager = ip_geo_manager

    def center_on_screen(self):
        """居中显示窗口"""
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )

    def setup_zoom_shortcuts(self):
        """设置字体缩放快捷键"""
        # 放大字体: Ctrl + +
        zoom_in_action = QAction("放大字体", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        self.addAction(zoom_in_action)

        # 缩小字体: Ctrl + -
        zoom_out_action = QAction("缩小字体", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        self.addAction(zoom_out_action)

        # 重置字体: Ctrl + 0
        reset_font_action = QAction("重置字体", self)
        reset_font_action.setShortcut("Ctrl+0")
        reset_font_action.triggered.connect(self.reset_font)
        self.addAction(reset_font_action)

    def setup_status_bar(self):
        """设置状态栏"""
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)

        # 左侧：状态信息
        self.status_label = QLabel()
        status_layout.addWidget(self.status_label)

        # 右侧拉伸
        status_layout.addStretch()

        # 右侧：操作按钮
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.clicked.connect(self.clear_logs)
        self.clear_btn.setFixedSize(80, 25)
        status_layout.addWidget(self.clear_btn)

        self.pause_btn = QPushButton("暂停滚动")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setFixedSize(80, 25)
        status_layout.addWidget(self.pause_btn)

        self.export_btn = QPushButton("导出日志")
        self.export_btn.clicked.connect(self.export_logs)
        self.export_btn.setFixedSize(80, 25)
        status_layout.addWidget(self.export_btn)

        # 设置状态栏
        self.statusBar().addPermanentWidget(status_widget, 1)

    def add_log(self, message):
        """添加日志消息"""

        # 检查是否是HTML格式
        if message.strip().startswith('<') and 'span' in message:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            html_content = f"{message}<br>"
            cursor.insertHtml(html_content)
        else:
            self.log_text.append(message)

        self.log_count += 1

        # 自动滚动到底部
        if self.auto_scroll:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)

        # 限制日志行数
        max_lines = self.ui_config.max_lines
        if self.log_count > max_lines:
            cursor = self.log_text.textCursor()
            cursor.setPosition(0)
            lines_to_remove = min(50, max_lines // 10)
            for _ in range(lines_to_remove):
                cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            self.log_count -= lines_to_remove

        self.update_status()

    def _handle_wheel_event(self, event):
        """处理滚轮事件：Ctrl+滚轮缩放字体"""
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            font = self.log_text.font()
            current_size = font.pointSize()

            if delta > 0:  # 滚轮向上，放大
                new_size = min(current_size + 1, 24)
            else:  # 滚轮向下，缩小
                new_size = max(current_size - 1, 8)

            # 更新字体
            font.setPointSize(new_size)
            self.log_text.setFont(font)

            # 立即显示更新后的字体信息
            self.show_font_info()

            event.accept()
        else:
            # 普通滚轮：滚动文本
            QTextEdit.wheelEvent(self.log_text, event)

    def zoom_in(self):
        """放大字体"""
        font = self.log_text.font()
        current_size = font.pointSize()
        new_size = min(current_size + 1, 24)

        if new_size != current_size:
            font.setPointSize(new_size)
            self.log_text.setFont(font)
            self.show_font_info("放大")

    def zoom_out(self):
        """缩小字体"""
        font = self.log_text.font()
        current_size = font.pointSize()
        new_size = max(current_size - 1, 8)

        if new_size != current_size:
            font.setPointSize(new_size)
            self.log_text.setFont(font)
            self.show_font_info("缩小")

    def reset_font(self):
        """重置字体到应用程序默认"""
        current_font = self.log_text.font()
        base_size = self.base_font.pointSize()

        if current_font.pointSize() != base_size:
            font = QFont(self.base_font)
            self.log_text.setFont(font)
            self.show_font_info("重置")

    def show_font_info(self, action=None):
        """显示字体信息"""
        current_font = self.log_text.font()
        font_name = current_font.family()
        font_size = current_font.pointSize()

        if action:
            message = f"字体{action}: {font_size}pt ({font_name})"
            if action == "重置":
                message = f"字体已重置: {font_size}pt ({font_name})"
        else:
            message = f"字体大小: {font_size}pt ({font_name})"

        self.statusBar().showMessage(f"🔍 {message}", 1500)
        self.update_status()  # 立即更新状态栏

    def update_status(self):
        """更新状态栏"""
        # 总是从实际控件获取最新的字体信息
        current_font = self.log_text.font()
        font_name = current_font.family()
        font_size = current_font.pointSize()

        status_text = f"📝 日志条目: {self.log_count} | 🔄 自动滚动: {'开启' if self.auto_scroll else '关闭'} | 🔍 字体: {font_name} {font_size}pt"
        self.status_label.setText(status_text)

        # 更新导出按钮状态
        self.export_btn.setEnabled(self.log_count > 0)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        # 获取光标位置
        cursor = self.log_text.cursorForPosition(position)
        cursor.select(QTextCursor.WordUnderCursor)
        selected_text = cursor.selectedText()

        # 尝试从选中文本中提取IP
        ip_address = self._extract_ip_from_text(selected_text)
        if not ip_address:
            # 如果没有直接选中IP，尝试从光标所在行查找
            cursor.select(QTextCursor.LineUnderCursor)
            line_text = cursor.selectedText()
            ip_address = self._extract_ip_from_text(line_text)

        if ip_address and self._is_valid_ip(ip_address):
            self.selected_ip = ip_address
            self._show_ip_menu(position, ip_address)
        else:
            # 显示带字体调整的默认右键菜单
            self._show_default_menu(position)

    def _extract_ip_from_text(self, text: str) -> str:
        """从文本中提取IP地址"""
        if not text:
            return ""

        # 查找IP地址
        match = self.ip_pattern.search(text)
        if match:
            return match.group()
        return ""

    def _is_valid_ip(self, ip_str: str) -> bool:
        """验证IP地址是否有效"""
        try:
            ipaddress.IPv4Address(ip_str)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False

    def _show_ip_menu(self, position, ip_address: str):
        """显示IP右键菜单"""
        menu = QMenu(self)

        # 添加菜单项
        if get_config_manager().get_config('IP_GEO_CONFIG').enabled:
            view_action = QAction("🌍 查看IP详情", self)
            view_action.triggered.connect(lambda: self._view_ip_details(ip_address))
            menu.addAction(view_action)
            menu.addSeparator()

        # 临时封禁
        temp_ban_action = QAction("🚫 加入临时封禁", self)
        temp_ban_action.triggered.connect(lambda: self._add_temp_ban(ip_address))
        menu.addAction(temp_ban_action)

        # 加入黑名单
        blacklist_action = QAction("⛔ 加入黑名单", self)
        blacklist_action.triggered.connect(lambda: self._add_to_blacklist(ip_address))
        menu.addAction(blacklist_action)

        # 加入白名单
        whitelist_action = QAction("✅ 加入白名单", self)
        whitelist_action.triggered.connect(lambda: self._add_to_whitelist(ip_address))
        menu.addAction(whitelist_action)

        # 查看安全状态
        security_action = QAction("🛡️ 查询安全状态", self)
        security_action.triggered.connect(lambda: self._show_security_status_only(ip_address))
        menu.addAction(security_action)

        menu.addSeparator()

        # 复制IP
        copy_action = QAction("📋 复制IP地址", self)
        copy_action.triggered.connect(lambda: self._copy_ip_to_clipboard(ip_address))
        menu.addAction(copy_action)

        # 在线查询子菜单（如果IP地理功能启用）
        if self.ip_geo_manager and get_config_manager().get_config('IP_GEO_CONFIG').search_urls.enabled:
            menu.addSeparator()
            online_menu = QMenu("🛜 在线查询", self)
            search_urls = self.ip_geo_manager.get_search_urls()

            if search_urls:
                for url_info in search_urls:
                    action_name = f"🌐 {url_info.get('name', '未知网站')}"
                    action = QAction(action_name, self)
                    url_name = url_info.get('name')
                    action.triggered.connect(lambda checked, name=url_name:
                                        self._open_online_search(ip_address, name))
                    online_menu.addAction(action)
            else:
                no_urls_action = QAction("⚠ 未配置搜索网址", self)
                no_urls_action.setEnabled(False)
                online_menu.addAction(no_urls_action)

            menu.addMenu(online_menu)

        # 显示菜单
        menu.exec_(self.log_text.mapToGlobal(position))

    def _show_default_menu(self, position):
        """显示默认的右键菜单（只保留复制和全选）"""
        menu = QMenu(self)

        # 复制
        copy_action = QAction("复制", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.log_text.copy)
        copy_action.setEnabled(self.log_text.textCursor().hasSelection())
        menu.addAction(copy_action)

        menu.addSeparator()

        # 全选
        select_all_action = QAction("全选", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.log_text.selectAll)
        menu.addAction(select_all_action)

        menu.addSeparator()

        # 添加字体信息显示
        current_font = self.log_text.font()
        font_label = QAction(f"当前字体: {current_font.family()} {current_font.pointSize()}pt", self)
        font_label.setEnabled(False)
        menu.addAction(font_label)

        # 添加字体大小调整子菜单
        font_menu = QMenu("调整字体大小", self)

        # 放大
        zoom_in_action = QAction(f"放大 (Ctrl+滚轮上 / Ctrl++)", self)
        zoom_in_action.triggered.connect(self.zoom_in)
        font_menu.addAction(zoom_in_action)

        # 缩小
        zoom_out_action = QAction(f"缩小 (Ctrl+滚轮下 / Ctrl+-)", self)
        zoom_out_action.triggered.connect(self.zoom_out)
        font_menu.addAction(zoom_out_action)

        # 重置
        reset_action = QAction(f"重置 (Ctrl+0)", self)
        reset_action.triggered.connect(self.reset_font)
        font_menu.addAction(reset_action)

        menu.addMenu(font_menu)

        menu.exec_(self.log_text.mapToGlobal(position))

    @Slot(str)
    def _view_ip_details(self, ip_address: str):
        """查看IP详情"""
        if not self.ip_geo_manager:
            QMessageBox.warning(self, "功能不可用", "IP地理功能未设置")
            return

        try:
            dialog = IPDetailDialog(ip_address, self.ip_geo_manager, self)
            dialog.exec()
            return

        except Exception as e:
            logger.error(f"显示IP详情失败: {e}", exc_info=True)
            self._show_security_status_only(ip_address)

    @Slot(str, str)
    def _open_online_search(self, ip_address: str, url_name: str):
        """打开在线查询网站"""
        if not self.ip_geo_manager:
            QMessageBox.warning(self, "功能不可用", "IP地理功能未设置")
            return

        try:
            # 使用IP地理管理器的在线搜索功能
            success = self.ip_geo_manager.search_ip_online(ip_address, url_name)

            if success:
                self.statusBar().showMessage(f"🌐 正在打开 {url_name} 查询 {ip_address}...", 3000)
                self.add_log(f"[GEO] 🌐 在线查询 {ip_address} - {url_name}\n")
            else:
                QMessageBox.warning(self, "打开失败", f"无法打开 {url_name} 查询 {ip_address}")

        except Exception as e:
            logger.error(f"打开在线查询失败: {e}")
            QMessageBox.critical(self, "错误", f"打开在线查询失败: {str(e)}")

    def _show_security_status_only(self, ip_address: str):
        """只显示安全状态信息"""
        if not self.security_manager:
            QMessageBox.warning(self, "功能不可用", "安全管理器未设置")
            return

        try:
            details = self.security_manager.get_security_status(ip_address)

            # 构建详细信息文本
            detail_text = f"📡 IP地址: {details['ip']}\n"
            detail_text += "─" * 40 + "\n"

            # 安全状态
            detail_text += f"🔐 安全状态:\n"
            detail_text += f"   白名单: {'✅ 是' if details['in_whitelist'] else '❌ 否'}\n"
            detail_text += f"   黑名单: {'⛔ 是' if details['in_blacklist'] else '✅ 否'}\n"
            detail_text += f"   认证失败次数: {details['failed_attempts']}\n"

            # 封禁信息
            if details['temp_banned']:
                detail_text += "\n🚫 临时封禁信息:\n"
                detail_text += f"   状态: 🔴 已被封禁\n"
                if details.get('ban_remark'):
                    detail_text += f"   原因: {details['ban_remark']}\n"
                if details.get('ban_protocol'):
                    detail_text += f"   协议: {details['ban_protocol']}\n"
                if details.get('unban_time_human'):
                    detail_text += f"   解封时间: {details['unban_time_human']}\n"
                if details.get('remaining_seconds', 0) > 0:
                    minutes = details['remaining_seconds'] // 60
                    seconds = details['remaining_seconds'] % 60
                    detail_text += f"   剩余时间: {minutes}分{seconds}秒\n"
            else:
                detail_text += f"   临时封禁: ✅ 否\n"

            # 扫描信息
            if details['scan_attempts'] > 0:
                detail_text += "\n🛡️ 扫描防护信息:\n"
                detail_text += f"   扫描尝试次数: {details['scan_attempts']}\n"
                if details['scan_types']:
                    detail_text += f"   扫描类型: {', '.join(details['scan_types'])}\n"

            # 显示详情对话框
            QMessageBox.information(self, f"IP安全状态 - {ip_address}", detail_text)

        except Exception as e:
            logger.error(f"获取IP状态失败: {e}")
            QMessageBox.critical(self, "错误", f"获取IP状态失败: {str(e)}")

    @Slot(str)
    def _add_temp_ban(self, ip_address: str):
        """添加临时封禁"""
        if not self.security_manager:
            QMessageBox.warning(self, "功能不可用", "安全管理器未设置")
            return

        try:
            # 检查是否已在黑名单或白名单中
            status = self.security_manager.get_security_status(ip_address)
            if status['in_blacklist']:
                QMessageBox.warning(self, "操作失败", "该IP已在黑名单中")
                return
            if status['in_whitelist']:
                reply = QMessageBox.question(
                    self, "确认操作",
                    "该IP在白名单中，是否仍然添加临时封禁？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            # 请求备注信息
            remark, ok = QInputDialog.getText(
                self, "临时封禁",
                f"请输入封禁原因 (IP: {ip_address}):\n\n建议填写具体的违规行为",
                text="手动添加临时封禁"
            )

            if ok and remark:
                # 添加临时封禁
                self.security_manager.add_temp_ban(ip_address, remark)
                QMessageBox.information(self, "操作成功",
                    f"✅ 已添加临时封禁: {ip_address}\n"
                    f"原因: {remark}\n"
                    f"封禁时长: {self.security_manager.config.auth_failure_detection.http_ban_duration}秒"
                )

                # 在日志中记录
                self.add_log(f"[SECURITY] 🚫 IP {ip_address} 已被添加到临时封禁，原因: {remark}\n")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加临时封禁失败: {str(e)}")

    @Slot(str)
    def _add_to_blacklist(self, ip_address: str):
        """添加到黑名单"""
        if not self.security_manager:
            QMessageBox.warning(self, "功能不可用", "安全管理器未设置")
            return

        try:
            # 请求备注信息
            remark, ok = QInputDialog.getText(
                self, "添加到黑名单",
                f"请输入备注信息 (IP: {ip_address}):\n\n建议填写具体的威胁原因",
                text="恶意IP地址"
            )

            if ok:
                # 检查是否在白名单中
                status = self.security_manager.get_security_status(ip_address)
                if status['in_whitelist']:
                    reply = QMessageBox.question(
                        self, "确认操作",
                        "该IP在白名单中，是否仍然添加到黑名单？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return

                # 添加到黑名单
                if self.security_manager.add_to_blacklist(ip_address, remark):
                    QMessageBox.information(self, "操作成功",
                        f"⛔ 已添加到黑名单: {ip_address}\n"
                        f"备注: {remark}"
                    )

                    # 在日志中记录
                    self.add_log(f"[SECURITY] ⛔ IP {ip_address} 已被添加到黑名单\n")
                else:
                    QMessageBox.warning(self, "操作失败", "添加黑名单失败")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加到黑名单失败: {str(e)}")

    @Slot(str)
    def _add_to_whitelist(self, ip_address: str):
        """添加到白名单"""
        if not self.security_manager:
            QMessageBox.warning(self, "功能不可用", "安全管理器未设置")
            return

        try:
            # 请求备注信息
            remark, ok = QInputDialog.getText(
                self, "添加到白名单",
                f"请输入备注信息 (IP: {ip_address}):\n\n建议填写信任原因",
                text="信任的内网IP"
            )

            if ok:
                # 检查是否在黑名单中
                status = self.security_manager.get_security_status(ip_address)
                if status['in_blacklist']:
                    reply = QMessageBox.question(
                        self, "确认操作",
                        "该IP在黑名单中，是否仍然添加到白名单？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return

                # 添加到白名单
                if self.security_manager.add_to_whitelist(ip_address, remark):
                    QMessageBox.information(self, "操作成功",
                        f"✅ 已添加到白名单: {ip_address}\n"
                        f"备注: {remark}"
                    )

                    # 在日志中记录
                    self.add_log(f"[SECURITY] ✅ IP {ip_address} 已被添加到白名单\n")
                else:
                    QMessageBox.warning(self, "操作失败", "添加白名单失败")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加到白名单失败: {str(e)}")

    @Slot(str)
    def _copy_ip_to_clipboard(self, ip_address: str):
        """复制IP到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(ip_address)
        self.statusBar().showMessage(f"📋 已复制IP地址: {ip_address}", 3000)

    def clear_logs(self):
        """清空日志"""
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有日志吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.log_text.clear()
            self.log_count = 0
            self.update_status()
            self.add_log("[SYSTEM] 📝 日志已清空\n")

    def toggle_pause(self):
        """切换暂停/继续自动滚动"""
        self.auto_scroll = not self.auto_scroll
        if self.auto_scroll:
            self.pause_btn.setText("暂停滚动")
            # 恢复时滚动到底部
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)
            self.add_log("[SYSTEM] 🔄 恢复自动滚动\n")
        else:
            self.pause_btn.setText("继续滚动")
            self.add_log("[SYSTEM] ⏸️ 暂停自动滚动\n")
        self.update_status()

    def export_logs(self):
        """导出日志到文件"""
        try:
            # 获取日志内容
            log_content = self.log_text.toPlainText()

            if not log_content.strip():
                QMessageBox.warning(self, "导出失败", "没有日志内容可导出")
                return

            # 弹出文件保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出日志",
                f"proxy_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;All Files (*)"
            )

            if file_path:
                # 确保文件扩展名
                if not file_path.lower().endswith('.txt'):
                    file_path += '.txt'

                # 写入文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 60 + "\n")
                    f.write("Python 代理服务日志导出\n")
                    f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(log_content)

                # 显示成功消息
                QMessageBox.information(
                    self,
                    "导出成功",
                    f"✅ 日志已成功导出到:\n{file_path}\n\n"
                    f"共 {len(log_content.splitlines())} 行日志"
                )

                # 在日志中记录
                self.add_log(f"[SYSTEM] 💾 日志已导出到: {file_path}\n")

        except Exception as e:
            QMessageBox.critical(
                self,
                "导出失败",
                f"导出日志时发生错误:\n{str(e)}"
            )

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 记录窗口关闭
        logger.debug("日志窗口已关闭")
        event.accept()
