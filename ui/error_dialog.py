# -*- coding: utf-8 -*-
"""
Module: error_dialog.py
Author: Takeshi
Date: 2025-12-26

Description:
    错误对话框
"""


from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QPushButton,
                              QHBoxLayout, QLabel, QTextEdit, QApplication)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt

from defaults.ui_default import ERROR_DIALOG_SIZE, DIALOG_ICOINS

class ErrorDialog(QMainWindow):
    def __init__(self, error_message):
        super().__init__()
        self.setWindowTitle("BindInterfaceProxy - 启动错误")
        self.setFixedSize(*ERROR_DIALOG_SIZE)
        self.center_on_screen()  # 居中显示
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 错误图标和标题
        title_layout = QHBoxLayout()
        error_icon = QLabel("❌")
        error_icon.setFont(QFont("Arial", 24))
        title_layout.addWidget(error_icon)

        title_label = QLabel("程序启动失败")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title_label.setStyleSheet("color: red;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 错误信息标签
        info_label = QLabel("BindInterfaceProxy启动时遇到错误，请检查配置后重新启动：")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(info_label)

        # 错误详情文本框
        self.error_text = QTextEdit()
        self.error_text.setFont(QFont("Consolas", 9))
        self.error_text.setPlainText(error_message)
        self.error_text.setReadOnly(True)
        layout.addWidget(self.error_text)

        # 按钮栏
        button_layout = QHBoxLayout()

        copy_btn = QPushButton("复制错误信息")
        copy_btn.clicked.connect(self.copy_error)
        button_layout.addWidget(copy_btn)

        button_layout.addStretch()

        exit_btn = QPushButton("退出程序")
        exit_btn.clicked.connect(self.exit_app)
        exit_btn.setStyleSheet("background-color: #ff4444; color: white;")
        button_layout.addWidget(exit_btn)

        layout.addLayout(button_layout)

        # 状态栏
        self.statusBar().showMessage("程序启动失败")

    def center_on_screen(self):
        """居中显示窗口"""
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )

    def copy_error(self):
        """复制错误信息到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.error_text.toPlainText())
        self.statusBar().showMessage("错误信息已复制到剪贴板")

    def exit_app(self):
        """退出程序"""
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
