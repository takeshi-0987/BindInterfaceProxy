# -*- coding: utf-8 -*-
"""
Module: healthcheck_dialog.py
Author: Takeshi
Date: 2025-11-08

Description:
    健康检查对话框
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QListWidget, QListWidgetItem,
                              QFrame, QGroupBox)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon
from datetime import datetime, timedelta
import threading
import logging

from defaults.config_manager import get_config_manager
from defaults.ui_default import (HEALTHCHECK_DIALOG_SIZE,
                                 HEALTHCHECK_REFRESH_INTERVAL,
                                 DIALOG_ICOINS)

logger = logging.getLogger(__name__)


class HealthCheckDialog(QDialog):
    """健康检查对话框 - PySide6 完整版"""

    # 信号定义
    auto_check_changed = Signal(bool)      # 自动检查状态改变
    check_started = Signal()               # 检查开始
    check_completed = Signal(dict)         # 检查完成（带结果）
    check_failed = Signal(str)             # 检查失败（带错误信息）

    def __init__(self, health_checker, parent=None):
        super().__init__(parent)
        self.health_checker = health_checker
        self.setup_ui()
        self.update_display()

        # 设置定时器，每30秒更新一次显示
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(HEALTHCHECK_REFRESH_INTERVAL)

        # 连接信号
        self.auto_check_changed.connect(self.on_auto_check_changed)
        self.check_started.connect(self.on_check_started)
        self.check_completed.connect(self.on_check_completed)
        self.check_failed.connect(self.on_check_failed)

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("健康检查")
        self.setFixedSize(*HEALTHCHECK_DIALOG_SIZE)

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

        # ====== 状态信息组 ======
        status_group = QGroupBox("检查状态")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(4)

        # 第一行：自动检查状态
        auto_status_layout = QHBoxLayout()

        self.auto_status_label = QLabel("自动检查状态:")
        self.auto_status_value = QLabel()

        auto_status_layout.addWidget(self.auto_status_label)
        auto_status_layout.addWidget(self.auto_status_value)
        auto_status_layout.addStretch()

        status_layout.addLayout(auto_status_layout)

        # 第二行：最近一次检查时间
        self.last_check_label = QLabel()

        # 第三行：最近一次检查结果
        self.last_result_label = QLabel()

        # 第四行：预计下一次检查时间
        self.next_check_label = QLabel()

        status_layout.addWidget(self.last_check_label)
        status_layout.addWidget(self.last_result_label)
        status_layout.addWidget(self.next_check_label)

        main_layout.addWidget(status_group)

        # ====== 控制按钮 ======
        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setSpacing(8)

        # 自动检查开关按钮
        self.auto_check_btn = QPushButton()
        self.auto_check_btn.setFixedSize(120, 28)
        self.auto_check_btn.clicked.connect(self.toggle_auto_check)

        # 手动检查按钮
        self.manual_check_btn = QPushButton("执行手动检查")
        self.manual_check_btn.setFixedSize(120, 28)
        self.manual_check_btn.clicked.connect(self.perform_manual_check)

        control_layout.addStretch()
        control_layout.addWidget(self.auto_check_btn)
        control_layout.addWidget(self.manual_check_btn)
        control_layout.addStretch()

        main_layout.addWidget(control_frame)

        # ====== URL列表组 ======
        url_group = QGroupBox("待检查URL列表")
        url_layout = QVBoxLayout(url_group)

        # URL列表
        self.url_list = QListWidget()
        self.url_list.setAlternatingRowColors(False)  # 不使用交替颜色
        self.url_list.setSelectionMode(QListWidget.NoSelection)  # 禁用选择
        self.url_list.setMaximumHeight(180)  # 限制列表高度

        # 初始化URL列表
        self.init_url_list()

        url_layout.addWidget(self.url_list)

        main_layout.addWidget(url_group)

        # ====== 底部区域 ======
        bottom_layout = QHBoxLayout()

        # 左下角：状态提示
        self.status_hint_label = QLabel("就绪")
        self.status_hint_label.setStyleSheet("color: #666; font-style: italic;")

        # 右侧：关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.setFixedSize(80, 28)
        self.close_btn.clicked.connect(self.close)

        bottom_layout.addWidget(self.status_hint_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.close_btn)

        main_layout.addLayout(bottom_layout)

    def init_url_list(self):
        """初始化URL列表（只显示URL，不显示状态）"""
        self.url_list.clear()

        if hasattr(self.health_checker, 'config') and self.health_checker.config:
            for url in self.health_checker.config.check_services:
                item = QListWidgetItem(url)
                self.url_list.addItem(item)

    def update_url_list_with_results(self, results):
        """根据检查结果更新URL列表显示，包括响应码

        Args:
            results: 包含URL检查详细结果的字典
        """
        self.url_list.clear()

        if not results:
            return

        # 计算统计信息
        url_results = {k: v for k, v in results.items() if k != 'last_check'}
        total_count = len(url_results)
        success_count = sum(1 for detail in url_results.values() if detail.get('success'))
        fail_count = total_count - success_count
        overall_status = any(detail.get('success') for detail in url_results.values())

        # 添加统一状态行
        if overall_status:
            status_text = f"✓ 检查通过 ({success_count}/{total_count} 个URL可用)"
        else:
            status_text = f"✗ 检查失败 ({success_count}/{total_count} 个URL可用)"

        status_item = QListWidgetItem(status_text)
        if overall_status:
            status_item.setForeground(QColor(0, 128, 0))  # 深绿色
        else:
            status_item.setForeground(QColor(220, 0, 0))  # 深红色
        self.url_list.addItem(status_item)

        # 添加分隔线
        sep_item = QListWidgetItem("─" * 50)
        sep_item.setForeground(QColor(180, 180, 180))
        self.url_list.addItem(sep_item)

        # 添加每个URL的结果
        for url in self.health_checker.config.check_services:
            detail = results.get(url)

            if not detail:
                # 未检查状态
                display_text = f"  {url}"
                color = QColor(120, 120, 120)  # 灰色
            elif detail.get('success'):
                # 检查通过
                status_code = detail.get('status_code', '?')
                response_time = detail.get('response_time')
                time_text = f" [{response_time}ms]" if response_time else ""
                display_text = f"  ✓ {url} ({status_code}){time_text}"
                color = QColor(0, 128, 0)  # 深绿色
            else:
                # 检查不通过
                status_code = detail.get('status_code')
                error = detail.get('error')
                if status_code:
                    display_text = f"  ✗ {url} ({status_code})"
                elif error:
                    error_text = error[:30] + "..." if len(error) > 30 else error
                    display_text = f"  ✗ {url} ({error_text})"
                else:
                    display_text = f"  ✗ {url} (失败)"
                color = QColor(220, 0, 0)  # 深红色

            item = QListWidgetItem(display_text)
            item.setForeground(color)
            self.url_list.addItem(item)

        self.url_list.scrollToTop()

    def update_display(self):
        """更新显示信息"""
        # 检查URL列表是否为空，更新按钮状态
        self._update_button_state()

        # 更新自动检查状态显示
        self.update_auto_status()

        # 更新自动检查按钮
        self.update_auto_check_button()

        # 更新最近一次检查时间
        self.update_last_check_time()

        # 更新最近一次检查结果
        self.update_last_result()

        # 更新下一次检查时间
        self.update_next_check_time()

        # 更新状态提示
        self.update_status_hint()

        # 只有在没有手动检查的情况下，且自动检查不是正在进行时，才重置URL列表
        if (not hasattr(self, 'is_manual_checking') or not self.is_manual_checking) and \
           self.health_checker.health_status != "checking":
            self.init_url_list()

    def _update_button_state(self):
        """更新按钮状态"""
        has_urls = False
        if hasattr(self.health_checker, 'config') and self.health_checker.config:
            check_services = self.health_checker.config.check_services
            has_urls = bool(check_services)

        self.auto_check_btn.setEnabled(has_urls)
        self.manual_check_btn.setEnabled(has_urls)

    def update_status_hint(self):
        """更新状态提示"""
        # 检查URL列表是否为空
        if hasattr(self.health_checker, 'config') and self.health_checker.config:
            check_services = self.health_checker.config.check_services
            if not check_services:
                self.status_hint_label.setText("⚠️ 无测试URL，无法检查，请在设置-其它设置中添加")
                self.status_hint_label.setStyleSheet("color: #FF9800; font-style: italic;")
                return

        if hasattr(self, 'is_manual_checking') and self.is_manual_checking:
            self.status_hint_label.setText("正在检查中，请稍候...")
            self.status_hint_label.setStyleSheet("color: #FF9800; font-style: italic;")
        elif self.health_checker.health_status == "checking":
            self.status_hint_label.setText("自动检查中...")
            self.status_hint_label.setStyleSheet("color: #FF9800; font-style: italic;")
        elif self.health_checker.health_status == "healthy":
            self.status_hint_label.setText("✅ 检查正常")
            self.status_hint_label.setStyleSheet("color: #4CAF50; font-style: italic;")
        elif self.health_checker.health_status == "unhealthy":
            self.status_hint_label.setText("❌ 检查异常")
            self.status_hint_label.setStyleSheet("color: #f44336; font-style: italic;")
        else:
            self.status_hint_label.setText("就绪")
            self.status_hint_label.setStyleSheet("color: #666; font-style: italic;")

    def update_auto_status(self):
        """更新自动检查状态显示"""
        if self.health_checker.config.enabled:
            self.auto_status_value.setText("已开启")
            self.auto_status_value.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.auto_status_value.setText("已关闭")
            self.auto_status_value.setStyleSheet("color: #f44336; font-weight: bold;")

    def update_auto_check_button(self):
        """更新自动检查按钮"""
        if self.health_checker.config.enabled:
            self.auto_check_btn.setText("关闭自动检查")
            self.auto_check_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: 1px solid #d32f2f;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #e53935;
                }
            """)
        else:
            self.auto_check_btn.setText("开启自动检查")
            self.auto_check_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #388E3C;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)

    def update_last_check_time(self):
        """更新最近一次检查时间"""
        if not self.health_checker.last_check_time:
            text = "最近检查: 从未检查"
            self.last_check_label.setText(text)
            self.last_check_label.setStyleSheet("color: #888;")
            return

        check_time = self.health_checker.last_check_time
        time_str = check_time.strftime("%Y-%m-%d %H:%M:%S")

        # 计算相对时间
        now = datetime.now()
        diff = now - check_time
        total_seconds = int(diff.total_seconds())

        if total_seconds < 60:
            ago_str = f"{total_seconds}秒前"
        elif total_seconds < 3600:
            ago_str = f"{total_seconds // 60}分钟前"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            ago_str = f"{hours}小时{minutes}分钟前"
        else:
            days = total_seconds // 86400
            ago_str = f"{days}天前"

        text = f"最近检查: {time_str} ({ago_str})"
        self.last_check_label.setText(text)
        self.last_check_label.setStyleSheet("color: #333;")

    def update_last_result(self):
        """更新最近一次检查结果，显示通过的URL和响应码"""
        if not self.health_checker.last_check_time:
            text = "检查结果: 无结果"
            self.last_result_label.setText(text)
            self.last_result_label.setStyleSheet("color: #888;")
            return

        # 如果有手动检查结果，优先显示
        if self.health_checker.all_connections_details:
            all_details = self.health_checker.all_connections_details
            url_details = {k: v for k, v in all_details.items()
                          if k != 'last_check'}

            if url_details:
                success_details = [detail for detail in url_details.values() if detail.get('success')]
                success_count = len(success_details)
                total_count = len(url_details)

                if success_count > 0:
                    # 显示第一个成功的URL和状态码
                    first_success = success_details[0]
                    status_code = first_success.get('status_code', '?')
                    url = first_success.get('url', '未知')
                    if len(url) > 30:
                        url = url[:27] + "..."
                    text = f"检查结果: ✓ 通过 ({success_count}/{total_count}) - {url} ({status_code})"
                    self.last_result_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                else:
                    text = f"检查结果: ✗ 失败 ({success_count}/{total_count})"
                    self.last_result_label.setStyleSheet("color: #f44336; font-weight: bold;")
            else:
                text = self._get_health_status_text()
                self.last_result_label.setStyleSheet(self._get_health_status_style())
        else:
            text = self._get_health_status_text()
            self.last_result_label.setStyleSheet(self._get_health_status_style())

        self.last_result_label.setText(text)

    def _get_health_status_text(self):
        """获取健康状态文本，显示通过的URL和状态码"""
        if self.health_checker.health_status == "healthy":
            text = "检查结果: ✓ 通过"
            if self.health_checker.last_success_url and self.health_checker.last_success_status_code:
                url = self.health_checker.last_success_url
                if len(url) > 30:
                    url = url[:27] + "..."
                text += f" - {url} ({self.health_checker.last_success_status_code})"
            return text
        elif self.health_checker.health_status == "unhealthy":
            text = "检查结果: ✗ 失败"
            if self.health_checker.last_failure_reason:
                reason = self.health_checker.last_failure_reason
                if len(reason) > 30:
                    reason = reason[:30] + "..."
                text += f" ({reason})"
            return text
        elif self.health_checker.health_status == "checking":
            return "检查结果: ⏳ 检查中..."
        else:
            return "检查结果: ? 未知"

    def _get_health_status_style(self):
        """获取健康状态样式"""
        if self.health_checker.health_status == "healthy":
            return "color: #4CAF50; font-weight: bold;"
        elif self.health_checker.health_status == "unhealthy":
            return "color: #f44336; font-weight: bold;"
        elif self.health_checker.health_status == "checking":
            return "color: #FF9800; font-weight: bold;"
        else:
            return "color: #888;"

    def update_next_check_time(self):
        """更新预计下一次检查时间"""
        if not self.health_checker.config.enabled:
            text = "下次检查: - (自动检查未开启)"
            self.next_check_label.setText(text)
            self.next_check_label.setStyleSheet("color: #888;")
            return

        now = datetime.now()

        if self.health_checker.last_check_time:
            next_time = self.health_checker.last_check_time + timedelta(
                seconds=self.health_checker.config.check_interval
            )
        else:
            next_time = now + timedelta(
                seconds=self.health_checker.config.check_interval
            )

        if next_time > now:
            # 显示完整的年月日时分秒，保持与最近检查时间格式一致
            time_str = next_time.strftime("%Y-%m-%d %H:%M:%S")

            # 计算距离现在的时间
            diff = next_time - now
            total_seconds = int(diff.total_seconds())

            if total_seconds < 60:
                in_str = f"{total_seconds}秒后"
            elif total_seconds < 3600:
                in_str = f"{total_seconds // 60}分钟后"
            elif total_seconds < 86400:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                in_str = f"{hours}小时{minutes}分钟后"
            else:
                days = total_seconds // 86400
                in_str = f"{days}天后"

            text = f"下次检查: {time_str} ({in_str})"
        else:
            text = "下次检查: 即将检查"

        self.next_check_label.setText(text)
        self.next_check_label.setStyleSheet("color: #2196F3;")
        # else:
        #     text = "下次检查: -"
        #     self.next_check_label.setText(text)
        #     self.next_check_label.setStyleSheet("color: #888;")

    def toggle_auto_check(self):
        """切换自动检查状态"""
        # 直接取反当前状态
        new_state = not self.health_checker.config.enabled
        self.health_checker.config.enabled = new_state

        if new_state:
            self.health_checker.start()
            logger.info("开启自动健康检查")
        else:
            self.health_checker.stop()
            logger.info("关闭自动健康检查")

        # 保存配置文件
        get_config_manager().update_config('HEALTH_CHECK_CONFIG', 'enabled', new_state)
        get_config_manager().save()

        self.auto_check_changed.emit(new_state)
        self.update_display()

    def perform_manual_check(self):
        """执行手动检查"""
        # 先重置表格状态
        self.init_url_list()

        # 设置手动检查状态
        self.is_manual_checking = True

        # 发射检查开始信号
        self.check_started.emit()

        # 在线程中执行检查
        check_thread = threading.Thread(target=self._perform_check_in_thread)
        check_thread.daemon = True
        check_thread.start()

    def _perform_check_in_thread(self):
        """在线程中执行检查"""
        try:
            if hasattr(self.health_checker, 'check_all_connections_status'):
                results = self.health_checker.check_all_connections_status()

                # # 同时调用统一状态检查来更新时间戳
                # if hasattr(self.health_checker, 'check_single_health_status'):
                #     self.health_checker.check_single_health_status()

                logger.info("手动检查完成")

                # 发射检查完成信号
                self.check_completed.emit(results)
            else:
                self.check_failed.emit("✗ 不支持检查所有连接状态")

        except Exception as e:
            logger.error(f"手动检查失败: {e}")
            self.check_failed.emit(f"✗ 检查失败: {str(e)[:50]}")

    def on_check_started(self):
        """检查开始时的处理"""
        self.manual_check_btn.setEnabled(False)
        self.manual_check_btn.setText("检查中...")
        self.status_hint_label.setText("正在检查中，请稍候...")
        self.status_hint_label.setStyleSheet("color: #FF9800; font-style: italic;")

    def on_check_completed(self, results):
        """检查完成时的处理"""
        self.update_url_list_with_results(results)
        self.update_display()
        self._restore_ui_state("✅ 检查完成")

    def on_check_failed(self, error_message):
        """检查失败时的处理"""
        error_item = QListWidgetItem(error_message)
        error_item.setForeground(QColor(220, 0, 0))
        self.url_list.addItem(error_item)
        self._restore_ui_state("❌ 检查失败")

    def _restore_ui_state(self, hint_text=None):
        """恢复UI状态"""
        self.manual_check_btn.setEnabled(True)
        self.manual_check_btn.setText("执行手动检查")
        self.is_manual_checking = False

        if hint_text:
            self.status_hint_label.setText(hint_text)
            if "✅" in hint_text:
                self.status_hint_label.setStyleSheet("color: #4CAF50; font-style: italic;")
            elif "❌" in hint_text:
                self.status_hint_label.setStyleSheet("color: #f44336; font-style: italic;")
            else:
                self.status_hint_label.setStyleSheet("color: #666; font-style: italic;")
        else:
            # 根据健康状态更新提示
            self.update_status_hint()

    def on_auto_check_changed(self, enabled):
        """自动检查状态改变时的处理"""
        pass

    def closeEvent(self, event):
        """关闭事件处理"""
        if hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()
        event.accept()
