# -*- coding: utf-8 -*-
"""
Module: proxy_worker.py
Author: Takeshi
Date: 2025-11-27

Description:
    管理单个代理实例
"""


import logging
import threading

from datetime import datetime
from typing import Literal

from core.dns_resolver import DNSResolver
from managers import ManagerContext

logger = logging.getLogger(__name__)


class ProxyWorker:
    """代理工作器类，管理单个代理实例"""

    def __init__(self, config_id, proxy_interface, bind_interface,
                 dns_resolver: DNSResolver,
                 context: ManagerContext,
                 kind: Literal['socks5', 'http'] = 'socks5'):
        self.config_id = config_id
        self.interface = proxy_interface
        self.proxy_name = getattr(proxy_interface, 'proxy_name', f"Proxy-{config_id}")
        self.bind_interface = bind_interface
        self.dns_resolver = dns_resolver
        self.context = context
        self.kind = kind

        # 从接口配置获取认证状态
        self.auth_enabled = getattr(proxy_interface, 'auth_enabled', True)
        self.security_enabled = getattr(proxy_interface, 'security_enabled', False)

        # 运行状态
        self.thread = None
        self.status = "stopped"
        self.proxy_server = None

        self._base_socks5_server = None

        self.start_time = None

    def get_auth_status(self):
        """获取认证状态"""
        return self.auth_enabled

    def toggle_auth(self):
        """切换接口认证状态"""
        self.auth_enabled = not self.auth_enabled
        # 更新接口对象的属性
        self.interface.auth_enabled = self.auth_enabled
        return self.auth_enabled

    def get_security_status(self):
        """获取安全管理状态"""
        return self.security_enabled

    def toggle_security(self):
        """切换安全管理状态"""
        self.security_enabled = not self.security_enabled
        # 更新接口对象的属性
        self.interface.security_enabled = self.security_enabled
        return self.security_enabled

    def start(self):
        """启动代理"""
        if self.thread and self.thread.is_alive():
            return

        self.status = "starting"
        self.start_time = datetime.now()

        self.thread = threading.Thread(
            target=self._run_proxy,
            daemon=True
        )
        self.thread.start()

    def stop(self):
        """停止代理"""
        try:
            if self.proxy_server and self.kind == 'socks5':
                self.proxy_server.stop()
            elif self.proxy_server and self.kind == 'http':
                self.proxy_server.stop()

        except Exception as e:
            logger.error(f"停止代理 {self.config_id}: {self.interface.proxy_name}时出错: {e}")

        self.status = "stopped"
        logger.debug(f"代理 {self.config_id}: {self.interface.proxy_name} 已停止")

    def restart(self):
        """重启代理"""
        self.stop()
        # 延迟1秒后启动
        threading.Timer(1.0, self.start).start()

    def _run_proxy(self):
        """运行代理的实际方法"""
        from servers.socks5_proxy_server import SOCKS5ProxyServer
        from servers.http_proxy_server import HTTPProxyServer
        try:
            logger.debug(f"[{self.config_id}: {self.interface.proxy_name}] 启动代理服务器...")

            if self.kind == 'socks5':

                # 导入 SOCKS5 代理服务器
                from utils import get_sock5_config
                sock5_kwargs = get_sock5_config(self.interface)

                self.proxy_server = SOCKS5ProxyServer(
                    name = self.proxy_name,
                    listen_host = self.interface.ip,
                    listen_port = self.interface.port,
                    egress_ip = self.bind_interface.ip,
                    egress_port = self.bind_interface.port,

                    dns_resolver = self.dns_resolver,

                    user_manager = self.context.user_manager,
                    security_manager = self.context.security_manager,
                    ip_geo_manager=self.context.ip_geo_manager,
                    stats_manager=self.context.stats_manager,

                    **sock5_kwargs
                )

            elif self.kind == 'http':

                from utils import get_http_config
                http_kwargs = get_http_config(self.interface)

                self.proxy_server = HTTPProxyServer(
                    name = self.proxy_name,
                    listen_host = self.interface.ip,
                    listen_port = self.interface.port,
                    egress_ip = self.bind_interface.ip,
                    egress_port = self.bind_interface.port,

                    dns_resolver = self.dns_resolver,

                    user_manager = self.context.user_manager,
                    security_manager = self.context.security_manager,
                    ip_geo_manager=self.context.ip_geo_manager,
                    stats_manager=self.context.stats_manager,
                    **http_kwargs
                )

            # 记录启动信息
            auth_status = "启用认证" if self.auth_enabled else "无认证"
            logger.debug(f"已启动 [{self.config_id}: {self.interface.proxy_name}] 监听 {self.interface.ip}:{self.interface.port} ({auth_status})")

            self.status = "running"

            """启动并等待代理服务器"""
            if self.proxy_server and self.kind == 'socks5':
                self.proxy_server.start()  # 阻塞
            elif self.proxy_server and self.kind == 'http':
                if not self.proxy_server.start():
                    raise Exception("HTTP代理启动失败")
                if hasattr(self.proxy_server, 'thread'):
                    self.proxy_server.thread.join()  # 用于http服务器等待线程结束
        except TimeoutError as e:
            logger.error(f"基服务器启动超时: {e}")
            try:
                if self._base_socks5_server:
                    self._base_socks5_server.stop()
                raise
            except:
                pass
        except Exception as e:
            logger.error(f"[{self.config_id}: {self.interface.proxy_name}] 代理异常: {e}")
            self.status = "error"

        finally:
            if self.status == "running":
                self.status = "stopped"
                logger.debug(f"[{self.config_id}: {self.interface.proxy_name}] 代理服务器已停止")

    def get_uptime(self):
        """获取运行时间"""
        if not self.start_time or self.status not in ["running", "starting"]:
            return None

        uptime = datetime.now() - self.start_time
        total_seconds = int(uptime.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}秒"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}分钟"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}小时{minutes}分钟"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{days}天{hours}小时{minutes}分钟"

    def get_info(self):
        """获取代理信息"""
        return {
            'config_id': self.config_id,
            'interface_name': getattr(self.interface, 'proxy_name', 'Unknown'),
            'address': f"{self.interface.ip}:{self.interface.port}",
            'status': self.status,
            'auth_enabled': self.auth_enabled,
            'uptime': self.get_uptime(),
        }
