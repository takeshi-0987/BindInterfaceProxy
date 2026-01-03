# -*- coding: utf-8 -*-
"""
Module: main.py
Author: Takeshi
Date: 2025-12-14

Description:
    BindInterfaceProxy 主程序入口
    此程序是自由软件：您可以根据自由软件基金会发布的 GNU 通用公共许可证条款重新发布和/或修改它；
    可以是该许可证的第3版，也可以是（在您的选择下）任何更新的版本。

    本程序是基于希望它有用而发布的，但没有任何保证；甚至没有对适销性或特定用途适用性的暗示保证。
    有关更多详细信息，请参阅 GNU 通用公共许可证。

    您应该已经收到一份 GNU 通用公共许可证的副本以及此程序。
    如果没有，请参阅 <http://www.gnu.org/licenses/>。
"""

import sys
import os
import logging
import traceback

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# === Qt 导入===
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer

# === 导入项目模块 ===
try:
    from defaults.config_manager import get_config_manager
    from utils.lifecycle_manager import get_applifecycle_manager
    from utils.startup_manager import StartupManager
    from utils.font_manager import FontManager

    from core import ProxyManager, DNSResolver
    from managers import (
        IPGeoManager,
        SecurityManager,
        StatsManager,
        HealthChecker,
        LoggingManager,
        UserManager,
        LogSignals,
        StatusSignals,
    )

    from ui import LogWindow, ErrorDialog, SystemTray, SettingsDialog, UserManagerDialog
    from utils import NetworkInterface
    from managers.context import ManagerContext

except Exception as e:
    error_msg = traceback.format_exc()
    print("=" * 60)
    print("程序启动失败！")
    print("导入阶段错误信息：")
    print(error_msg)
    print("=" * 60)
    input("按回车键退出...")
    sys.exit(1)

logger = logging.getLogger(__name__)

# === 主应用类 ===
class MainProxyApp:
    def __init__(self):
        # 创建 QApplication 并保存为实例属性
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # 加载配置管理
        self.config_manager = get_config_manager()

        # 登记重启和关闭管理
        get_applifecycle_manager().register_app(self)
        # 登记系统中断信号
        get_applifecycle_manager().setup_signal_handlers()

        # 初始化启动管理器
        self.startup_manager = StartupManager()
        self.startup_manager.finished.connect(self._on_startup_finished)

        # 显示启动窗口
        self.startup_manager.show()

        # 异步初始化
        QTimer.singleShot(100, self._async_initialize)

    def _on_startup_finished(self):
        """启动窗口关闭完成回调"""
        logger.debug("启动窗口已完全关闭")

    def _async_initialize(self):
        """初始化"""
        try:
            self._update_startup_progress("🚀 开始启动代理服务器...", 10)

            # 加载配置
            self._update_startup_progress("加载配置文件...", 20)
            self.config_dict = self.config_manager.get_all_dicts()
            self._log_config_summary()

            #  初始化用户管理器
            from defaults.user_default import USERS_FILE
            self.user_manager = UserManager(USERS_FILE)

            #  检查配置完整性
            self._update_startup_progress("检查配置完整性...", 30)
            config_complete, missing_item = self.config_manager.validate_completeness()

            has_auth = self.config_manager.has_auth_config()

            # 如果配置不完整，进入引导流程
            if not config_complete:
                logger.info(f"配置不完整，缺少: {missing_item}")
                self.startup_manager.close()
                if not self._run_setup_guide(missing_item=missing_item):
                    # 如果_run_setup_guide没有注册退出
                    get_applifecycle_manager().quit_app()
                return


            # 启用用户认证，但未配置用户，进入引导流程
            if has_auth:
                user_count = self.user_manager.get_user_count()
                if user_count == 0:
                    logger.info(f"启用用户认证，但未配置用户")
                    self.startup_manager.close()
                    if not self._run_setup_guide(user_reason=True):
                        get_applifecycle_manager().quit_app()
                    return

            # 初始化组件
            self._update_startup_progress("初始化组件...", 50)

            # 1. 初始化信号
            self.log_signals = LogSignals()
            self.status_signals = StatusSignals()

            # 2. 初始化日志管理器
            log_config = self.config_manager.get_config('LOG_CONFIG')
            self.logging_manager = LoggingManager(self.log_signals)
            self.logging_manager.setup_logging(log_config)


            # 3. 初始化绑定网络接口
            bind_config = self.config_manager.get_config_dict('BIND_INTERFACE_CONFIG')
            self.bind_interface = NetworkInterface(**bind_config)

            # 4. 初始化DNS解析器
            dns_config = self.config_manager.get_config('DNS_CONFIG')
            self.dns_resolver = DNSResolver(dns_config)

            # 5 初始化各类管理器
            ip_geo_config = self.config_manager.get_config('IP_GEO_CONFIG')
            self.ip_geo_manager = IPGeoManager(ip_geo_config)

            security_config = self.config_manager.get_config('SECURITY_CONFIG')
            self.security_manager = SecurityManager(security_config)

            stats_config = self.config_manager.get_config('STATS_CONFIG')
            self.stats_manager = StatsManager(stats_config)

            healthcheck_config = self.config_manager.get_config('HEALTH_CHECK_CONFIG')
            self.health_checker = HealthChecker(
                healthcheck_config,
                self.bind_interface,
                self.dns_resolver,
                self.ip_geo_manager,
                self.status_signals
            )

            # 6. 初始化日志窗口
            self.log_window = LogWindow(log_config.ui, self.security_manager, self.ip_geo_manager)
            self.log_window.hide()
            self.log_window.setAttribute(Qt.WA_QuitOnClose, False)

            # 7. 初始化管理器上下文
            self.context = ManagerContext()
            self.context.initialize(
                user_manager=self.user_manager,
                security_manager=self.security_manager,
                health_checker=self.health_checker,
                stats_manager=self.stats_manager,
                ip_geo_manager=self.ip_geo_manager,
                log_signals=self.log_signals,
                status_signals=self.status_signals,
            )

            # 8. 初始化代理管理器
            self.proxy_manager = ProxyManager(self.bind_interface, self.dns_resolver,
                                              self.context, self.status_signals)

            self._update_startup_progress("初始化系统托盘...", 70)
            # 9. 初始化系统托盘
            self.tray_icon = SystemTray(
                app=self.app,
                proxy_manager=self.proxy_manager,
                log_window=self.log_window,
                bind_interface=self.bind_interface,
                context=self.context,
            )

            # 10. 设置信号连接
            self.log_signals.new_log.connect(self.log_window.add_log)
            logger.debug("new_log 信号连接到 ui.log_window.add_log")

            self.status_signals.health_changed.connect(self.tray_icon.on_health_changed)
            logger.debug("health_changed 信号连接到 ui.tray_icon.on_health_changed")

            self.status_signals.proxy_status_changed.connect(self.tray_icon.on_proxy_status_changed)
            logger.debug("status_signals 信号连接到 ui.tray_icon.on_proxy_status_changed")

            self.status_signals.security_changed.connect(self.tray_icon.update_tray_menu)
            logger.debug("security_changed 信号连接到 ui.tray_icon.update_tray_menu")

            # 启动代理服务
            self._update_startup_progress("启动代理服务...", 80)
            socks_proxies_list = self.config_manager.get_config_dict('SOCKS5_PROXY_CONFIG')
            http_proxies_list = self.config_manager.get_config_dict('HTTP_PROXY_CONFIG')
            self.proxy_manager.setup_proxies(socks_proxies_list, http_proxies_list)
            self.proxy_manager.start_all_proxies()

            #  启动健康检查
            self._update_startup_progress("启动健康检查...", 90)
            QTimer.singleShot(5000, self.health_checker.first_start_and_check)

            # 更新托盘菜单
            self.tray_icon.update_tray_menu()
            self._update_startup_progress("✅ 代理程序启动完成", 100)
            logger.info("✅ 代理程序启动完成")

            # 延迟关闭启动窗口
            QTimer.singleShot(1500, self.startup_manager.close)

        except Exception as e:
            logger.error(f"启动代理服务器失败: {e}")
            self._update_startup_progress(f"❌ 启动失败: {str(e)[:50]}", 0)
            QTimer.singleShot(2000, self.startup_manager.close)


    def _update_startup_progress(self, message: str, progress: int = None):
        """更新进度"""
        if hasattr(self, 'startup_manager'):
            self.startup_manager.update(message, progress)

    def _log_config_summary(self):
        """记录配置摘要"""
        try:
            socks_count = len(self.config_dict.get('SOCKS5_PROXY_CONFIG', []))
            http_count = len(self.config_dict.get('HTTP_PROXY_CONFIG', []))
            bind_interface = self.config_dict.get('BIND_INTERFACE_CONFIG', {})
            bind_info = bind_interface.get('iface_name', bind_interface.get('ip', '未设置'))

            logger.info(f"配置加载: SOCKS5代理={socks_count}个, HTTP代理={http_count}个, 出口接口={bind_info}")
        except Exception as e:
            logger.error(f"记录配置摘要失败: {e}")

    def _run_setup_guide(self, missing_item: str = '', user_reason: bool = False) -> bool:
        """运行配置引导流程，返回的是bool表示是否已经注册延迟退出程序
        """
        try:
            # 创建一个自定义的消息框
            msg_box = QMessageBox()
            msg_box.setWindowTitle("配置代理")

            if user_reason:
                msg_box.setText("代理启用了用户认证，但没有添加用户，\n需要取消用户认证或添加用户才能运行。\n是否立即进行配置？")
            else:
                msg_box.setText(f"{missing_item}配置信息不完整，\n需要配置代理服务器才能运行。\n是否立即进行配置？")

            msg_box.setIcon(QMessageBox.Question)

            # 设置中文按钮
            yes_btn = msg_box.addButton("是", QMessageBox.YesRole)
            no_btn = msg_box.addButton("否", QMessageBox.NoRole)
            msg_box.setDefaultButton(yes_btn)

            msg_box.exec()

            # 判断哪个按钮被点击了
            clicked_btn = msg_box.clickedButton()

            # 如果选是
            if clicked_btn == yes_btn:
                # 从ConfigManager获取当前配置字典
                current_config = self.config_manager.get_all_dicts()

                dialog = SettingsDialog(self.user_manager, current_config)
                result = dialog.exec()

                # 检查设置页面是否触发了重启
                if get_applifecycle_manager().should_restart():
                    logger.info("设置页面重启流程已启动")
                    return True

                else:
                    logger.info("设置页面用户未选择重启，即将退出程序...")
                    return False

            # 如果选否
            else:
                logger.info("用户选择不配置代理，程序退出")
                get_applifecycle_manager().quit_app()
                return True

        except Exception as e:
            logger.error(f"配置引导失败: {e}")
            get_applifecycle_manager().quit_app()
            return True


    def quit_app(self):
        """标准退出流程"""

        logger.info("正在退出程序...")

        try:
            # 停止健康检查
            if hasattr(self, 'health_checker') and self.health_checker:
                self.health_checker.stop()
                logger.info("✓ 健康检查器已停止")

            # 停止所有代理
            if hasattr(self, 'proxy_manager') and self.proxy_manager:
                self.proxy_manager.stop_all_proxies()
                logger.info("✓ 代理服务已停止")

            # 关闭统计管理器
            if hasattr(self, 'stats_manager') and self.stats_manager:
                self.stats_manager.stop()
                logger.info("✓ 统计管理器已停止")

            # 关闭安全管理器
            if hasattr(self, 'security_manager') and self.security_manager:
                self.security_manager.stop()
                logger.info("✓ 安全管理器已停止")

            # 关闭ip地理器
            if hasattr(self, 'ip_geo_manager') and self.ip_geo_manager:
                self.ip_geo_manager.close()
                logger.info("✓ IP地理解析已停止")

            # 关闭DNS解析器
            if hasattr(self, 'dns_resolver') and self.dns_resolver:
                self.dns_resolver.shutdown()
                logger.info("✓ DNS解析器已停止")

            # 关闭日志窗口
            if hasattr(self, 'log_window') and self.log_window:
                self.log_window.close()
                logger.info("✓ 日志窗口已关闭")

            # 清理托盘图标
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.tray_icon.hide()
                logger.info("✓ 托盘图标已清理")

            logger.info("✅ 所有服务已停止")

        except Exception as e:
            logger.error(f"退出应用时发生错误: {e}")

        finally:
            # 关闭日志系统
            logger.info("✓ 退出日志系统……")
            if hasattr(self, 'logging_manager') and self.logging_manager:
                self.logging_manager.shutdown()

            # 请求 Qt 退出事件循环
            self.app.quit()

    def run(self):
        """启动事件循环"""
        return self.app.exec()


# === 主函数 ===
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [PID:%(process)d] %(name)s - %(levelname)s - %(message)s'
    )
    # 显示当前 PID
    logger.info(f"🚀 应用程序启动，当前进程 PID: {os.getpid()}")

    # Wayland 兼容性处理
    if sys.platform == "linux":
        # 检查桌面环境
        session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        wayland_display = os.environ.get('WAYLAND_DISPLAY')

        if session_type == 'wayland' or wayland_display:
            logger.info(f"检测到Wayland会话: XDG_SESSION_TYPE={session_type}, WAYLAND_DISPLAY={wayland_display}")

            # 优先尝试XWayland
            if 'DISPLAY' in os.environ and os.environ['DISPLAY']:
                logger.info("Wayland环境：尝试使用XWayland (xcb)")
                os.environ['QT_QPA_PLATFORM'] = 'xcb'
            else:
                logger.warning("Wayland环境且没有XWayland，系统托盘可能不可用")

                # 尝试设置Wayland的SNI支持
                os.environ['QT_QPA_PLATFORM'] = 'wayland'
                os.environ['QT_WAYLAND_DISABLE_WINDOWDECORATION'] = '1'

    # 创建 QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 设置全局字体
    font_manager = FontManager.get_instance()
    font_manager.setup_application_font(app, point_size=9)

    # Linux系统托盘检查，不支持托盘无法启动
    if sys.platform == "linux":
        from PySide6.QtWidgets import QSystemTrayIcon

        if not QSystemTrayIcon.isSystemTrayAvailable():
            # 显示错误信息
            from PySide6.QtWidgets import QMessageBox

            session_type = os.environ.get('XDG_SESSION_TYPE', 'x11')
            is_wayland = session_type == 'wayland'

            if is_wayland:
                msg = "Wayland环境系统托盘支持有限。\n请切换到X11会话或安装AppIndicator扩展。"
            else:
                msg = "X11环境系统托盘不可用。\n请检查桌面环境配置。"

            QMessageBox.critical(None, "系统托盘错误",
                            f"无法启动：{msg}\n\n应用必须依赖系统托盘运行。",
                            QMessageBox.Ok)
            sys.exit(1)

    # 防止无限重启
    if os.environ.get('APP_RESTARTED') == '1':
        logger.info("检测到这是重启实例，清除 APP_RESTARTED 标记")
        os.environ.pop('APP_RESTARTED', None)


    app_instance = None
    exit_code = 0

    try:
        app_instance = MainProxyApp()
        exit_code = app_instance.run()

    except Exception:
        error_msg = traceback.format_exc()
        logger.error(f"主程序发生未处理异常:\n{error_msg}")

        # 弹出错误窗口
        try:
            error_dialog = ErrorDialog(error_msg)
            error_dialog.exec()
        except Exception:
            pass

        exit_code = 1

    finally:
        # 重启判断
        if get_applifecycle_manager().should_restart():
            logger.info("🔁 主程序退出后检测到重启请求，启动新实例...")
            get_applifecycle_manager().perform_restart()
        else:
            logger.info("👋 应用已正常退出")

        sys.exit(exit_code)


if __name__ == "__main__":
    main()
