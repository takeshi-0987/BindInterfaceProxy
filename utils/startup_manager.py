# -*- coding: utf-8 -*-
"""
Module: startup_manager.py
Author: Takeshi
Date: 2025-12-20

Description:
    启动进度管理器
"""

import logging
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from ui.startup_window import StartupWindow

logger = logging.getLogger(__name__)


class StartupManager(QObject):
    """启动进度管理器"""

    finished = Signal()

    def __init__(self):
        super().__init__()
        self.window = None

    def show(self):
        """显示启动窗口"""
        try:
            if self.window is not None:
                return

            self.window = StartupWindow()
            self.window.closed.connect(self._on_window_closed)

            # 显示窗口
            self.window.show()
            QApplication.processEvents()

            logger.debug("启动窗口已显示")

        except Exception as e:
            logger.error(f"显示启动窗口失败: {e}")
            self.finished.emit()

    def _on_window_closed(self):
        """窗口关闭回调"""
        logger.debug("启动窗口已关闭")
        self.window = None
        self.finished.emit()

    def update(self, message: str, progress: int = None):
        """更新进度"""
        try:
            if self.window and self.window.isVisible():
                self.window.update_progress(message, progress)
        except Exception as e:
            logger.error(f"更新进度失败: {e}")

    def close(self):
        """关闭启动窗口"""
        logger.debug("关闭启动窗口")

        if self.window and self.window.isVisible():
            try:
                self.window.fade_out()
            except Exception as e:
                logger.error(f"关闭窗口时出错: {e}")
                self._on_window_closed()
        else:
            self.finished.emit()
