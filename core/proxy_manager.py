# -*- coding: utf-8 -*-
"""
Module: proxy_manager.py
Author: Takeshi
Date: 2025-12-26

Description:
    管理所有代理工作器
"""


import logging

from .proxy_worker import ProxyWorker
from .dns_resolver import DNSResolver
from managers.context import ManagerContext
from managers.signals import StatusSignals

from PySide6.QtCore import QTimer

logger = logging.getLogger(__name__)


class ProxyManager:
    """
    代理管理器，管理所有代理工作器

    参数：
        bind_interface：流量出口的网络接口
    """

    def __init__(self, bind_interface, dns_resolver: DNSResolver, context: ManagerContext, signals: StatusSignals):
        self.bind_interface = bind_interface
        self.dns_resolver = dns_resolver
        self.context = context
        self.proxy_workers = {}
        self.signals = signals

    def setup_proxies(self, socks5_proxy_config, http_proxy_config):
        """设置代理工作器"""
        try:
            from utils import generate_all_interfaces

            socks5_list, socks5_invalid_list = generate_all_interfaces(socks5_proxy_config)
            http_list, http_invalid_list = generate_all_interfaces(http_proxy_config)

            if not socks5_list and not http_list:
                error_msg = (
                    "没有找到可用的网络接口！\n\n无效配置：\n" +
                    "\n".join([f"- {config}" for config in socks5_invalid_list]) +
                    "\n".join([f"- {config}" for config in http_invalid_list])
                            )
                raise Exception(error_msg)

            logger.info(f"找到 {len(socks5_list)} 个socks5网络接口和 {len(http_list)} 个http网络接口")
            logger.info(f"绑定接口: {self.bind_interface.iface_name} {self.bind_interface.ip}")

            # 创建代理工作器S
            for i, interface in enumerate(socks5_list):
                config_id = f"socks5_{i}"

                worker = ProxyWorker(
                    config_id,
                    interface,
                    self.bind_interface,
                    self.dns_resolver,
                    self.context,
                    kind='socks5',
                )
                self.proxy_workers[config_id] = worker

                # 记录接口认证状态
                auth_status = "认证" if worker.get_auth_status() else "无认证"
                logger.debug(f"创建 SOCKS5 代理: {interface.iface_name} {interface.ip}:{interface.port} ({auth_status})")

            for i, interface in enumerate(http_list):
                config_id = f"http_{i}"

                worker = ProxyWorker(
                    config_id,
                    interface,
                    self.bind_interface,
                    self.dns_resolver,
                    self.context,
                    kind='http',
                )
                self.proxy_workers[config_id] = worker

                # 记录接口认证状态
                auth_status = "认证" if worker.get_auth_status() else "无认证"
                logger.debug(f"创建 HTTP 代理: {interface.iface_name} {interface.ip}:{interface.port} ({auth_status})")

            return True

        except Exception as e:
            logger.error(f"设置代理失败: {e}")
            raise


    def start_all_proxies(self):
        """启动所有代理"""
        logger.info("正在一键启动所有代理...")
        http_proxy = {}
        start_count = 0

        for config_id, worker in self.proxy_workers.items():
            if config_id.startswith("http"):
                http_proxy[config_id] = worker
                continue

            if worker.status in ["stopped", "error"]:
                worker.start()
                start_count += 1
                auth_status = "认证" if worker.get_auth_status() else "无认证"
                logger.info(f"启动代理: {config_id}: {worker.interface.iface_name} {worker.interface.ip}:{worker.interface.port} ({auth_status})")

        for config_id, worker in http_proxy.items():
            if worker.status in ["stopped", "error"]:
                worker.start()
                start_count += 1
                auth_status = "认证" if worker.get_auth_status() else "无认证"
                logger.info(f"启动代理: {config_id}: {worker.interface.iface_name} {worker.interface.ip}:{worker.interface.port} ({auth_status})")

        if start_count > 0:
            logger.info(f"已启动 {start_count} 个代理")
        else:
            logger.info("没有需要启动的代理")

        QTimer.singleShot(200, lambda: self.signals.proxy_status_changed.emit())
        return start_count

    def stop_all_proxies(self):
        """停止所有代理"""
        logger.info("正在一键停止所有代理...")
        stop_count = 0

        for config_id, worker in self.proxy_workers.items():
            if worker.status in ["running", "starting"]:
                worker.stop()
                stop_count += 1
                logger.info(f"停止代理: {config_id}: {worker.interface.iface_name} {worker.interface.ip}:{worker.interface.port}")

        if stop_count > 0:
            logger.info(f"已停止 {stop_count} 个代理")
        else:
            logger.info("没有正在运行的代理")

        QTimer.singleShot(200, lambda: self.signals.proxy_status_changed.emit())
        return stop_count

    def restart_all_proxies(self):
        """重启所有代理"""
        logger.info("正在一键重启所有代理...")
        http_proxy = {}
        restart_count = 0

        for config_id, worker in self.proxy_workers.items():
            if config_id.startswith("http"):
                http_proxy[config_id] = worker
                continue

            if worker.status in ["running", "error"]:
                worker.restart()
                restart_count += 1
                logger.info(f"重启代理: {config_id}")

        for config_id, worker in http_proxy.items():
            if worker.status in ["running", "error"]:
                worker.restart()
                restart_count += 1
                logger.info(f"重启代理: {config_id}")

        if restart_count > 0:
            logger.info(f"已重启 {restart_count} 个代理")
        else:
            logger.info("没有需要重启的代理")
        QTimer.singleShot(200, lambda: self.signals.proxy_status_changed.emit())
        return restart_count

    def start_proxy(self, config_id):
        """启动指定代理"""
        if config_id in self.proxy_workers:
            self.proxy_workers[config_id].start()
            worker = self.proxy_workers[config_id]
            logger.info(f"启动代理: {config_id}: {worker.interface.iface_name} {worker.interface.ip}:{worker.interface.port}")
            QTimer.singleShot(200, lambda: self.signals.proxy_status_changed.emit())
            return True
        return False

    def stop_proxy(self, config_id):
        """停止指定代理"""
        if config_id in self.proxy_workers:
            self.proxy_workers[config_id].stop()
            worker = self.proxy_workers[config_id]
            logger.info(f"停止代理: {config_id}: {worker.interface.iface_name} {worker.interface.ip}:{worker.interface.port}")
            QTimer.singleShot(200, lambda: self.signals.proxy_status_changed.emit())
            return True
        return False

    def restart_proxy(self, config_id):
        """重启指定代理"""
        if config_id in self.proxy_workers:
            self.proxy_workers[config_id].restart()
            worker = self.proxy_workers[config_id]
            logger.info(f"重启代理: {config_id}: {worker.interface.iface_name} {worker.interface.ip}:{worker.interface.port}")
            QTimer.singleShot(200, lambda: self.signals.proxy_status_changed.emit())
            return True
        return False

    def toggle_proxy_auth(self, config_id):
        """切换指定代理的认证状态"""
        if config_id in self.proxy_workers:
            worker = self.proxy_workers[config_id]
            new_status = worker.toggle_auth()
            status_text = "启用" if new_status else "禁用"

            # 重启代理以应用新的认证设置
            worker.restart()
            logger.info(f"接口 {config_id}: {worker.interface.iface_name} {worker.interface.ip}:{worker.interface.port}认证已{status_text}，正在重启...")
            return True
        return False

    def get_running_count(self):
        """获取运行中的代理数量"""
        return sum(1 for worker in self.proxy_workers.values()
                  if worker.status == "running")

    def get_auth_count(self):
        """获取启用认证的代理数量"""
        return sum(1 for worker in self.proxy_workers.values()
                  if worker.get_auth_status())

    def get_security_count(self):
        """获取启用认证的代理数量"""
        return sum(1 for worker in self.proxy_workers.values()
                  if worker.get_security_status())

    def get_total_count(self):
        """获取总代理数量"""
        return len(self.proxy_workers)

    def get_running_proxy(self):
        """获取第一个运行中的代理信息（用于健康检查）"""
        for config_id, worker in self.proxy_workers.items():
            if config_id.startswith('socks5') and worker.status == "running":
                return {
                    'ip': worker.interface.ip,
                    'port': worker.interface.port,
                    'auth_enabled': worker.get_auth_status()
                }
        return None

    def get_all_proxy_info(self):
        """获取所有代理信息"""
        return {config_id: worker.get_info()
                for config_id, worker in self.proxy_workers.items()}
