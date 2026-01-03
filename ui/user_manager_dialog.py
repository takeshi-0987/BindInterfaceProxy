# -*- coding: utf-8 -*-
"""
Module: user_manager.py
Author: Takeshi
Date: 2025-11-08

Description:
    用户管理对话框
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QListWidget, QMessageBox,
                              QListWidgetItem, QFormLayout, QApplication)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from defaults.ui_default import USER_MANAGER_WINDOW_SIZE, DIALOG_ICOINS

class UserManagerDialog(QDialog):
    def __init__(self, user_manager, parent=None, require_first_user=False):
        super().__init__(parent)
        self.user_manager=user_manager
        self.require_first_user = require_first_user
        self.setWindowTitle("BindInterfaceProxy - 用户管理")
        self.setFixedSize(*USER_MANAGER_WINDOW_SIZE)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        icon = QIcon()
        for i in DIALOG_ICOINS:
            icon.addFile(i)
        self.setWindowIcon(icon)

        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.center_on_screen()
        self.setup_ui()
        self.load_users()

    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)

        # 首次配置的提示信息
        if self.require_first_user and self.user_manager.get_user_count() == 0:
            warning_label = QLabel("⚠️ 由于开启了用户认证模式，请先添加用户")
            warning_label.setStyleSheet("color: orange; font-weight: bold;")
            layout.addWidget(warning_label)

        # 用户列表
        layout.addWidget(QLabel("用户列表:"))
        self.user_list = QListWidget()
        layout.addWidget(self.user_list)

        # 操作按钮布局
        btn_layout = QHBoxLayout()

        # 添加用户按钮
        add_user_btn = QPushButton("➕ 添加用户")
        add_user_btn.clicked.connect(self.show_add_user_dialog)
        btn_layout.addWidget(add_user_btn)

        # 修改密码按钮
        self.change_password_btn = QPushButton("修改密码")
        self.change_password_btn.clicked.connect(self.change_password)
        btn_layout.addWidget(self.change_password_btn)

        # 删除用户按钮
        self.delete_user_btn = QPushButton("删除用户")
        self.delete_user_btn.clicked.connect(self.delete_user)
        btn_layout.addWidget(self.delete_user_btn)

        layout.addLayout(btn_layout)

        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

    def center_on_screen(self):
        """居中显示对话框"""
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )

    def show_add_user_dialog(self):
        """显示添加用户对话框"""
        dialog = AddUserDialog(self.user_manager, self)
        if dialog.exec():
            self.load_users()

    def load_users(self):
        """加载用户列表"""
        self.user_list.clear()
        users = self.user_manager.list_users()
        for username in users:
            item = QListWidgetItem(f"👤 {username}")
            item.setData(Qt.UserRole, username)
            self.user_list.addItem(item)

        # 更新按钮状态
        has_users = len(users) > 0
        self.change_password_btn.setEnabled(has_users)
        self.delete_user_btn.setEnabled(has_users)

    def change_password(self):
        """修改密码"""
        current_item = self.user_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "选择错误", "请先选择一个用户")
            return

        username = current_item.data(Qt.UserRole)
        dialog = ChangePasswordDialog(username, self.user_manager, self)
        if dialog.exec():
            QMessageBox.information(self, "成功", "密码修改成功")

    def delete_user(self):
        """删除用户"""
        current_item = self.user_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "选择错误", "请先选择一个用户")
            return

        username = current_item.data(Qt.UserRole)

        # 检查是否只剩一个用户
        from defaults.config_manager import get_config_manager
        if get_config_manager().has_auth_config() and self.user_manager.get_user_count() <= 1:
            QMessageBox.warning(self, "错误", "由于开启了代理认证，不能删除最后一个用户")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除用户 {username} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, message = self.user_manager.delete_user(username)
            if success:
                QMessageBox.information(self, "成功", message)
                self.load_users()
            else:
                QMessageBox.warning(self, "错误", message)

    def reject(self):
        """重写 reject 方法（点击取消或ESC时调用）"""
        super().reject()

    def accept(self):
        """重写 accept 方法"""
        super().accept()

    def closeEvent(self, event):
        """关闭事件处理"""
        super().closeEvent(event)


class AddUserDialog(QDialog):
    """添加用户对话框"""
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.setWindowTitle("添加用户")
        self.setModal(True)
        self.setFixedSize(350, 200)
        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)

        # 表单布局
        form_layout = QFormLayout()

        # 用户名输入
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        form_layout.addRow("用户名:", self.username_input)

        # 密码输入
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("密码:", self.password_input)

        # 确认密码
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("请再次输入密码")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("确认密码:", self.confirm_password_input)

        layout.addLayout(form_layout)

        # 按钮布局
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.add_user)
        btn_layout.addWidget(self.add_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # 回车键确认
        self.password_input.returnPressed.connect(self.add_user)
        self.confirm_password_input.returnPressed.connect(self.add_user)

    def add_user(self):
        """添加用户"""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not username:
            QMessageBox.warning(self, "输入错误", "请输入用户名")
            return

        if not password:
            QMessageBox.warning(self, "输入错误", "请输入密码")
            return

        if password != confirm_password:
            QMessageBox.warning(self, "输入错误", "两次输入的密码不一致")
            return

        success, message = self.user_manager.add_user(username, password)
        if success:
            QMessageBox.information(self, "成功", message)
            self.accept()  # 关闭对话框并返回成功
        else:
            QMessageBox.warning(self, "错误", message)


class ChangePasswordDialog(QDialog):
    """修改密码对话框"""
    def __init__(self, username, user_manager, parent=None):
        super().__init__(parent)
        self.username = username
        self.user_manager = user_manager
        self.setWindowTitle(f"修改密码 - {username}")
        self.setModal(True)
        self.setFixedSize(350, 200)
        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)

        # 表单布局
        form_layout = QFormLayout()

        # 旧密码
        self.old_password_input = QLineEdit()
        self.old_password_input.setPlaceholderText("请输入当前密码")
        self.old_password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("当前密码:", self.old_password_input)

        # 新密码
        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("请输入新密码")
        self.new_password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("新密码:", self.new_password_input)

        # 确认新密码
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("请再次输入新密码")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("确认新密码:", self.confirm_password_input)

        layout.addLayout(form_layout)

        # 按钮布局
        btn_layout = QHBoxLayout()

        self.confirm_btn = QPushButton("确认修改")
        self.confirm_btn.clicked.connect(self.on_confirm)
        btn_layout.addWidget(self.confirm_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # 回车键确认
        self.new_password_input.returnPressed.connect(self.on_confirm)
        self.confirm_password_input.returnPressed.connect(self.on_confirm)

    def on_confirm(self):
        """确认修改密码"""
        old_password = self.old_password_input.text()
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        # 验证输入
        if not old_password:
            QMessageBox.warning(self, "输入错误", "请输入当前密码")
            return

        if not new_password:
            QMessageBox.warning(self, "输入错误", "请输入新密码")
            return

        if new_password != confirm_password:
            QMessageBox.warning(self, "输入错误", "两次输入的新密码不一致")
            return

        # 验证旧密码
        from utils.crypto_utils import verify_user_credentials
        if not verify_user_credentials(self.username, old_password):
            QMessageBox.warning(self, "验证失败", "当前密码错误")
            return

        # 更新密码
        success, message = self.user_manager.update_user(self.username, new_password)
        if success:
            self.accept()  # 关闭对话框并返回成功
        else:
            QMessageBox.warning(self, "错误", message)
