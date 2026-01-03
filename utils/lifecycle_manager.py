# -*- coding: utf-8 -*-
"""
Module: lifecycle_manager.py
Author: Takeshi
Date: 2025-12-19

Description:
    App生命周期管理
"""

import os
import sys
import signal
import subprocess
import logging

logger = logging.getLogger(__name__)

class AppLifecycleManager:
    """重启管理器"""

    def __init__(self):
        self.restart_pending = False  # 是否需要重启
        self.app = None  # 主程序类
        self.exit_scheduled = False  # 退出/重启已安排标志

    def prepare_restart(self):
        """准备重启"""
        logger.info("挂起重启标志……")
        self.restart_pending = True
        return True

    def should_restart(self) -> bool:
        """检查是否需要重启"""
        # 防止无限重启
        if os.environ.get('APP_RESTARTED') == '1':
            return False
        return self.restart_pending

    def perform_restart(self):
        """执行重启进程 - 不使用sys.executable，避免nuitka编译出错"""
        try:
            # 1. 总是使用 sys.argv[0] 作为可执行文件路径
            executable = sys.argv[0]
            logger.info(f"执行重启进程，程序路径: {executable}")

            # 2. 过滤重启参数并构建命令
            restart_flags = {'--restart', '--force-restart', '--restarted'}
            args = [arg for arg in sys.argv[1:] if arg not in restart_flags] + ['--restarted']

            # 3. 检查是否是.py文件（需要Python解释器执行）
            if executable.lower().endswith('.py'):
                # 如果是.py文件，用sys.executable（Python解释器）来执行这个脚本
                cmd = [sys.executable, executable] + args
            else:
                # 如果是.exe或其他可执行文件，直接执行
                cmd = [executable] + args

            logger.info(f"启动命令: {' '.join(cmd)}")

            # 4. 启动新进程
            env = os.environ.copy()
            env['APP_RESTARTED'] = '1'

            process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(),
                env=env
            )
            logger.info(f"新进程已启动，PID: {process.pid}")
            return True

        except Exception as e:
            logger.error(f"重启失败: {e}", exc_info=True)
            return False

    # def perform_restart(self):
    #     """执行重启进程"""
    #     try:
    #         logger.info("执行重启进程...")
    #         cmd = [sys.executable] + [arg for arg in sys.argv if arg not in ('--restart', '--force-restart')] + ['--restarted']
    #         env = os.environ.copy()
    #         env['APP_RESTARTED'] = '1'

    #         process = subprocess.Popen(
    #             cmd,
    #             cwd=os.getcwd(),
    #             env=env
    #         )
    #         logger.info(f"新进程已启动，PID: {process.pid}")
    #         return True
    #     except Exception as e:
    #         logger.error(f"重启失败: {e}", exc_info=True)
    #         return False

    def register_app(self, app):
        """注册主程序对象"""
        self.app = app

    def restart(self):
        """执行重启"""
        # 如果已经有退出安排了，就不重复执行
        if self.exit_scheduled:
            logger.warning("退出/重启操作已安排，忽略重复请求")
            return

        logger.info("准备重启应用程序...")
        self.exit_scheduled = True

        # 设置重启标志
        self.prepare_restart()

        # 300ms后退出应用
        if self.app:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, self.app.quit_app)
        else:
            logger.error("未注册主程序对象，无法重启")
            self.exit_scheduled = False

    def quit_app(self):
        """执行退出"""
        # 如果已经有退出安排了，就不重复执行
        if self.exit_scheduled:
            logger.warning("退出/重启操作已安排，忽略重复请求")
            return

        logger.info("准备退出应用程序...")
        self.exit_scheduled = True

        # 300ms后退出应用
        if self.app:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, self.app.quit_app)
        else:
            logger.error("未注册主程序对象，无法退出")
            self.exit_scheduled = False

    # 设置中断信号处理
    def setup_signal_handlers(self):
        """
        根据平台设置信号处理器

        Windows: SIGTERM + Ctrl+Break (SIGBREAK)
        Linux/Mac: SIGINT (Ctrl+C) + SIGTERM
        """
        if not self._is_running_interactively():
            logger.info("未启用交互终端/控制台，不注册中断信号")
            return

        logger.info("已启用交互终端/控制台，开始注册中断信号……")

        def signal_handler(signum, frame):
            """统一的信号处理函数"""
            # 获取信号名称
            sig_names = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM（标准终止）",
            }

            sig_name = sig_names.get(signum, f"Signal {signum}")
            logger.info(f"收到信号: {sig_name}，准备退出...")
            self.quit_app()

        try:

            signal.signal(signal.SIGINT, signal_handler)
            logger.info("注册 Ctrl+C 信号，触发程序标准退出")

            signal.signal(signal.SIGTERM, signal_handler)
            logger.info("注册标准终止信号，触发程序标准退出")

        except Exception as e:
            logger.error(f"信号处理器设置失败: {e}")

        # 启动一个“心跳”定时器，让 Python 有机会运行，避免卡在qt的循环中，解决随缘触发问题
        from PySide6.QtCore import QTimer
        # 即使回调是空的，也能触发 Python 解释器检查信号
        self.heartbeat = QTimer()
        self.heartbeat.timeout.connect(lambda: None)
        self.heartbeat.start(1000)  # 每 1s 一次
        logger.info(f"启用心跳计时器，定期检查中断信号")


    def _is_running_interactively(self) -> bool:
        """
        判断程序是否在“交互式终端”中运行。

        条件：
        - stdin 是 TTY（用户可以输入）
        - stdout 是 TTY（输出可见）

        这样可以排除：
        - 输出被重定向（app.py > log.txt）
        - 后台运行（nohup, &）
        - 被其他程序调用
        """
        try:
            stdin_tty = sys.stdin.isatty()
            stdout_tty = sys.stdout.isatty()
            return stdin_tty and stdout_tty
        except Exception:
            # 某些极端环境（如嵌入式）可能没有 stdin/stdout
            return False


# 单例模式
_applifecycle_manager = None

def get_applifecycle_manager() -> AppLifecycleManager:
    """获取生命周期管理器单例"""
    global _applifecycle_manager
    if _applifecycle_manager is None:
        _applifecycle_manager = AppLifecycleManager()
    return _applifecycle_manager
