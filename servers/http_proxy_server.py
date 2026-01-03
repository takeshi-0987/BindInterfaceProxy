# -*- coding: utf-8 -*-
"""
Module: http_proxy_server.py
Author: Takeshi
Date: 2025-11-08

Description:
    HTTP代理服务器
"""

import base64
import http.server
import http.client
import logging
import os
import select
import socket
import socketserver
import ssl
import threading
import time
from typing import Optional, Literal, Dict
from urllib.parse import urlparse

from utils import ProxyProtocolReceiver
from core import  DNSResolver

from managers import IPGeoManager, SecurityManager, StatsManager, UserManager


logger = logging.getLogger(__name__)

class HTTPProxyServer:
    """
    一个支持HTTP/HTTPS协议的代理服务器，直接连接到目标网站（绑定指定网卡）。
    """

    def __init__(self,
                 name: str,

                 listen_host: str,
                 listen_port: int,

                 egress_ip: str,
                 egress_port: int = 0,  # 0表示由系统分配

                 use_https: bool = False,
                 cert_file: Optional[str] = None,
                 key_file: Optional[str] = None,

                 dns_resolver: Optional[DNSResolver] = None,

                 auth_enabled: bool = False,
                 user_manager: Optional[UserManager] = None,

                 proxy_protocol: Optional[Literal['v1', 'v2']] = None,
                 ip_geo_manager: Optional[IPGeoManager] = None,

                 security_enabled: bool = False,
                 security_manager: Optional[SecurityManager] = None,



                 stats_enabled: bool = True,
                 stats_manager: Optional[StatsManager] = None,

                 ):
        # 代理名称
        self.name = name

        # 监听地址
        self.listen_host = listen_host
        self.listen_port = listen_port

        # 出口地址
        self.egress_ip = egress_ip
        self.egress_port = egress_port

        # https代理功能
        self.use_https = use_https
        self.cert_file = cert_file
        self.key_file = key_file

        # 是否开启用户认证
        self.auth_enabled = auth_enabled
        self.user_manager = user_manager

        # 是否开启开安管理
        self.security_enabled = security_enabled
        self.security_manager = security_manager

        # 是否启用自定义dns解析器
        self.dns_resolver = dns_resolver

        # 客户端ip和地理信息
        self.proxy_protocol = proxy_protocol
        self.ip_geo_manager = ip_geo_manager
        self._real_ips: Dict[socket.socket, str] = {}

        # 是否开启连接和流量统计
        self.stats_enabled = stats_enabled
        self.stats_manager = stats_manager

        # 运行参数
        self.mode = "https" if self.use_https else "http"
        self.server = None
        self.thread = None
        self.running = False
        self._stop_event = threading.Event()

        # UDP唤醒socket，用于中断连接等待循环
        self._wakeup_socket = None
        self._force_stop = False
        self._udp_port = None
        self._udp_listening = False
        self._udp_thread = None


    def start(self) -> bool:
        """启动HTTP/HTTPS代理服务器"""
        try:
            if self.running:
                logger.warning(f"{self.name}: {self.mode}代理服务器已经在运行")
                return True

            # HTTPS模式需要证书检查并创建SSL上下文
            ssl_context = None
            if self.use_https:
                if not self.cert_file or not self.key_file:
                    logger.error(f"{self.name}: 启动HTTPS模式，需要提供cert_file和key_file参数")
                    return False
                if not os.path.exists(self.cert_file):
                    logger.error(f"{self.name}: 证书文件不存在: {self.cert_file}")
                    return False
                if not os.path.exists(self.key_file):
                    logger.error(f"{self.name}: 私钥文件不存在: {self.key_file}")
                    return False
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(certfile=self.cert_file, keyfile=self.key_file)
                logger.debug(f"{self.name}: SSL上下文创建成功")

            # 创建自定义的HTTP代理handler
            handler_class = lambda *args: HTTPProxyHandler(
                *args,
                name=self.name,
                egress_ip=self.egress_ip,
                egress_port=self.egress_port,
                dns_resolver=self.dns_resolver,
                stats_enabled=self.stats_enabled,
                stats_manager=self.stats_manager,
                auth_enabled=self.auth_enabled,
                user_manager=self.user_manager,
                security_enabled=self.security_enabled,
                security_manager=self.security_manager,
                ip_geo_manager=self.ip_geo_manager,
                mode=self.mode,
            )

            # 选择服务器类
            if self.proxy_protocol:
                server_class = lambda *args: ProxyProtocolHTTPServer(
                    *args,
                    proxy_protocol=self.proxy_protocol,
                    real_ips_dict=self._real_ips,
                    use_https=self.use_https,
                    ssl_context=ssl_context,
                    name=self.name,
                )
                logger.info(f"{self.name}: 启用 Proxy Protocol 功能，版本为: {self.proxy_protocol}")
            else:
                server_class = lambda *args: StandardHTTPServer(
                    *args,
                    use_https=self.use_https,
                    ssl_context=ssl_context,
                    name=self.name,
                )

            # 创建服务器
            self.server = server_class((self.listen_host, self.listen_port), handler_class)
            self.server.allow_reuse_address = True
            self.server.timeout = 0.5
            self.server.daemon_threads = True

            # 对于标准服务器且启用HTTPS的情况，立即包装socket
            if self.use_https and not self.proxy_protocol and ssl_context:
                self.server.socket = ssl_context.wrap_socket(
                    self.server.socket,
                    server_side=True
                )
                logger.debug(f"{self.name}: 标准服务器SSL包装完成")

            self._stop_event.clear()
            self.running = True

            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()

            status = "有认证" if self.auth_enabled else "无认证"
            status += "有安全管理 " if self.security_enabled else "无安全管理 "
            status += "有连接统计 " if self.stats_enabled else "无连接统计 "
            status += f"有proxy_protocol: {self.proxy_protocol}" if self.proxy_protocol else "无proxy_protocol"
            logger.info(f"{self.name}: {self.mode}代理服务器启动: 监听地址： {self.listen_host}:{self.listen_port}, 网络出口： {self.egress_ip}:{self.egress_port}，功能状态：{status}")

            if self.use_https:
                logger.info(f"{self.name}: {self.mode}代理服务器证书文件: {self.cert_file}")
                logger.info(f"{self.name}: {self.mode}代理服务器私钥文件: {self.key_file}")

            # 创建UDP监听线程
            self._udp_listening = True
            self._udp_thread = threading.Thread(
                target=self._udp_listener,
                daemon=True,
                name=f"{self.name}-UDP-Listener"
            )
            self._udp_thread.start()

            logger.debug(f"{self.name}: UDP监听线程已启动")

            # 等待UDP端口分配完成
            for _ in range(10):
                if hasattr(self, '_udp_port') and self._udp_port is not None:
                    break
                time.sleep(0.1)

            if self._udp_port:
                logger.debug(f"{self.name}: UDP监听端口分配完成: {self._udp_port}")
            else:
                logger.warning(f"{self.name}: UDP端口分配超时，唤醒功能可能不可用")

            self._create_wakeup_socket()
            return True

        except ssl.SSLError as e:
            logger.error(f"{self.name}: SSL证书错误: {e}")
            return False
        except Exception as e:
            logger.error(f"{self.name}: {self.mode}代理服务器启动失败: {e}")
            # import traceback
            # traceback.print_exc()
            self.running = False
            return False

    def _run_server(self):
        """运行服务器"""
        try:
            while self.running and not self._stop_event.is_set():
                try:
                    if self.server is not None:
                        self.server.handle_request()
                except socket.timeout:
                    continue
                except ssl.SSLError as e:
                    logger.debug(f"{self.name}: SSL连接错误: {e}")
                    continue
                except OSError as e:
                    if self.running and not self._force_stop:
                        if e.errno in [10053, 10054, 10038]:
                            logger.debug(f"{self.name}: 客户端连接错误: {e}")
                            continue
                        logger.debug(f"{self.name}: {self.mode} 代理服务器 OS 错误: {e}")
                    break
                except Exception as e:
                    if self.running and not self._force_stop:
                        logger.error(f"{self.name}: {self.mode} 代理服务器处理请求异常: {e}")
                        time.sleep(0.1)
        except Exception as e:
            if self.running and not self._force_stop:
                logger.error(f"{self.name}: {self.mode} 代理服务器运行异常: {e}")
        finally:
            self.running = False
            logger.debug(f"{self.name}: {self.mode} 代理服务器线程退出")

    def _create_wakeup_socket(self) -> None:
        """创建用于唤醒服务器的socket"""
        try:
            self._wakeup_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._wakeup_socket.settimeout(1)
            logger.debug(f"{self.name}: 创建UDP唤醒socket成功")
        except Exception as e:
            logger.debug(f"{self.name}: 创建UDP唤醒socket失败: {e}")

    def _wakeup_server(self) -> None:
        """唤醒服务器使其退出循环"""
        if not self._wakeup_socket:
            return

        if not hasattr(self, '_udp_port') or self._udp_port is None:
            logger.debug(f"{self.name}: UDP端口未分配，无法发送唤醒信号")
            return

        try:
            self._wakeup_socket.sendto(
                b'SHUTDOWN',
                (self.listen_host, self._udp_port)
            )
            logger.debug(f"{self.name}: UDP唤醒信号已发送到端口 {self._udp_port}")
        except Exception as e:
            logger.debug(f"{self.name}: 发送UDP唤醒信号失败: {e}")
        finally:
            if self._wakeup_socket:
                self._wakeup_socket.close()
                self._wakeup_socket = None

    def _udp_listener(self):
        """UDP监听线程，接收唤醒信号"""
        udp_socket = None
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_socket.bind((self.listen_host, 0))
            self._udp_port = udp_socket.getsockname()[1]
            udp_socket.settimeout(1.0)

            logger.debug(f"{self.name}: UDP监听器已启动在 {self.listen_host}:{self._udp_port}")

            while self._udp_listening:
                try:
                    data, addr = udp_socket.recvfrom(1024)
                    if data == b'SHUTDOWN' or data == b'WAKEUP':
                        logger.debug(f"{self.name}: 收到UDP唤醒信号来自 {addr}")
                        self._stop_event.set()
                        break
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._udp_listening:
                        logger.debug(f"{self.name}: UDP监听错误: {e}")
        except Exception as e:
            logger.error(f"{self.name}: UDP监听器异常: {e}")
        finally:
            if udp_socket:
                udp_socket.close()
            self._udp_listening = False
            logger.debug(f"{self.name}: UDP监听器已停止")

    def stop(self):
        """停止 HTTP 代理服务器"""
        if not self.running:
            logger.debug(f"{self.name}: 代理服务器未运行，无需停止")
            return

        logger.info(f"{self.name}: 正在停止 {self.mode} 代理服务器...")

        # 1. 发送UDP唤醒信号
        if hasattr(self, '_udp_port') and self._udp_port:
            self._wakeup_server()

        # 2. 设置停止标志
        self.running = False
        self._udp_listening = False
        self._stop_event.set()

        # 3. 等待UDP线程
        if hasattr(self, '_udp_thread') and self._udp_thread and self._udp_thread.is_alive():
            self._udp_thread.join(timeout=1)
            if self._udp_thread.is_alive():
                logger.debug(f"{self.name}: UDP线程仍在运行，强制继续")

        # 4. 等待主线程
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        # 5. 关闭TCP服务器
        if self.server:
            try:
                self.server.server_close()
            except Exception as e:
                logger.debug(f"{self.name}: 关闭TCP服务器时出错: {e}")
            finally:
                self.server = None

        # 6. 清理UDP端口信息
        if hasattr(self, '_udp_port'):
            self._udp_port = None

        logger.info(f"{self.name}: {self.mode} 代理服务器已完全停止")

    def is_running(self):
        """检查是否在运行"""
        return self.running and not self._stop_event.is_set()

    def get_status(self):
        """获取状态信息"""
        if self.is_running():
            auth_status = "认证" if self.auth_enabled else "无认证"
            return f"🔐 运行中 ({auth_status})"
        else:
            return "🔴 未运行"

    def get_config_info(self):
        """获取配置信息"""
        cert_exists = os.path.exists(self.cert_file) if self.cert_file else False
        key_exists = os.path.exists(self.key_file) if self.key_file else False

        return {
            'name': self.name,
            'mode': self.mode,
            'listen_host': self.listen_host,
            'listen_port': self.listen_port,
            'egress_ip': self.egress_ip,
            'egress_port': self.egress_port,
            'cert_exists': cert_exists,
            'key_exists': key_exists,
            'cert_file': self.cert_file,
            'key_file': self.key_file,
            'auth_enabled': self.auth_enabled,
            'security_enabled': self.security_enabled,
            'proxy_protocol': self.proxy_protocol,
            'stats_enabled': self.stats_enabled,
        }


class HTTPProxyHandler(http.server.BaseHTTPRequestHandler):
    """
    HTTP代理请求处理器 - 直接连接到目标网站（绑定指定网卡）
    """

    def __init__(self,
                *args,
                name: str = 'Unknown',
                egress_ip: str = '0.0.0.0',
                egress_port: int = 0,
                dns_resolver: Optional[DNSResolver] = None,
                stats_enabled: bool = True,
                stats_manager: Optional[StatsManager] = None,
                auth_enabled: bool = False,
                user_manager=None,
                security_enabled=False,
                security_manager=None,
                ip_geo_manager=None,
                mode: str = 'http',
                **kwargs):
        self.name = name
        self.egress_ip = egress_ip
        self.egress_port = egress_port
        self.dns_resolver = dns_resolver

        self.stats_enabled = stats_enabled
        self.stats_manager = stats_manager

        self.auth_enabled = auth_enabled
        self.user_manager = user_manager
        self.security_enabled = security_enabled
        self.security_manager = security_manager
        self.ip_geo_manager = ip_geo_manager
        self.location_info = ""

        self._timeout = 30
        self._authenticated = False
        self.current_user = ""
        self._real_client_ip = None
        self.client_ip = None

        # 连接统计相关
        self.connection_id = ""
        self.total_sent_to_client = 0
        self.total_received_from_client = 0

        self.mode = mode

        self._request_terminated = False  # 黑名单解析标志位
        super().__init__(*args, **kwargs)

    def handle_one_request(self):
        """重写单个请求处理流程"""
        connection_success: bool = False

        try:
            # 建立连接
            self.setup()

            # 获取IP地理位置信息
            if self.client_ip and self.ip_geo_manager:
                try:
                    self.location_info = self.ip_geo_manager.get_ip_location_string(self.client_ip)
                    logger.debug(f"{self.name}: 获取到地理位置信息: {self.location_info}")
                except Exception as e:
                    logger.debug(f"{self.name}: 获取IP地理位置失败: {e}")

            logger.info(f"{self.name}:📞收到新的{self.mode}代理连接请求，来自 {self.client_ip} {self.location_info}")

            # ==================== 安全检查顺序 ====================

            # 1. 快速连接检测（应该在安全检查之前）
            if self.security_enabled and self.security_manager and self.client_ip:
                try:
                    logger.debug(f"{self.name}: 执行快速连接检测...")
                    if self.security_manager.record_connection(self.client_ip, protocol='http'):
                        logger.warning(f"{self.name}: 🚨检测到快速连接攻击 - IP {self.client_ip} {self.location_info}")
                        self.send_error_encoded(429, "Too Many Requests")
                        self.close_connection = True
                        return
                except Exception as e:
                    logger.debug(f"{self.name}: 记录连接失败: {e}")

            # 2. IP黑白名单检查
            if self.security_enabled and self.security_manager:
                logger.debug(f"{self.name}: 执行IP黑白名单检查...")
                if not self.security_manager.is_ip_allowed(self.client_ip):
                    logger.warning(f"{self.name}: 🛡️IP {self.client_ip} {self.location_info} 被安全策略拒绝")
                    self.send_error_encoded(403, "Access Denied by Security Policy")
                    self.close_connection = True
                    return

            # 设置socket超时用于读取请求行
            self.connection.settimeout(5.0)

            # 读取请求行
            try:
                logger.debug(f"{self.name}: 开始读取请求行...")
                self.raw_requestline = self.rfile.readline(65537)
                logger.debug(f"{self.name}: 读取到请求行: {self.raw_requestline}")
            except socket.timeout:
                logger.debug(f"{self.name}: 读取请求行超时")
                self.send_error_encoded(408, "Request Timeout")
                self.close_connection = True
                return
            except Exception as e:
                logger.error(f"{self.name}: 读取请求行失败: {e}")
                self.close_connection = True
                return

            if not self.raw_requestline:
                logger.debug(f"{self.name}: 连接已关闭，没有收到请求行")
                self.close_connection = True
                return

            if len(self.raw_requestline) > 65536:
                logger.warning(f"{self.name}: 请求行过长 - IP {self.client_ip}")
                if self.security_enabled and self.security_manager:
                    try:
                        if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_request'):
                            logger.warning(f"{self.name}: 🛡️已自动封禁畸形请求攻击IP: {self.client_ip}")
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                self.send_error_encoded(414, "Request URI Too Long")
                self.close_connection = True
                return

            # 重置超时时间为正常值
            self.connection.settimeout(self._timeout)

            # 解析请求
            logger.debug(f"{self.name}: 开始解析请求...")
            if not self.parse_request():
                logger.warning(f"{self.name}: 请求解析失败")
                if self.security_enabled and self.security_manager and self.client_ip:
                    try:
                        if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_request'):
                            logger.warning(f"{self.name}: 🛡️已自动封禁畸形请求攻击IP: {self.client_ip}")
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                self.close_connection = True
                return

            logger.debug(f"{self.name}: 请求解析成功: {self.command} {self.path} {self.request_version}")

            # 3. HTTP协议层面的攻击检测
            logger.debug(f"{self.name}: 开始HTTP协议攻击检测...")
            self._detect_http_protocol_attacks()
            if self.close_connection:
                logger.debug(f"{self.name}: HTTP协议攻击检测要求关闭连接")
                return

            # 4. 检查可疑HTTP头
            if self.security_enabled and self.security_manager and self.client_ip:
                logger.debug(f"{self.name}: 检查可疑HTTP头...")
                suspicious_headers = self._check_suspicious_headers()
                if suspicious_headers:
                    logger.warning(f"{self.name}: 检测到可疑HTTP头 - IP {self.client_ip} {self.location_info} - {suspicious_headers}")
                    try:
                        if self.security_manager.record_scan_attempt(self.client_ip, 'suspicious_headers'):
                            logger.warning(f"{self.name}: 🛡️已自动封禁可疑头攻击IP: {self.client_ip}")
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                    self.send_error_encoded(400, "Suspicious Request Headers")
                    self.close_connection = True
                    return

            # 认证检查
            if self.auth_enabled and not self._authenticated:
                logger.debug(f"{self.name}: 开始认证检查...")
                if not self.check_pre_auth():
                    logger.debug(f"{self.name}: 认证检查失败")
                    return
                self._authenticated = True
                logger.debug(f"{self.name}: 认证检查成功，用户: {self.current_user}")

            # 记录连接开始（在认证成功后）
            if self.stats_enabled and self.stats_manager:
                self.connection_id = self.stats_manager.record_connection_start(
                    ip=self.client_ip,
                    protocol=self.mode,
                    country=self.location_info,
                    proxy_name=self.name,
                    user=self.current_user if self.auth_enabled else "无认证"
                )
                logger.debug(f"{self.name}: 记录连接开始: {self.connection_id}")

            # ==================== 处理实际请求 ====================

            # 处理请求
            mname = 'do_' + self.command
            if not hasattr(self, mname):
                logger.warning(f"{self.name}: 不支持的HTTP方法: {self.command} - IP {self.client_ip}")
                if self.security_enabled and self.security_manager and self.client_ip:
                    try:
                        if self.security_manager.record_scan_attempt(self.client_ip, 'invalid_http_method'):
                            logger.warning(f"{self.name}: 🛡️已自动封禁无效HTTP方法攻击IP: {self.client_ip}")
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                self.send_error_encoded(501, f"Unsupported method: {self.command}")
                self.close_connection = True
                return

            method = getattr(self, mname)
            logger.debug(f"{self.name}: 开始处理{self.command}请求...")
            method()

            # 检查请求是否被解析黑名单提前终止
            if self._request_terminated:
                logger.debug(f"{self.name}: 请求被提前终止")
                return  # 直接返回，不标记为成功

            logger.debug(f"{self.name}: {self.command}请求处理完成")

            connection_success = True

        except ssl.SSLError as e:
            client_ip = getattr(self, '_real_client_ip', '未知')
            error_detail = self.get_ssl_error_detail(e)
            logger.warning(f"{self.name}: ❓SSL错误 from {client_ip}: {error_detail}")
            try:
                self.send_error_encoded(400, "SSL Handshake Error")
            except:
                pass
            self.close_connection = True
            connection_success = False
        except socket.timeout as e:
            logger.debug(f"{self.name}: 请求超时: {e}")
            try:
                self.send_error_encoded(408, "Request Timeout")
            except:
                pass
            self.close_connection = True
            connection_success = False
        except (ConnectionResetError, BrokenPipeError) as e:
            client_ip = getattr(self, '_real_client_ip', '未知')
            logger.debug(f"{self.name}: 连接重置 from {client_ip}: {e}")
            connection_success = False
        except Exception as e:
            client_ip = getattr(self, '_real_client_ip', '未知')
            logger.error(f"{self.name}: ❓处理请求异常 from {client_ip}: {e}", exc_info=True)
            try:
                self.send_error_encoded(500, "Internal Server Error")
            except:
                pass
            self.close_connection = True
            connection_success = False
        finally:
            # 记录连接结束
            if self.stats_enabled and self.stats_manager and self.connection_id:
                self.stats_manager.record_connection_end(
                    connection_id=self.connection_id,
                    bytes_sent=self.total_sent_to_client,
                    bytes_received=self.total_received_from_client,
                    success=connection_success,
                )
                logger.debug(f"{self.name}: 记录连接结束: {self.connection_id}, 成功: {connection_success}")

            try:
                self.finish()
                logger.debug(f"{self.name}: 连接清理完成")
            except Exception as e:
                logger.debug(f"{self.name}: 清理连接时出错: {e}")


    def _detect_http_protocol_attacks(self):
        """检测HTTP协议层面的攻击 - 修复版本"""
        # 检查是否启用了安全管理和扫描防护
        if not self.security_enabled:
            logger.debug(f"{self.name}: 安全管理未启用，跳过攻击检测")
            return  # 直接返回，继续处理请求

        if not self.security_manager:
            logger.debug(f"{self.name}: 安全管理器为空，跳过攻击检测")
            return

        if not self.client_ip:
            logger.warning(f"{self.name}: 客户端IP为空，跳过攻击检测")
            return

        location_display = f"{self.location_info}" if self.location_info else ""

        logger.debug(f"{self.name}: 开始HTTP协议攻击检测...")

        try:
            # 1. 检测无效的HTTP方法
            logger.debug(f"{self.name}: 检查HTTP方法: {self.command}")
            if self.command not in ['CONNECT', 'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS']:
                logger.warning(f"{self.name}: 检测到无效HTTP方法: {self.command} - IP {self.client_ip} {location_display}")
                if self.security_manager.record_scan_attempt(self.client_ip, 'invalid_http_method'):
                    logger.warning(f"{self.name}: 🛡️已自动封禁无效HTTP方法攻击IP: {self.client_ip}")
                self.send_error_encoded(400, "Invalid HTTP Method")
                self.close_connection = True
                return

            # 2. 检测畸形的HTTP请求行
            logger.debug(f"{self.name}: 检查请求行: path={self.path}, version={self.request_version}")
            if not self.path or not self.request_version:
                logger.warning(f"{self.name}: 检测到畸形HTTP请求行 - IP {self.client_ip} {location_display}")
                if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_request'):
                    logger.warning(f"{self.name}: 🛡️已自动封禁畸形请求攻击IP: {self.client_ip}")
                self.send_error_encoded(400, "Malformed Request Line")
                self.close_connection = True
                return

            # 3. 对于CONNECT方法，检查目标格式
            logger.debug(f"{self.name}: 检查CONNECT方法目标格式...")
            if self.command == 'CONNECT':
                if ':' not in self.path:
                    logger.warning(f"{self.name}: 检测到畸形CONNECT请求: {self.path} - IP {self.client_ip} {location_display}")
                    if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_connect'):
                        logger.warning(f"{self.name}: 🛡️已自动封禁畸形CONNECT攻击IP: {self.client_ip}")
                    self.send_error_encoded(400, "Malformed CONNECT Request")
                    self.close_connection = True
                    return

                try:
                    host, port_str = self.path.split(':', 1)
                    port = int(port_str)
                    if port <= 0 or port > 65535:
                        logger.warning(f"{self.name}: 检测到无效端口号范围: {port} - IP {self.client_ip} {location_display}")
                        raise ValueError("Invalid port range")
                    logger.debug(f"{self.name}: CONNECT目标解析成功: host={host}, port={port}")
                except (ValueError, IndexError) as e:
                    logger.warning(f"{self.name}: 检测到无效端口号: {self.path} - IP {self.client_ip} {location_display}")
                    if self.security_manager.record_scan_attempt(self.client_ip, 'invalid_port'):
                        logger.warning(f"{self.name}: 🛡️已自动封禁无效端口攻击IP: {self.client_ip}")
                    self.send_error_encoded(400, "Invalid Port Number")
                    self.close_connection = True
                    return

            logger.debug(f"{self.name}: HTTP协议攻击检测通过")

        except Exception as e:
            logger.error(f"{self.name}: HTTP协议攻击检测失败: {e}", exc_info=True)
            # 不要因为检测失败而阻止正常请求
            # 只是记录错误，但不设置close_connection

    def _check_suspicious_headers(self):
        """检查可疑的HTTP请求头"""
        suspicious_headers = []
        suspicious_patterns = [
            ('user-agent', ['sqlmap', 'nikto', 'nmap', 'nessus', 'metasploit', 'wpscan', 'acunetix']),
            ('host', ['localhost', '127.0.0.1', '0.0.0.0', '::1']),
            ('referer', ['javascript:', 'data:', 'file://']),
            ('content-type', ['application/x-www-form-urlencoded', 'multipart/form-data']),
        ]

        for header_name, patterns in suspicious_patterns:
            header_value = self.headers.get(header_name, '').lower()
            for pattern in patterns:
                if pattern in header_value:
                    suspicious_headers.append(f"{header_name}: {header_value}")
                    break

        return suspicious_headers

    def check_pre_auth(self) -> bool:
        """代理认证主流程，包含认证失败的安全管理"""
        try:
            location_display = f"{self.location_info}" if self.location_info else ""

            logger.debug(f"{self.name}: 开始认证检查...")

            # 再次安全检查
            if self.security_enabled and self.security_manager:
                if not self.security_manager.is_ip_allowed(self.client_ip):
                    logger.warning(f"{self.name}: 🛡️IP {self.client_ip} {location_display} 被安全策略拒绝")
                    self.send_error_encoded(403, "Access Denied by Security Policy")
                    self.close_connection = True
                    return False

            auth_header = self.headers.get('Proxy-Authorization', '')
            logger.debug(f"{self.name}: 认证头: {auth_header[:20]}...")  # 只显示前20字符

            if not auth_header.startswith('Basic '):
                logger.debug(f"{self.name}: 缺少或错误的认证头 - 客户端: {self._real_client_ip} {location_display}")

                if self.security_enabled and self.security_manager:
                    try:
                        self.security_manager.record_auth_failure(self.client_ip, protocol='http')
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录认证失败失败: {e}")

                self.send_pre_auth_required()
                self.close_connection = True
                return False

            try:
                auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = auth_decoded.split(':', 1)
                logger.debug(f"{self.name}: 解析的用户名: {username}")
            except Exception as e:
                logger.debug(f"{self.name}: 解析认证信息失败: {e} - 客户端: {self._real_client_ip} {location_display}")

                if self.security_enabled and self.security_manager:
                    try:
                        self.security_manager.record_auth_failure(self.client_ip, protocol='http')
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录认证失败失败: {e}")

                self.send_pre_auth_required()
                self.close_connection = True
                return False

            if self.user_manager and not self.user_manager.verify_user_credentials(username, password):
                logger.warning(f"{self.name}: ❌用户认证失败: 凭据错误 - 客户端: {self._real_client_ip} {location_display} [验证名：{username}]")

                if self.security_enabled and self.security_manager:
                    try:
                        self.security_manager.record_auth_failure(self.client_ip, protocol='http')
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录认证失败失败: {e}")

                self.send_pre_auth_required()
                self.close_connection = True
                return False

            logger.info(f"{self.name}:✅ 认证成功 - 客户端: {self._real_client_ip} {location_display} [用户名：{username}]")

            if self.security_enabled and self.security_manager:
                try:
                    self.security_manager.record_auth_success(self.client_ip)
                except Exception as e:
                    logger.debug(f"{self.name}: 记录认证成功失败: {e}")

            self.current_user = username
            return True

        except Exception as e:
            logger.error(f"{self.name}: 认证检查错误: {e}", exc_info=True)

            if self.security_enabled and self.security_manager:
                try:
                    self.security_manager.record_auth_failure(self.client_ip, protocol='http')
                except Exception as e:
                    logger.debug(f"{self.name}: 记录认证失败失败: {e}")

            self.send_pre_auth_required()
            self.close_connection = True
            return False

    def send_pre_auth_required(self):
        """认证错误时发送继续认证要求"""
        try:
            # 发送正确的407响应
            error_message = 'Proxy Authentication Required'
            response = (
                f"HTTP/1.1 407 Proxy Authentication Required\r\n"
                f"Proxy-Authenticate: Basic realm=\"HTTPS Proxy Authentication Required\"\r\n"
                f"Content-Type: text/html\r\n"
                f"Content-Length: {len(error_message)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"{error_message}"
            )

            logger.debug(f"{self.name}: 发送407认证要求")
            self.wfile.write(response.encode('utf-8'))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.debug(f"{self.name}: 发送认证要求时连接断开: {e}")
        except Exception as e:
            logger.debug(f"{self.name}: 发送认证要求失败: {e}")

    def do_CONNECT(self):
        """处理 HTTPS 连接（隧道模式）- 修复版本"""
        try:
            logger.debug(f"{self.name}: 开始处理CONNECT请求: {self.path}")

            host, port = self.path.split(':', 1)
            port = int(port)

            logger.debug(f"{self.name}: 建立HTTPS隧道连接: {host}:{port} [{self.current_user}]")

            # 解析目标地址（支持域名）
            target_ip = self.resolve_target(host, port)
            logger.debug(f"{self.name}: DNS解析结果: {host} -> {target_ip}")

            if target_ip == '0.0.0.0':
                logger.warning(f"{self.name}: 🚫 拒绝黑名单域名访问: {host} -> {target_ip}")
                self.send_error_encoded(403, "Access to this domain is blocked by proxy policy")
                self._request_terminated = True  # 设置终止标志
                return

            # 创建到目标服务器的连接（绑定到指定网卡）
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(self._timeout)

            try:
                # 绑定到指定的出口网卡
                logger.debug(f"{self.name}: 绑定到出口网卡: {self.egress_ip}:{self.egress_port}")
                server_socket.bind((self.egress_ip, self.egress_port))
                logger.debug(f"{self.name}: 连接到目标服务器: {target_ip}:{port}")
                server_socket.connect((target_ip, port))
            except OSError as e:
                # 如果绑定特定端口失败，尝试系统分配端口
                if "Address already in use" in str(e):
                    logger.warning(f"{self.name}: 端口 {self.egress_port} 被占用，使用系统分配端口")
                    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    server_socket.settimeout(self._timeout)
                    server_socket.connect((target_ip, port))
                else:
                    raise

            logger.info(f"{self.name}: CONNECT连接到目标服务器成功:{host}({target_ip}):{port}")

            # 告诉客户端隧道建立
            logger.debug(f"{self.name}: 发送200 OK响应")
            self.send_response(200)
            self.send_header('Proxy-Connection', 'close')
            self.end_headers()

            # 双向数据转发（包含流量统计）
            logger.debug(f"{self.name}: 开始数据转发...")
            self.relay_data_with_stats(self.connection, server_socket)

        except socket.timeout as e:
            logger.error(f"{self.name}: 连接目标服务器超时: {e}")
            self.send_error_encoded(504, "Connection timeout")
        except ConnectionRefusedError as e:
            logger.error(f"{self.name}: 目标服务器拒绝连接: {e}")
            self.send_error_encoded(502, "Connection refused by target server")
        except Exception as e:
            logger.error(f"{self.name}: 建立HTTPS隧道错误: {e}", exc_info=True)
            try:
                self.send_error_encoded(502, str(e)[:100])
            except:
                pass

    def resolve_target(self, host: str, port: int) -> str:
        """解析目标地址，支持域名解析"""
        try:
            # 尝试解析为IP地址
            try:
                socket.inet_aton(host)
                return host  # 已经是IP地址
            except socket.error:
                # 是域名，需要DNS解析
                if self.dns_resolver:
                    # 使用DNS解析器解析
                    return self.dns_resolver.resolve(host, self.egress_ip)
                else:
                    # 使用系统DNS解析
                    logger.debug(f"{self.name}: 使用系统DNS解析: {host}")
                    result = socket.getaddrinfo(host, port, family=socket.AF_INET)
                    if result:
                        target_ip = result[0][4][0]
                        logger.debug(f"{self.name}: 系统DNS解析成功: {host} -> {target_ip}")
                        return str(target_ip)
                    else:
                        raise RuntimeError(f"{self.name}: DNS解析返回空结果")
        except Exception as e:
            logger.error(f"{self.name}: DNS解析失败 {host}: {e}")
            raise Exception(f"DNS解析失败: {e}")

    def handle_http_request(self, method):
        """处理 HTTP 请求"""
        try:
            logger.debug(f"{self.name}: 开始处理HTTP请求: {method} {self.path}")

            # 直接从Host头获取目标
            host_header = self.headers.get('Host', '')
            if not host_header:
                self.send_error_encoded(400, "Missing Host header")
                return

            # 解析主机和端口
            if ':' in host_header:
                target_host, port_str = host_header.split(':', 1)
                try:
                    target_port = int(port_str)
                    if target_port == 443:  # 如果客户端错误指定443端口
                        logger.warning(f"{self.name}: 客户端指定端口443，改为80")
                        target_port = 80
                except ValueError:
                    target_host = host_header
                    target_port = 80
            else:
                target_host = host_header
                target_port = 80

            logger.debug(f"{self.name}: HTTP请求: {method} {self.path} -> {target_host}:{target_port}")

            # 解析目标地址
            target_ip = self.resolve_target(target_host, target_port)
            if target_ip == '0.0.0.0':
                logger.warning(f"{self.name}: 🚫 拒绝黑名单域名访问: {target_host} -> {target_ip}")
                self.send_error_encoded(403, "Access to this domain is blocked by proxy policy")
                self._request_terminated = True  # 设置终止标志
                return  # 提前返回

            # 创建到目标服务器的连接（绑定到指定网卡）
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(self._timeout)

            try:
                # 绑定到指定的出口网卡
                server_socket.bind((self.egress_ip, self.egress_port))
                server_socket.connect((target_ip, target_port))
            except OSError as e:
                # 如果绑定特定端口失败，尝试系统分配端口
                if "Address already in use" in str(e):
                    logger.warning(f"{self.name}: 端口 {self.egress_port} 被占用，使用系统分配端口")
                    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    server_socket.settimeout(self._timeout)
                    server_socket.connect((target_ip, target_port))
                else:
                    raise

            logger.info(f"{self.name}: {method}成功连接到目标服务器:{target_host}({target_ip}):{target_port}")

            # 使用http.client发送请求
            conn = None
            try:
                # 创建HTTP连接
                conn = http.client.HTTPConnection(
                    host=target_ip,
                    port=target_port,
                    timeout=self._timeout
                )

                # 使用我们自己的socket（已经绑定到指定网卡）
                conn.sock = server_socket

                # 读取请求体
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length) if content_length > 0 else b''

                # 准备请求头
                headers = {}
                for key, value in self.headers.items():
                    key_lower = key.lower()
                    if key_lower not in ['proxy-connection', 'proxy-authorization',
                                        'proxy-authenticate', 'connection']:
                        if key_lower == 'host':
                            headers['Host'] = f"{target_host}:{target_port}"
                        else:
                            headers[key] = value

                if 'connection' not in headers:
                    headers['Connection'] = 'close'

                # 构建请求路径
                request_path = self.path
                if request_path.startswith('http://'):
                    parsed = urlparse(request_path)
                    request_path = parsed.path
                    if parsed.query:
                        request_path += '?' + parsed.query
                elif not request_path.startswith('/'):
                    request_path = '/' + request_path

                logger.debug(f"{self.name}: 发送HTTP请求: {method} {request_path}")

                # 记录从客户端接收的流量
                if self.stats_enabled and self.stats_manager:
                    # 估算请求头大小
                    header_size = len(f"{method} {request_path} HTTP/1.1\r\n")
                    for key, value in headers.items():
                        header_size += len(f"{key}: {value}\r\n")
                    header_size += len("\r\n")

                    received_request_from_client = header_size + len(body)
                    self.total_received_from_client += received_request_from_client

                    self.stats_manager.record_traffic(
                        bytes_sent=0,
                        bytes_received=received_request_from_client,
                        protocol=self.mode,
                        country=self.location_info,
                        proxy_name=self.name,
                        ip=self.client_ip,
                        user=self.current_user,
                        connection_id=self.connection_id,
                    )

                # 发送请求
                conn.request(
                    method=method,
                    url=request_path,
                    body=body,
                    headers=headers
                )

                # 获取响应
                try:
                    response = conn.getresponse()

                    # 统计发送给客户端的流量（响应头）
                    if self.stats_enabled and self.stats_manager:
                        # 估算响应头大小
                        sent_header_to_client = len(f"HTTP/1.1 {response.status} {response.reason}\r\n")
                        for header, value in response.getheaders():
                            sent_header_to_client += len(f"{header}: {value}\r\n")
                        sent_header_to_client += len("\r\n")

                        self.total_sent_to_client += sent_header_to_client
                        self.stats_manager.record_traffic(
                                    bytes_sent=sent_header_to_client,
                                    bytes_received=0,
                                    protocol=self.mode,
                                    country=self.location_info,
                                    proxy_name=self.name,
                                    ip=self.client_ip,
                                    user=self.current_user,
                                    connection_id=self.connection_id,
                                )

                    # 转发响应给客户端
                    self.send_response(response.status, response.reason)

                    # 转发响应头
                    for header, value in response.getheaders():
                        if header.lower() not in ['transfer-encoding', 'connection']:
                            self.send_header(header, value)

                    # 设置正确的Content-Length
                    content_length_header = response.getheader('Content-Length')
                    if content_length_header:
                        self.send_header('Content-Length', content_length_header)

                    self.send_header('Connection', 'close')
                    self.end_headers()

                    # 转发响应体并统计流量
                    try:
                        while True:
                            chunk = response.read(4096)
                            if not chunk:
                                break
                            self.wfile.write(chunk)

                            # 统计发送给客户端的流量（响应体）
                            if self.stats_enabled and self.stats_manager:
                                sent_chunk_to_client = len(chunk)
                                self.total_sent_to_client += sent_chunk_to_client
                                self.stats_manager.record_traffic(
                                    bytes_sent=sent_chunk_to_client,
                                    bytes_received=0,
                                    protocol=self.mode,
                                    country=self.location_info,
                                    proxy_name=self.name,
                                    ip=self.client_ip,
                                    user=self.current_user,
                                    connection_id=self.connection_id,
                                )
                    except (ConnectionResetError, BrokenPipeError) as e:
                        logger.debug(f"{self.name}: 客户端在接收响应体时断开连接: {e}")

                    logger.info(f"{self.name}: HTTP响应成功: {method} {self.path} -> {response.status}")

                except http.client.RemoteDisconnected as e:
                    logger.warning(f"{self.name}: 目标服务器断开连接: {e}")
                    self.send_error_encoded(502, "Target server closed connection")

                except socket.timeout as e:
                    logger.warning(f"{self.name}: 读取响应超时: {e}")
                    self.send_error_encoded(504, "Gateway Timeout")

                except Exception as e:
                    logger.error(f"{self.name}: 获取响应失败: {e}")
                    # 使用安全的错误消息
                    self.send_error_encoded(502, f"Failed to get response: {str(e)[:100]}")

            except socket.timeout as e:
                logger.error(f"{self.name}: 连接目标服务器超时: {e}")
                self.send_error_encoded(504, "Connection timeout")

            except ConnectionRefusedError as e:
                logger.error(f"{self.name}: 目标服务器拒绝连接: {e}")
                self.send_error_encoded(502, "Connection refused by target server")

            except Exception as e:
                logger.error(f"{self.name}: HTTP请求处理失败: {e}", exc_info=True)
                try:
                    self.send_error_encoded(502, str(e)[:100])
                except:
                    pass

            finally:
                # 确保关闭连接
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
                elif server_socket:
                    try:
                        server_socket.close()
                    except:
                        pass

        except Exception as e:
            logger.error(f"{self.name}: HTTP请求处理异常: {e}", exc_info=True)
            try:
                self.send_error_encoded(500, "Internal Server Error")
            except:
                pass

    def send_error_encoded(self, code, message=None):
        """发送错误响应，处理编码问题"""
        try:
            # 确保消息是ASCII安全的
            if message:
                # 将非ASCII字符替换为?
                safe_message = ''
                for char in message:
                    try:
                        char.encode('latin-1')
                        safe_message += char
                    except UnicodeEncodeError:
                        safe_message += '?'
                message = safe_message

            # 发送完整的HTTP响应
            self.send_response(code, message or "")
            self.send_header('Content-Type', 'text/plain; charset=utf-8')

            # 根据HTTP规范，一些状态码需要响应体
            if code not in [204, 304]:
                error_body = f"Error {code}: {message or ''}\r\n"
                self.send_header('Content-Length', str(len(error_body.encode('utf-8'))))
            else:
                self.send_header('Content-Length', '0')

            self.send_header('Connection', 'close')
            self.end_headers()

            # 发送响应体
            if code not in [204, 304]:
                try:
                    self.wfile.write(error_body.encode('utf-8'))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError) as e:
                    logger.debug(f"{self.name}: 发送错误响应体时连接断开: {e}")

            logger.debug(f"{self.name}: 发送错误响应 {code}: {message}")

        except Exception as e:
            logger.debug(f"{self.name}: 发送错误响应失败: {e}")
            try:
                # 最后尝试：发送最基本的HTTP响应
                basic_response = f"HTTP/1.1 {code} Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                self.wfile.write(basic_response.encode('latin-1'))
                self.wfile.flush()
            except Exception as inner_e:
                logger.debug(f"{self.name}: 发送基本响应也失败: {inner_e}")

    def relay_data_with_stats(self, client_conn, target_sock):
        """在客户端和目标服务器之间双向转发数据，包含流量统计"""
        try:
            logger.debug(f"{self.name}: 开始数据转发...")
            while True:
                rlist, _, _ = select.select([client_conn, target_sock], [], [], 1)
                if not rlist:
                    continue

                for sock in rlist:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            logger.debug(f"{self.name}: 连接关闭，停止数据转发")
                            return  # 连接关闭

                        if sock is client_conn:
                            # 从客户端接收，发往目标服务器
                            target_sock.sendall(data)

                            # 统计接收的流量
                            if self.stats_enabled and self.stats_manager:
                                received_from_client_once = len(data)
                                self.total_received_from_client += received_from_client_once
                                self.stats_manager.record_traffic(
                                    bytes_sent=0,
                                    bytes_received=received_from_client_once,
                                    protocol=self.mode,
                                    country=self.location_info,
                                    proxy_name=self.name,
                                    ip=self.client_ip,
                                    user=self.current_user,
                                    connection_id=self.connection_id,
                                )
                        else:
                            # 从目标服务器接收，发往客户端
                            client_conn.sendall(data)

                            # 统计发送的流量
                            if self.stats_enabled and self.stats_manager:
                                sent_to_client_once = len(data)
                                self.total_sent_to_client += sent_to_client_once
                                self.stats_manager.record_traffic(
                                    bytes_sent=sent_to_client_once,
                                    bytes_received=0,
                                    protocol=self.mode,
                                    country=self.location_info,
                                    proxy_name=self.name,
                                    ip=self.client_ip,
                                    user=self.current_user,
                                    connection_id=self.connection_id,
                                )
                    except (socket.timeout, BlockingIOError):
                        continue
                    except (ConnectionResetError, BrokenPipeError, OSError) as e:
                        logger.debug(f"{self.name}: 连接异常: {e}")
                        return  # 连接异常
                    except Exception as e:
                        logger.debug(f"{self.name}: 客户端和目标服务器数据转发错误: {e}")
                        return
        except Exception as e:
            logger.debug(f"{self.name}: 客户端和目标服务器数据转发异常: {e}")
        finally:
            if target_sock:
                try:
                    target_sock.close()
                    logger.debug(f"{self.name}: 目标连接已关闭")
                except Exception as e:
                    logger.debug(f"{self.name}: 关闭目标连接失败: {e}")

    def do_GET(self):
        """处理 HTTP GET 请求"""
        self.handle_http_request('GET')

    def do_POST(self):
        """处理 HTTP POST 请求"""
        self.handle_http_request('POST')

    def do_PUT(self):
        """处理 HTTP PUT 请求"""
        self.handle_http_request('PUT')

    def do_DELETE(self):
        """处理 HTTP DELETE 请求"""
        self.handle_http_request('DELETE')

    def do_HEAD(self):
        """处理 HTTP HEAD 请求"""
        self.handle_http_request('HEAD')

    def do_PATCH(self):
        """处理 HTTP PATCH 请求"""
        self.handle_http_request('PATCH')

    def do_OPTIONS(self):
        """处理 HTTP OPTIONS 请求"""
        self.handle_http_request('OPTIONS')

    def get_ssl_error_detail(self, error):
        """获取SSL错误的详细信息"""
        error_str = str(error)

        error_map = {
            'UNEXPECTED_EOF_WHILE_READING': '客户端在SSL握手完成前断开',
            'NO_SHARED_CIPHER': '没有共享的加密套件',
            'UNSUPPORTED_PROTOCOL': '不支持的SSL/TLS协议版本',
            'BAD_KEY_SHARE': 'TLS密钥交换失败',
            'HTTP_REQUEST': 'HTTP请求发送到HTTPS端口',
            'SSLV3_ALERT_HANDSHAKE_FAILURE': 'SSLv3握手失败',
            'DECRYPTION_FAILED': '解密失败或错误记录MAC',
            'BAD_RECORD_MAC': '错误记录MAC',
        }

        for key, description in error_map.items():
            if key in error_str:
                return f"{description} ({key})"

        return f"SSL错误: {error}"

    def setup(self):
        """重写 setup 方法"""
        super().setup()

        # 重置父类可能设置的close_connection
        # 父类为普通HTTP服务器设置的close_connection逻辑不适合代理服务器
        if hasattr(self, 'close_connection') and self.close_connection:
            logger.debug(f"{self.name}: ⚠️ 父类setup设置了close_connection=True，重置为False")
            self.close_connection = False

        # 安全获取真实IP
        self._real_client_ip = None

        if (hasattr(self.server, 'real_ips_dict') and
            isinstance(self.server.real_ips_dict, dict)):
            self._real_client_ip = self.server.real_ips_dict.get(self.connection)

        self.client_ip = self._real_client_ip or self.client_address[0]

        # 记录日志
        source = "【真实客户端】" if self._real_client_ip else "直接连接"
        logger.debug(f"{self.name}: {source}来自 {self.client_ip}")

    def parse_request(self):
        """重写解析请求方法，添加更多日志"""
        try:

            # 调用父类方法
            result = super().parse_request()

            if not result:
                logger.warning(f"{self.name}: 父类parse_request返回False")
                return False

            # 记录解析结果
            logger.debug(f"{self.name}: 解析结果 - 命令: {self.command}, 路径: {self.path}, 版本: {self.request_version}")
            logger.debug(f"{self.name}: 请求头数量: {len(self.headers)}")

            # 🔧 关键修复：重置父类可能设置的close_connection
            # 父类为普通HTTP服务器设置的规则可能不适合代理服务器
            if self.close_connection:
                logger.debug(f"{self.name}: ⚠️ 父类parse_request设置了close_connection=True，重置为False")
                self.close_connection = False

            return True
        except Exception as e:
            logger.error(f"{self.name}: 解析请求时出错: {e}")
            return False

    def log_message(self, format, *args):
        """自定义日志格式"""
        try:
            username = self.current_user if self.auth_enabled else "无认证"
            logger.info(f"{self.name}: 来自 {self.client_ip} {self.location_info} [{username}] 执行 {format % args}")

        except Exception as e:
            logger.error(f"{self.name}: HTTPProxyHandler 日志错误: {e}")


class StandardHTTPServer(socketserver.ThreadingTCPServer):
    """标准HTTPS服务器，支持安全管理器"""

    def __init__(self, server_address, RequestHandlerClass,
                use_https=False, ssl_context=None, name=None, security_enabled=False, security_manager=None, **kwargs):

        self.use_https = use_https
        self.ssl_context = ssl_context
        self.name = name
        self.security_enabled = security_enabled
        self.security_manager = security_manager

        super().__init__(server_address, RequestHandlerClass, **kwargs)


class ProxyProtocolHTTPServer(socketserver.ThreadingTCPServer):
    """支持 Proxy Protocol 和 HTTPS 的自定义 TCP 服务器"""

    def __init__(self, server_address, RequestHandlerClass, proxy_protocol=None,
                 real_ips_dict=None, use_https=False, ssl_context=None, name=None, security_enabled=False, security_manager=None, **kwargs):

        self.proxy_protocol = proxy_protocol
        self.real_ips_dict: Dict[socket.socket, str] = real_ips_dict or {}
        self.use_https = use_https
        self.ssl_context = ssl_context
        self.name = name
        self.security_enabled = security_enabled
        self.security_manager = security_manager
        super().__init__(server_address, RequestHandlerClass, **kwargs)

    def get_request(self):
        """重写获取请求方法，在连接建立时处理 Proxy Protocol 和 SSL"""
        try:
            # 1. 调用父类获取原始socket连接
            sock, addr = super().get_request()

            # 2. 先处理 Proxy Protocol 获取真实IP（在SSL之前）
            real_ip = None
            if self.proxy_protocol:
                try:
                    proxy_info, remaining_data = ProxyProtocolReceiver.receive_and_parse(
                        sock, self.proxy_protocol
                    )
                    if proxy_info:
                        real_ip = proxy_info.get('client_ip')
                        logger.debug(f"{self.name}: Proxy Protocol 解析成功: 真实IP {real_ip} -> 代理IP {addr[0]}")

                    if remaining_data:
                        logger.debug(f"{self.name}: 丢弃Proxy Protocol剩余数据: {len(remaining_data)}字节")

                except Exception as e:
                    logger.debug(f"{self.name}: Proxy Protocol 解析失败: {e}")

            # 3. 存储真实IP信息
            if real_ip:
                self.real_ips_dict[sock] = real_ip
            else:
                self.real_ips_dict[sock] = addr[0]

            # 4. 处理 SSL/TLS 加密
            if self.use_https and self.ssl_context:
                try:
                    original_sock = sock
                    sock = self.ssl_context.wrap_socket(sock, server_side=True)

                    if original_sock in self.real_ips_dict:
                        real_ip_value = self.real_ips_dict[original_sock]
                        del self.real_ips_dict[original_sock]
                        self.real_ips_dict[sock] = real_ip_value

                    logger.debug(f"{self.name}: SSL包装完成")

                except ssl.SSLError as e:
                    client_ip = real_ip or addr[0]
                    logger.warning(f"{self.name}: ❓SSL握手失败 from {client_ip}: {e}")

            return sock, addr

        except Exception as e:
            logger.error(f"{self.name}: ⁉️获取请求失败: {e}")
            raise

    def close_request(self, request):
        """连接关闭时清理字典"""
        if request in self.real_ips_dict:
            del self.real_ips_dict[request]
        super().close_request(request)
