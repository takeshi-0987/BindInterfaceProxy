# -*- coding: utf-8 -*-
"""
Module: startup_window.py
Author: Takeshi
Date: 2025-12-20

Description:
    启动进度窗口
"""

import os
import logging
import random
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFrame, QApplication, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QLinearGradient, QPainterPath

from defaults.ui_default import STARTUP_BG_LIST, STARTUP_BG_FORMAT
from defaults.app_info import AppInfo

logger = logging.getLogger(__name__)


class StartupWindow(QWidget):
    """启动进度窗口"""

    closed = Signal()

    def __init__(self, app_name="BindInterfaceProxy", author="Version 1.0.0 | By Takeshi"):
        super().__init__()

        app_info = AppInfo.get_about_info()
        self.app_name = app_info['name']
        self.version = app_info['version']
        self.author = app_info['author']

        self.display = f"Version {self.version} | By {self.author}"

        # 窗口设置
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(900, 500)

        # 创建UI
        self._create_ui()

        # 居中显示
        self._center_on_screen()

    def _create_ui(self):
        """创建UI"""
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 背景图层 ===
        self.bg_widget = QWidget(self)
        self.bg_widget.setObjectName("bgWidget")
        self.bg_widget.setGeometry(0, 0, self.width(), self.height())

        # === 右侧蒙版图层 ===
        self.overlay_widget = QWidget(self)
        self.overlay_widget.setObjectName("overlayWidget")
        # 蒙版从60%位置开始，覆盖右侧40%
        self.overlay_widget.setGeometry(
            int(self.width() * 0.6),
            0,
            int(self.width() * 0.4),
            self.height()
        )

        # 蒙版布局
        overlay_layout = QVBoxLayout(self.overlay_widget)
        overlay_layout.setContentsMargins(30, 30, 30, 50)
        overlay_layout.setSpacing(20)

        # 应用标题
        title_label = QLabel(self.app_name)
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignCenter)

        # 作者信息
        author_label = QLabel(self.display)
        author_label.setObjectName("authorLabel")
        author_label.setAlignment(Qt.AlignCenter)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("separator")
        separator.setFixedHeight(1)

        # 状态标签
        self.status_label = QLabel("正在启动...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)

        # 进度条和百分比容器
        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setValue(0)

        # 进度百分比
        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("progressLabel")
        self.progress_label.setMinimumWidth(35)

        progress_layout.addWidget(self.progress_bar, 8)
        progress_layout.addWidget(self.progress_label, 2)

        # 弹性空间
        overlay_layout.addSpacerItem(QSpacerItem(20, 50, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 添加到蒙版布局
        overlay_layout.addWidget(title_label)
        overlay_layout.addWidget(author_label)
        overlay_layout.addWidget(separator)

        # 用空widget控制间距
        spacer_widget = QWidget()
        spacer_widget.setFixedHeight(20)
        overlay_layout.addWidget(spacer_widget)

        overlay_layout.addWidget(self.status_label)
        overlay_layout.addWidget(progress_container)

        # # 底部弹性空间
        # overlay_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 设置样式
        self._set_style_sheet()

        # 加载随机图片
        QTimer.singleShot(10, self._load_random_background_image)

    def _load_random_background_image(self):
        """加载随机背景图片"""
        try:
            # 定义图片搜索路径
            image_search_paths = STARTUP_BG_LIST

            # 支持的图片格式
            image_extensions = STARTUP_BG_FORMAT

            # 收集所有找到的图片
            all_images = []

            for base_path in image_search_paths:
                if os.path.exists(base_path):
                    # 如果是文件夹，遍历里面的文件
                    if os.path.isdir(base_path):
                        for file in os.listdir(base_path):
                            file_path = os.path.join(base_path, file)
                            if os.path.isfile(file_path):
                                ext = os.path.splitext(file)[1].lower()
                                if ext in image_extensions:
                                    all_images.append(file_path)
                                    logger.debug(f"找到图片: {file_path}")
                    else:
                        # 如果是文件，直接添加
                        ext = os.path.splitext(base_path)[1].lower()
                        if ext in image_extensions and os.path.isfile(base_path):
                            all_images.append(base_path)

            # 去重
            all_images = list(set(all_images))

            logger.info(f"找到 {len(all_images)} 张背景图片")

            if all_images:
                # 随机选择一张图片
                selected_image = random.choice(all_images)
                logger.info(f"随机选择图片: {selected_image}")

                # 加载图片
                pixmap = QPixmap(selected_image)
                if not pixmap.isNull():
                    # 保存原始图片
                    self.original_pixmap = pixmap
                    self.update()  # 触发重绘
                else:
                    logger.warning(f"图片加载失败: {selected_image}")
                    self._create_gradient_background()
            else:
                logger.info("未找到图片，使用渐变背景")
                self._create_gradient_background()

        except Exception as e:
            logger.error(f"加载随机背景图片失败: {e}")
            self._create_gradient_background()

    def _create_gradient_background(self):
        """创建渐变背景"""
        # 创建渐变颜色列表
        gradients = [
            (QColor(52, 152, 219), QColor(41, 128, 185)),  # 蓝色系
            (QColor(46, 204, 113), QColor(39, 174, 96)),   # 绿色系
            (QColor(155, 89, 182), QColor(142, 68, 173)),  # 紫色系
            (QColor(241, 196, 15), QColor(243, 156, 18)),  # 黄色系
            (QColor(230, 126, 34), QColor(211, 84, 0)),    # 橙色系
        ]

        # 随机选择一个渐变
        start_color, end_color = random.choice(gradients)

        # 创建一个全屏的pixmap
        self.original_pixmap = QPixmap(self.width(), self.height())
        self.original_pixmap.fill(Qt.transparent)

        painter = QPainter(self.original_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 创建渐变
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, start_color)
        gradient.setColorAt(1, end_color)

        painter.fillRect(0, 0, self.width(), self.height(), gradient)

        # === 修改这里：使用 FontManager 获取字体 ===
        painter.setPen(QColor(255, 255, 255, 200))

        # 导入并使用 FontManager
        from utils.font_manager import FontManager
        font_manager = FontManager.get_instance()

        if font_manager.is_font_loaded():
            font = font_manager.get_font(32, QFont.Bold)
            logger.debug("开始窗口使用自定义字体")
        else:
            # 回退到系统默认字体
            font = QFont()
            font.setPointSize(32)
            font.setBold(True)
            font.setWeight(QFont.Bold)
            logger.debug("开始窗口使用系统字体")

        painter.setFont(font)

        # 只在左侧60%区域内绘制文字
        left_rect = self.original_pixmap.rect()
        left_rect.setWidth(int(self.width() * 0.6))
        painter.drawText(left_rect, Qt.AlignCenter | Qt.AlignTop, self.app_name)

        # 修改小字体的部分
        if font_manager.is_font_loaded():
            font = font_manager.get_font(18, QFont.Normal)
        else:
            font = QFont()
            font.setPointSize(18)

        painter.setFont(font)
        painter.drawText(left_rect.adjusted(0, 80, 0, 0), Qt.AlignCenter, "网络代理工具")

        painter.end()
        self.update()  # 触发重绘

    def _set_style_sheet(self):
        """设置样式表"""
        style_sheet = """
            #overlayWidget {
                /* 右侧白色蒙版样式 */
                background-color: rgba(255, 255, 255, 0.92);  /* 92% 不透明的白色 */
                border-top-right-radius: 15px;                /* 右上角圆角 */
                border-bottom-right-radius: 15px;             /* 右下角圆角 */
                border-left: 1px solid rgba(255, 255, 255, 0.3);  /* 左侧分隔线 */
            }

            #titleLabel {
                /* 应用标题样式 */
                color: #2c3e50;        /* 深灰色文字 */
                font-size: 28px;       /* 字体大小 */
                font-weight: bold;     /* 粗体 */
                padding: 5px 0;        /* 上下内边距 */
            }

            #authorLabel {
                /* 作者信息样式 */
                color: #3498db;        /* 蓝色文字 */
                font-size: 15px;       /* 字体大小 */
                font-weight: bold;      /* 粗体（注意：这里应该是 font-weight，不是 font-style） */
                padding-bottom: 5px;   /* 底部内边距 */
            }

            #separator {
                /* 分隔线样式 */
                background-color: #3498db;  /* 蓝色分隔线 */
                opacity: 0.5;               /* 50% 透明度 */
                margin: 10px 0;             /* 上下外边距 */
            }

            #statusLabel {
                /* 状态标签样式 */
                color: #2c3e50;                     /* 深灰色文字 */
                font-size: 14px;                    /* 字体大小 */
                font-weight: bold;                  /* 粗体 */
                padding: 10px 12px;                 /* 内边距 */
                background-color: rgba(52, 152, 219, 0.1);  /* 浅蓝色背景 */
                border-radius: 6px;                 /* 圆角 */
                border-left: 3px solid #3498db;     /* 左侧边框 */

                /* 居中设置 - 必须先定义 */
                text-align: center;                 /* 水平居中 */
                margin: 0 auto;                     /* 水平居中（关键：用这个替代 margin-left/right）*/

                margin-top: 20px;                   /* 上外边距 */
                margin-bottom: 20px;                /* 下外边距 */
                min-height: 30px;                   /* 最小高度 */
                max-width: 280px;                   /* 最大宽度 */
            }

            #progressBar {
                /* 进度条样式 */
                border: 1px solid #d5dbdb;          /* 边框 */
                background-color: #f8f9f9;          /* 背景色 */
                border-radius: 2px;                 /* 圆角 */
                margin: 10px 0;                     /* 上下外边距 */
            }

            #progressBar::chunk {
                /* 进度条填充部分样式 */
                background-color: #2ecc71;          /* 绿色填充 */
                border-radius: 2px;                 /* 圆角 */
            }

            #progressLabel {
                /* 进度百分比样式 */
                color: #2ecc71;                     /* 绿色文字 */
                font-size: 16px;                    /* 字体大小 */
                font-weight: bold;                  /* 粗体 */
                padding: 0 5px;                     /* 左右内边距 */
                min-width: 40px;                    /* 最小宽度 */
            }
        """
        self.setStyleSheet(style_sheet)


    def paintEvent(self, event):
        """绘制窗口"""
        # 先绘制父类
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制阴影
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(5, 5, self.width()-10, self.height()-10, 15, 15)

        # 创建圆角路径
        rounded_path = QPainterPath()
        rounded_path.addRoundedRect(0, 0, self.width(), self.height(), 15, 15)
        painter.setClipPath(rounded_path)

        # 如果有背景图片，绘制全屏图片
        if hasattr(self, 'original_pixmap') and not self.original_pixmap.isNull():
            # 缩放图片以适应窗口
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(),
                self.height(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled_pixmap)

        # 恢复剪裁
        painter.setClipping(False)

    def update_progress(self, message: str, progress: int = None):
        """更新进度"""
        self.status_label.setText(message)

        if progress is not None:
            self.progress_bar.setValue(progress)
            self.progress_label.setText(f"{progress}%")

        QApplication.processEvents()

    def _center_on_screen(self):
        """居中显示"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def fade_out(self):
        """关闭窗口"""
        logger.debug("关闭启动窗口")
        self.closed.emit()
        self.close()

    def mousePressEvent(self, event):
        """支持拖动"""
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """拖动窗口"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def showEvent(self, event):
        """显示事件"""
        super().showEvent(event)
        QApplication.processEvents()
