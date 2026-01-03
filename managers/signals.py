
from PySide6.QtCore import QObject, Signal

class LogSignals(QObject):
    """日志信号"""
    new_log = Signal(str)  # 为 ui.log_window 添加日志信息

class StatusSignals(QObject):
    """各类状态信号"""
    health_changed = Signal(str)    # 为 ui.tray_icon 提供变化后的健康状态
    proxy_status_changed = Signal() # 为 ui.tray_icon 提供变化后的代理变化状态
    security_changed = Signal(str)  # 为 ui.tray_icon 提供变化后的安全管理模式
