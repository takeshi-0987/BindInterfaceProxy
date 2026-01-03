# -*- coding: utf-8 -*-
"""
Module: tray_icon.py
Author: Takeshi
Date: 2025-12-26

Description:
    系统托盘模块
"""

import os
import sys
import json
import logging

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (QSystemTrayIcon, QMenu, QMessageBox)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QTimer
from typing import Optional, Dict, Any

from defaults.ui_default import MENU_REFRESH_INTERVAL, TRAY_ICON_MAPPING
from defaults.user_default import USER_CONFIG_FILE
from defaults.config_manager import get_config_manager

logger = logging.getLogger(__name__)

class SystemTray:
    """系统托盘管理"""

    def __init__(self, app, proxy_manager, log_window, bind_interface, context):
        self.app = app
        self.proxy_manager = proxy_manager
        self.health_checker = context.health_checker
        self.user_manager = context.user_manager
        self.security_manager = context.security_manager
        self.ip_geo_manager = context.ip_geo_manager
        self.log_window = log_window
        self.bind_interface = bind_interface
        self.status_signals = context.status_signals
        self.stats_manager = context.stats_manager

        self.icon_mapping = TRAY_ICON_MAPPING
        self.current_icon_state = 'unknown'

        # 图标目录
        self.icon_dir = Path("resources/icons")
        self.icon_dir.mkdir(parents=True, exist_ok=True)
        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon()
        self.tray_menu = QMenu()

        # 对话框列表，防止对话框资源提前回收
        self._dialog_list = []

        self.setup_tray()

    def setup_tray(self):
        """设置系统托盘"""
        # 初始图标
        self.update_tray_icon()
        self.tray_icon.setToolTip("BindInterfaceProxy\n统一网络出口")

        # 连接信号
        self.tray_icon.activated.connect(self.on_tray_activated)

        # 设置菜单
        self.tray_icon.setContextMenu(self.tray_menu)

        # 如果是Linux实例，应用Hide-Show修复托盘图标无响应
        if sys.platform == "linux":
            logger.info("Linux系统：应用Hide-Show修复")

            # 显示 → 隐藏 → 再显示
            self.tray_icon.show()
            QTimer.singleShot(300, self.tray_icon.hide)
            QTimer.singleShot(600, self.tray_icon.show)
        else:
            # 正常显示
            self.tray_icon.show()

        # 定时更新菜单
        self.menu_timer = QTimer()
        self.menu_timer.timeout.connect(self.update_tray_menu)
        # 菜单更新频率
        self.menu_timer.start(MENU_REFRESH_INTERVAL)

    def get_icon_state(self):
        """获取图标应该显示的状态"""
        # 1. 检查是否有运行的代理
        running_count = self.proxy_manager.get_running_count()

        if running_count == 0:
            return 'all_stopped'

        # 2. 如果有运行的代理，检查健康状态
        try:
            health_info = self.health_checker.get_health_info()
            health_status = health_info.get('status', 'unknown')
            return health_status
        except Exception as e:
            logger.error(f"获取健康状态失败: {e}")
            return 'unknown'

    def update_tray_icon(self):
        """更新托盘图标"""
        # 获取应该显示的状态
        icon_state = self.get_icon_state()

        # 如果状态没有变化，不需要更新
        if icon_state == self.current_icon_state:
            return

        self.current_icon_state = icon_state

        # 获取图标路径
        icon_path = self.icon_mapping.get(icon_state, self.icon_mapping['unknown'])

        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # 创建后备图标
            self._create_fallback_icon(icon_state)

        logger.debug(f"托盘图标更新为: {icon_state}")

    def _create_fallback_icon(self, state):
        """创建后备颜色图标"""
        colors = {
            'all_stopped': QColor(128, 128, 128),    # 灰色 - 所有停止
            'healthy': QColor(0, 120, 215),          # 蓝色 - 正常
            'unhealthy': QColor(200, 50, 50),        # 红色 - 异常
            'checking': QColor(255, 185, 0),         # 黄色 - 检测中
            'unknown': QColor(0, 120, 215),          # 蓝色 - 未知
        }

        color = colors.get(state, QColor(128, 128, 128))

        # 创建32x32图标
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 画圆形背景
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 32, 32)

        # 添加白色"BIP"文字
        painter.setPen(QPen(Qt.white, 1))

        # 设置字体 - 使用粗体，稍微小一点以适应圆形
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(14)  # 调整字体大小
        painter.setFont(font)

        # 计算文字位置居中
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "BIP")

        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))

    def on_tray_activated(self, reason):
        """处理托盘图标点击事件"""
        try:
            if reason == QSystemTrayIcon.Trigger:  # 左键单击
                # 切换日志窗口显示状态
                self.toggle_log_window()

        except Exception as e:
            logger.error(f"处理托盘点击事件时出错: {e}")

    def toggle_log_window(self):
        """切换日志窗口显示状态"""
        if get_config_manager().get_config('LOG_CONFIG').ui.enabled is False:
            QMessageBox.information(None, "信息", "界面日志功能未启用，请先在设置中启用该功能。")
            return

        if self.log_window.isVisible():
            self.log_window.hide()
        else:
            self.show_log_window()

    def show_log_window(self):
        """显示日志窗口"""
        if get_config_manager().get_config('LOG_CONFIG').ui.enabled is False:
            QMessageBox.information(None, "信息", "界面日志功能未启用，请先在设置中启用该功能。")
            return

        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def update_tray_menu(self):
        """更新托盘菜单"""
        self.tray_menu.clear()

        # 获取代理统计信息
        running_count = self.proxy_manager.get_running_count()
        total_count = self.proxy_manager.get_total_count()
        auth_count = self.proxy_manager.get_auth_count()
        security_count = self.proxy_manager.get_security_count()

        # 获取用户数量
        # user_count = password_manager.get_user_count()

        # 获取安全检查模式
        security_mode = self.security_manager.get_stats()['security_mode']


        # 健康检查是否开启
        health_text = "自动" if self.health_checker.config.enabled else "手动"

        # 获取健康状态
        health_info = self.health_checker.get_health_info()
        health_status = health_info['status']
        last_check_time = health_info['last_check']
        # 距离上次检查经过了多长时间
        if last_check_time:
            last_check_uptime = self.health_checker.get_formatted_check_time(only_time=True)
            last_check_upt_str = f"(上次检查：{last_check_uptime})"
        else:
            last_check_upt_str = '(从未检查)'

        # 根据健康状态更新图标颜色
        security_text = {
            "whitelist": "白名单",
            "blacklist": "黑名单",
            "mixed": "混合",
        }.get(security_mode, "未知")

        # 健康状态文本
        status_text = {
            "healthy": "💚 网络通畅",
            "unhealthy": "💔 网络不通",
            "checking": "🔄 检测中",
            "unknown": "❓ 未知"
        }.get(health_status, "未知")


        # 更新工具提示
        tooltip = (f"BindInterfaceProxy\n"
                   f"目标网卡: {self.bind_interface.iface_name}\n"
                   f"目标地址: {self.bind_interface.ip}:{self.bind_interface.port}\n"
                   f"网络: {status_text}\n"
                   f"运行: {running_count}/{total_count}\n"
                   f"认证: {auth_count}/{total_count}\n"
                   f"安全管理 {security_count}/{total_count}\n"
                   f"健康检查: {health_text}")
        self.tray_icon.setToolTip(tooltip)

        # 标题行
        title_action = self.tray_menu.addAction(f"BindInterfaceProxy - 目标接口: {self.bind_interface.iface_name} - {self.bind_interface.ip}:{self.bind_interface.port}")
        title_action.setEnabled(False)

        network_health_action = self.tray_menu.addAction(f"📶 网络状态: {status_text} {last_check_upt_str}")
        network_health_action.setEnabled(False)

        status_action = self.tray_menu.addAction(
            f"🌐 运行: {running_count}/{total_count}, 认证: {auth_count}/{total_count}, 安全管理: {security_count}/{total_count}")
        status_action.setEnabled(False)

        self.tray_menu.addSeparator()

        # 用户管理
        user_management_action = self.tray_menu.addAction(f"👤 用户管理")
        user_management_action.triggered.connect(self.show_user_manager)

        security_action = self.tray_menu.addAction(f"🛡️ 安全管理（模式: {security_text}）")
        security_action.triggered.connect(self.show_security_manager)

        self.tray_menu.addSeparator()

        # 统计监控
        stats_action =  self.tray_menu.addAction("📊 连接流量统计")
        stats_action.triggered.connect(self.show_stats_dialog)

        # 网络健康度检查
        stats_action =  self.tray_menu.addAction(f"🔍 网络健康度检查 ({health_text})")
        stats_action.triggered.connect(self.show_healthcheck_dialog)

        self.tray_menu.addSeparator()

        # 一键操作
        if running_count > 0:
            stop_all_action = self.tray_menu.addAction("⏹️ 一键停止所有代理")
            stop_all_action.triggered.connect(self.stop_all_proxies)
        else:
            start_all_action = self.tray_menu.addAction("▶️ 一键启动所有代理")
            start_all_action.triggered.connect(self.start_all_proxies)


        self.tray_menu.addSeparator()

        for config_id, worker in self.proxy_manager.proxy_workers.items():
            # 运行状态图标
            if worker.status == "running":
                status_icon = "🟢"
            elif worker.status == "starting":
                status_icon = "🟡"
            elif worker.status == "error":
                status_icon = "🔴"
            else:
                status_icon = "⚫"

            proxy_kind = worker.kind
            if proxy_kind == "http":
                if getattr(worker.interface, "use_https", False):
                    proxy_kind = "https"

            proxy_name = f"{worker.interface.proxy_name or 'Unknown'}" if hasattr(worker.interface, 'proxy_name') else "Unknown"
            address = f"{worker.interface.ip}:{worker.interface.port}"

            # 认证状态
            auth_enabled = worker.get_auth_status()
            auth_icon = "👤✔️" if auth_enabled else "👤✖️"
            auth_status = "启用" if auth_enabled else "停用"

            # 安全管理状态
            security_enabled = worker.get_security_status()
            security_icon = "🛡️✔️" if security_enabled else "🛡️✖️"
            security_status = "启用" if security_enabled else "停用"

            # 创建代理菜单项
            proxy_action = self.tray_menu.addAction(f"{status_icon} [{proxy_kind}] {proxy_name} - {address}  {auth_icon}  {security_icon}")

            # 创建子菜单
            proxy_menu = QMenu(f"{proxy_name} - {address}")

            # 操作按钮
            if worker.status in ["running", "starting"]:
                stop_action = proxy_menu.addAction("⏹️ 停止")
                stop_action.triggered.connect(lambda checked, cid=config_id: self.stop_proxy(cid))

            if worker.status in ["stopped", "error"]:
                start_action = proxy_menu.addAction("▶️ 启动")
                start_action.triggered.connect(lambda checked, cid=config_id: self.start_proxy(cid))

            restart_action = proxy_menu.addAction("🔄 重启")
            restart_action.triggered.connect(lambda checked, cid=config_id: self.restart_proxy(cid))

            proxy_action.setMenu(proxy_menu)

            # 认证切换按钮
            auth_toggle_text = f"⛔ 停用认证" if auth_enabled else f"👤 启用认证"
            auth_toggle_action = proxy_menu.addAction(auth_toggle_text)
            auth_toggle_action.triggered.connect(lambda checked, cid=config_id: self.toggle_proxy_auth(cid))

            # 认证切换按钮
            security_toggle_text = f"⛔ 停用安全管理" if security_enabled else f"🛡️ 启用安全管理"
            security_toggle_action = proxy_menu.addAction(security_toggle_text)
            security_toggle_action.triggered.connect(lambda security, cid=config_id: self.toggle_proxy_security(cid))

            proxy_menu.addSeparator()

            # 状态信息
            status_action = proxy_menu.addAction(f"运行状态: {worker.status}")
            status_action.setEnabled(False)

            # 认证状态和控制
            auth_status_action = proxy_menu.addAction(f"认证状态: {auth_status}")
            auth_status_action.setEnabled(False)

            # 安全管理状态
            security_status_action = proxy_menu.addAction(f"认证状态: {security_status}")
            security_status_action.setEnabled(False)

            # 运行时间
            if worker.start_time and worker.status in ["running", "starting"]:
                uptime_str = self._format_uptime(worker.start_time)

                uptime_action = proxy_menu.addAction(f"运行时间: {uptime_str}")
                uptime_action.setEnabled(False)

                if proxy_kind == "https":
                    # 证书信息
                    cert_file = getattr(worker.interface, 'cert_file', '未知')
                    key_file = getattr(worker.interface, 'key_file', '未知')

                    import os
                    cert_status = "✅ 已配置" if os.path.exists(cert_file) else "❌ 缺失"
                    key_status = "✅ 已配置" if os.path.exists(key_file) else "❌ 缺失"

                    cert_action = proxy_menu.addAction(f"证书: {cert_status}")
                    cert_action.setEnabled(False)
                    key_action = proxy_menu.addAction(f"私钥: {key_status}")
                    key_action.setEnabled(False)

        self.tray_menu.addSeparator()

        # 查看日志
        view_logs_action = self.tray_menu.addAction("📋 查看日志")
        view_logs_action.triggered.connect(self.show_log_window)

        # 添加设置菜单项
        settings_action = self.tray_menu.addAction("⚙️ 设置")
        settings_action.triggered.connect(self.show_settings_dialog)

        self.tray_menu.addSeparator()

        # 重启按钮
        restart_action = self.tray_menu.addAction("🔄 重启程序")
        restart_action.triggered.connect(self.perform_restart)

        # 退出按钮
        exit_action = self.tray_menu.addAction("❌ 退出")
        exit_action.triggered.connect(self.quit_app)

    def _format_uptime(self, start_time: datetime) -> str:
        """格式化显示时间"""
        uptime = datetime.now() - start_time
        total_seconds = int(uptime.total_seconds())

        if total_seconds < 60:
            uptime_str = f"{total_seconds}秒"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            uptime_str = f"{minutes}分钟"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            uptime_str = f"{hours}小时{minutes}分钟"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            uptime_str = f"{days}天{hours}小时{minutes}分钟"
        return uptime_str

    def on_proxy_status_changed(self):
        """处理代理状态变化"""
        self.update_tray_icon()
        self.update_tray_menu()

    def on_health_changed(self, health_status):
        """处理健康状态改变"""
        logger.debug(f"网络健康状态: {health_status}")
        self.update_tray_icon()
        self.update_tray_menu()

    def load_config_from_file(self) -> Optional[Dict[str, Any]]:
        """从配置文件加载配置"""
        config_path = USER_CONFIG_FILE

        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            if not isinstance(config_data, dict):
                logger.error(f"配置文件格式错误: {config_path}")
                return None

            logger.info(f"从文件加载配置: {config_path}")
            return config_data

        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON解析错误: {config_path}, 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"加载配置文件失败: {config_path}, 错误: {e}")
            return None


    def stop_proxy(self, config_id):
        """停止指定代理"""
        self.proxy_manager.stop_proxy(config_id)


    def start_proxy(self, config_id):
        """启动指定代理"""
        self.proxy_manager.start_proxy(config_id)


    def restart_proxy(self, config_id):
        """重启指定代理"""
        self.proxy_manager.restart_proxy(config_id)


    def stop_all_proxies(self):
        self.proxy_manager.stop_all_proxies()


    def start_all_proxies(self):
        self.proxy_manager.start_all_proxies()


    def restart_all_proxies(self):
        self.proxy_manager.restart_all_proxies()


    def toggle_proxy_auth(self, config_id):
        """切换指定代理的认证状态"""
        if config_id in self.proxy_manager.proxy_workers:
            worker = self.proxy_manager.proxy_workers[config_id]

            # 需要启用认证时检测用户管理
            if not worker.get_auth_status():
                user_count = self.user_manager.get_user_count()
                logger.info(f"当前用户数量: {user_count}")

                if user_count == 0:
                    logger.info("未找到用户配置，需要先添加用户")

                    # 使用UserManagerDialog，并设置require_first_user=True
                    from ui.user_manager_dialog import UserManagerDialog
                    dialog = UserManagerDialog(self.user_manager, require_first_user=True)
                    result = dialog.exec()

                    user_count = self.user_manager.get_user_count()
                    if user_count == 0:
                        logger.info("用户取消配置，无法切换认证")
                        QMessageBox.information(None, "提示", "没有设置用户，无法开启认证")
                        return
                    else:
                        logger.info(f"用户配置完成，当前用户数量: {user_count}")

            new_status = worker.toggle_auth()
            status_text = "启用" if new_status else "停用"

            # 重启代理以应用新的认证设置
            worker.restart()
            logger.info(f"接口 {config_id} 认证已{status_text}，正在重启...")

            # 保存切换后的状态
            proxy_kind, i = config_id.split('_')
            proxy_config = proxy_kind.upper() + "_PROXY_CONFIG"
            proxy_need_change = i + ".auth_enabled"
            get_config_manager().update_config(proxy_config, proxy_need_change, new_status)
            get_config_manager().save()

            # 更新托盘菜单
            QTimer.singleShot(2000, self.update_tray_menu)


    def toggle_proxy_security(self, config_id):
        """切换指定代理的安全管理状态"""
        if config_id in self.proxy_manager.proxy_workers:
            worker = self.proxy_manager.proxy_workers[config_id]
            new_status = worker.toggle_security()
            status_text = "启用" if new_status else "停用"

            # 重启代理以应用新的安全管理设置
            worker.restart()
            logger.info(f"接口 {config_id} 安全管理已{status_text}，正在重启...")

            # 保存切换后的状态
            proxy_kind, i = config_id.split('_')
            proxy_config = proxy_kind.upper() + "_PROXY_CONFIG"
            proxy_need_change = i + ".security_enabled"
            get_config_manager().update_config(proxy_config, proxy_need_change, new_status)
            get_config_manager().save()

            # 更新托盘菜单
            QTimer.singleShot(2000, self.update_tray_menu)

    def manual_health_check(self):
        """手动立即执行健康检查"""
        logger.info("手动触发网络连通性检查")
        self.health_checker._perform_check()
        self.update_tray_menu()


    def show_user_manager(self):
        """显示用户管理对话框"""
        try:
            from ui.user_manager_dialog import UserManagerDialog
            dialog = UserManagerDialog(self.user_manager, require_first_user=False)
            dialog.exec()

        except Exception as e:
            logger.error(f"打开用户管理失败: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "错误", f"打开用户管理失败: {e}")


    def show_healthcheck_dialog(self):
        """显示健康度检查对话框"""
        try:
            from ui.healthcheck_dialog import HealthCheckDialog
            dialog = HealthCheckDialog(self.health_checker)
            self._dialog_list.append(dialog)
            # 连接 finished 信号
            dialog.finished.connect(lambda: self._on_dialog_closed(dialog))
            dialog.show()
        except Exception as e:
            logger.error(f"打开健康度检查失败: {e}")
            QMessageBox.warning(None, "错误", f"打开健康度检查失败: {e}")

    def show_security_manager(self):
        """显示安全管理对话框"""
        try:
            from ui.security_manager_dialog import SecurityManagerDialog
            dialog = SecurityManagerDialog(self.security_manager, self.ip_geo_manager, self.status_signals)
            self._dialog_list.append(dialog)
            # 连接 finished 信号
            dialog.finished.connect(lambda: self._on_dialog_closed(dialog))
            dialog.show()
        except Exception as e:
            logger.error(f"打开安全管理失败: {e}")
            QMessageBox.warning(None, "错误", f"打开安全管理失败: {e}")

    def show_stats_dialog(self):
        """显示统计对话框"""
        if get_config_manager().get_config('STATS_CONFIG').enable_stats is False:
            QMessageBox.information(None, "信息", "连接流量统计功能未启用，请先在设置中启用该功能。")
            return
        try:
            from .stats_dialog import MonitorDialog
            dialog = MonitorDialog(self.stats_manager)
            self._dialog_list.append(dialog)
            # 连接 finished 信号
            dialog.finished.connect(lambda: self._on_dialog_closed(dialog))
            dialog.show()
        except:
            logger.error(f"打开连接和流量统计失败: {e}")
            QMessageBox.warning(None, "错误", f"打开连接和流量统计失败: {e}")

    def _on_dialog_closed(self, dialog):
        """对话框关闭时的处理"""
        logger.debug(f"对话框关闭: {dialog}")

        # 从列表中移除
        if hasattr(self, '_dialog_list') and dialog in self._dialog_list:
            self._dialog_list.remove(dialog)
            logger.debug(f"{dialog}从列表移除，剩余: {len(self._dialog_list)}个")

    def quit_app(self):
        """退出程序"""
        message_box = QMessageBox()
        message_box.setWindowTitle("退出确认")
        message_box.setText("确定要退出代理服务器吗？")
        message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        # 获取按钮并单独设置样式
        yes_button = message_box.button(QMessageBox.Yes)
        no_button = message_box.button(QMessageBox.No)

        # 设置按钮文本
        yes_button.setText("是")
        no_button.setText("否")

        # 简洁的样式表 - 只改变悬停颜色
        yes_style = """
            QPushButton:hover {
                background-color: #ffebee;
                color: #d32f2f;
            }
        """

        no_style = """
            QPushButton:hover {
                background-color: #e8f5e8;
                color: #388e3c;
            }
        """

        yes_button.setStyleSheet(yes_style)
        no_button.setStyleSheet(no_style)

        reply = message_box.exec()

        if reply == QMessageBox.Yes:
            # logger.info("🚪 正在退出...")
            try:
                from utils.lifecycle_manager import get_applifecycle_manager
                get_applifecycle_manager().quit_app()
            except:
                try:
                    self.tray_icon.hide()
                    self.log_window.close()
                except:
                    pass
                os._exit(0)


    def show_settings_dialog(self):
        """显示设置对话框"""
        try:
            from ui.settings_dialog import SettingsDialog

            current_config = self.load_config_from_file()
            dialog = SettingsDialog(self.user_manager, current_config)
            self._dialog_list.append(dialog)
            # 连接 finished 信号
            dialog.finished.connect(lambda: self._on_dialog_closed(dialog))
            dialog.show()

        except Exception as e:
            logger.error(f"打开设置失败: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "错误", f"打开设置失败: {e}")


    def perform_restart(self):
        """执行重启程序"""

        # 创建自定义消息框
        msg_box = QMessageBox()
        msg_box.setWindowTitle("重启确认")
        msg_box.setText("确定要重启代理服务器吗？\n程序将自动重新启动。")
        msg_box.setIcon(QMessageBox.Question)

        yes_btn = msg_box.addButton("确定", QMessageBox.YesRole)
        no_btn = msg_box.addButton("取消", QMessageBox.NoRole)
        msg_box.setDefaultButton(no_btn)

        msg_box.exec()

        # 判断哪个按钮被点击
        if msg_box.clickedButton() == yes_btn:
            logger.info("用户确认重启程序...")
            from utils.lifecycle_manager import get_applifecycle_manager
            get_applifecycle_manager().restart()
        else:
            logger.info("用户取消重启操作")
