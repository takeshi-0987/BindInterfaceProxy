# -*- coding: utf-8 -*-
"""
Module: socks5_proxy_server.py
Author: Takeshi
Date: 2025-09-29

Description:
    SOCKS5代理服务器
"""

import logging
import select
import socket
import struct
import threading
from typing import Optional, Tuple, Literal

from utils import ProxyProtocolReceiver

from core import DNSResolver

from managers import IPGeoManager, SecurityManager, StatsManager, UserManager


logger = logging.getLogger(__name__)

class SOCKS5ProxyServer:
    def __init__(self,
                 name: str,

                 listen_host: str,
                 listen_port: int,

                 egress_ip: str,
                 egress_port: int = 0,

                 dns_resolver: Optional[DNSResolver] = None,

                 auth_enabled: bool = False,
                 user_manager: Optional[UserManager] = None,

                 proxy_protocol: Optional[Literal['v1', 'v2']] = None,
                 ip_geo_manager: Optional[IPGeoManager] = None,

                 security_enabled: bool = False,
                 security_manager: Optional[SecurityManager] = None,

                 stats_enabled: bool = True,
                 stats_manager: Optional[StatsManager] = None,

                 health_check_mode: bool = False,
                ):
        """
        SOCKS5代理服务器初始化
        """
        # 代理名称
        self.name = name

        # 监听地址
        self.listen_host = listen_host
        self.listen_port = listen_port

        # 出口地址
        self.egress_ip = egress_ip
        self.egress_port = egress_port

        # 是否开启用户认证
        self.auth_enabled = auth_enabled
        self.user_manager = user_manager
        self.current_user: str = ""

        # 客户端ip和地理信息
        self.proxy_protocol = proxy_protocol
        self.ip_geo_manager = ip_geo_manager
        self.client_ip: str = ""     # 客户端ip
        self.location_info: str = ""

        # 自定义dns解析器
        self.dns_resolver = dns_resolver

        # 是否开启安全检查
        self.security_enabled = security_enabled
        self.security_manager = security_manager

        # 是否开启连接和流量统计
        self.stats_enabled = stats_enabled
        self.stats_manager = stats_manager

        # 是否健康检查模式
        self.health_check_mode = health_check_mode
        if self.health_check_mode:
            logger.debug(f"Socks5启用健康模式，启用健康检查功能")
            # self.health_check_passed: bool = False      # 健康检查状态, health_chekcer会检查此状态
            # logger.debug(f"健康状态初始化为 {self.health_check_passed}")

            self.proxy_protocol = None

            self.auth_enabled = False
            logger.debug(f"{self.name}: Socks5启用健康模式，忽略用户认证")

            self.security_enabled = False
            logger.debug(f"{self.name}: Socks5启用健康模式，忽略安全策略")

            self.stats_enabled = False
            logger.debug(f"{self.name}: Socks5启用健康模式，关闭流量统计")


        # 运行参数
        self.running = False
        self.server_socket: Optional[socket.socket] = None


    def handle_client(self, client_socket: socket.socket, client_addr: Tuple[str, int]):
        """处理客户端连接"""

        real_client_ip: Optional[str] = None
        connection_id: str = ""
        total_sent_to_client: int = 0
        total_received_from_client: int = 0
        connection_success: bool = False  # 记录连接是否成功

        try:
            # Proxy Protocol 处理
            if self.proxy_protocol:
                logger.debug(f"{self.name}: handle_client开始处理 Proxy Protocol {self.proxy_protocol}")
                proxy_info, _ = ProxyProtocolReceiver.receive_and_parse(
                    client_socket, self.proxy_protocol
                )

                if proxy_info:
                    real_client_ip = proxy_info.get('client_ip')
                    logger.debug(f"{self.name}: handle_client PP解析成功: 真实IP: {real_client_ip}")
                else:
                    logger.error(f"{self.name}: Proxy Protocol 解析失败或未找到")

            # 记录连接IP
            self.client_ip  = real_client_ip or client_addr[0]

            # 获取IP地理位置信息
            if self.client_ip and not self.location_info:
                try:
                    self.location_info = self.ip_geo_manager.get_ip_location_string(self.client_ip)
                except Exception as e:
                    logger.debug(f"{self.name}: handle_client获取IP地理位置失败: {e}")

            logger.info(f"{self.name}: 📞收到新的SOCKS5请求，来自 {self.client_ip} {self.location_info}")

            # ==================== 安全检查 ====================

            # 1. 检查IP是否被允许（黑白名单）
            if self.security_enabled and self.security_manager:
                if not self.security_manager.is_ip_allowed(self.client_ip):
                    logger.warning(f"{self.name}:🛡️客户端：{self.client_ip} {self.location_info} 被安全策略拒绝")
                    client_socket.close()
                    return

            # 2. 记录连接（快速连接检测）
            # 注意：这应该在握手之前记录，用于检测快速连接攻击
            if self.security_enabled and self.security_manager:
                try:
                    # 记录连接，检测快速连接
                    if self.security_manager.record_connection(self.client_ip, protocol='socks5'):
                        logger.warning(f"{self.name}: 🚨检测到快速连接攻击 - IP {self.client_ip} {self.location_info}")
                        # 快速连接检测已触发封禁，直接关闭连接
                        client_socket.close()
                        return
                except Exception as e:
                    logger.debug(f"{self.name}: 记录连接失败: {e}")

            # ==================== SOCKS5握手 ====================
            if not self.handle_socks5_handshake(client_socket):
                client_socket.close()
                logger.debug(f"{self.name}: {self.client_ip} {self.location_info} 的SOCKS5握手处理失败")
                return
            logger.debug(f"{self.name}: {self.client_ip} {self.location_info} 的SOCKS5握手处理成功")

            # 记录连接开始（握手成功后）
            if self.stats_enabled and self.stats_manager:
                connection_id = self.stats_manager.record_connection_start(
                    ip=self.client_ip,
                    protocol='socks5',
                    country=self.location_info,
                    proxy_name=self.name,
                    user=self.current_user if self.auth_enabled else "无认证",
                )
                logger.debug(f"{self.name}: 记录连接开始：{self.client_ip} socks5 {self.location_info} {self.current_user}")

            # 解析dns请求
            target_ip, target_port, domain = self.parse_socks5_request(client_socket)
            if target_ip == '0.0.0.0':
                logger.warning(f"{self.name}: 🚫 拒绝黑名单域名访问: {domain} -> {target_ip}")
                # 发送拒绝响应
                self.send_socks5_response(client_socket, False)
                return
            logger.debug(f"{self.name}: 向远端目标发起连接: {domain}({target_ip}):{target_port}")

            # 创建到目标服务器的连接（绑定到指定IP）
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(30)
            try:
                server_socket.bind((self.egress_ip, self.egress_port))
                server_socket.connect((target_ip, target_port))
            except OSError as e:
                # 如果绑定特定端口失败，尝试系统分配端口
                if "Address already in use" in str(e):
                    logger.warning(f"{self.name}: 端口 {self.egress_port} 被占用，使用系统分配端口")
                    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    server_socket.settimeout(30)
                    server_socket.connect((target_ip, target_port))
                else:
                    raise

            # 向客户端发送成功连接远端目标的响应
            self.send_socks5_response(client_socket, True)
            logger.info(f"{self.name}: ✈️ Socks5成功连接到目标服务器 {domain}({target_ip}):{target_port}")

            # 开始数据转发并获取流量统计
            total_sent_to_client, total_received_from_client = self.forward_data(client_socket, server_socket, connection_id)

            # 只有forward_data正常返回，才标记为成功
            connection_success = True

        except Exception as e:
            logger.error(f"{self.name}: 处理客户端连接请求时发生未知错误: {e}")
            try:
                # 发送失败请求
                self.send_socks5_response(client_socket, False)
            except:
                pass
            connection_success = False  # 标记为失败
        finally:
            # 记录连接结束
            if connection_id and self.stats_manager:
                self.stats_manager.record_connection_end(
                    connection_id=connection_id,
                    bytes_sent=total_sent_to_client,
                    bytes_received=total_received_from_client,
                    success=connection_success,
                )
                logger.debug(f"{self.name}: 记录连接结束: {connection_id}, 发送: {total_sent_to_client}, 接收: {total_received_from_client}")

            try:
                client_socket.close()
            except:
                pass


    def handle_socks5_handshake(self, client_socket: socket.socket) -> bool:
        """处理SOCKS5握手，支持无认证和用户名密码认证，包含扫描检测"""
        try:
            # 读取版本和方法数量
            data = client_socket.recv(2)
            if len(data) < 2:
                logger.warning(f"{self.name}: 客户端{self.client_ip} {self.location_info}握手失败：接收到的字节少于2，无法进行有效的SOCKS5握手")
                if self.client_ip and self.security_enabled and self.security_manager:
                    try:
                        if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_request'):
                            logger.warning(f"{self.name}: 🛡️已自动封禁扫描攻击IP: {self.client_ip} {self.location_info}")
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                return False

            # 检查SOCKS版本（扫描检测）
            if data[0] != 0x05:
                logger.warning(f"{self.name}: 客户端({self.client_ip} {self.location_info})握手失败：不支持的SOCKS版本 {data[0]}")
                if self.client_ip and self.security_enabled and self.security_manager:
                    try:
                        # 注意：这里应该是 invalid_version，不是 invalid_method
                        if self.security_manager.record_scan_attempt(self.client_ip, 'invalid_version'):
                            logger.warning(f"{self.name}: 🛡️已自动封禁无效版本攻击IP: {self.client_ip} {self.location_info}")
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                return False

            # 读取方法列表
            nmethods = data[1]
            if nmethods == 0:
                logger.warning(f"{self.name}: 客户端{self.client_ip} {self.location_info}握手失败：未提供认证方法")
                if self.client_ip and self.security_enabled and self.security_manager:
                    try:
                        if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_request'):
                            logger.warning(f"{self.name}: 🛡️已自动封禁扫描攻击IP: {self.client_ip} {self.location_info}")
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                return False

            methods = b''
            while len(methods) < nmethods:
                chunk = client_socket.recv(nmethods - len(methods))
                if not chunk:
                    logger.warning(f"{self.name}: 客户端{self.client_ip} {self.location_info}握手失败：未能接收完整的认证方法列表")
                    if self.client_ip and self.security_enabled and self.security_manager:
                        try:
                            if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_request'):
                                logger.warning(f"{self.name}: 🛡️已自动封禁扫描攻击IP: {self.client_ip}")
                        except Exception as e:
                            logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                    return False
                methods += chunk

            # 根据是否启用认证选择方法
            if self.auth_enabled:
                if 0x02 in methods:  # 用户名密码认证
                    client_socket.sendall(b'\x05\x02')  # 选择用户名密码认证
                    return self.handle_username_password_auth(client_socket)
                else:
                    logger.warning(f"{self.name}: 客户端{self.client_ip} {self.location_info}握手失败：需要用户名密码认证但客户端不支持")
                    client_socket.sendall(b'\x05\xff')  # 无可接受的方法
                    if self.client_ip and self.security_enabled and self.security_manager:
                        try:
                            # 注意：这里应该是 invalid_method
                            if self.security_manager.record_scan_attempt(self.client_ip, 'invalid_method'):
                                logger.warning(f"{self.name}: 🛡️已自动封禁无效方法攻击IP: {self.client_ip} {self.location_info}")
                        except Exception as e:
                            logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                    return False
            else:
                if 0x00 in methods:  # 无认证
                    client_socket.sendall(b'\x05\x00')  # 选择无认证
                    logger.debug(f"{self.name}: 客户端{self.client_ip} {self.location_info}握手成功，无需认证")
                    return True
                else:
                    logger.warning(f"{self.name}: 客户端{self.client_ip} {self.location_info}握手失败：不支持的认证方法 (methods: {list(methods)})")
                    client_socket.sendall(b'\x05\xff')  # 无可接受的方法
                    if self.client_ip and self.security_enabled and self.security_manager:
                        try:
                            # 注意：这里应该是 invalid_method
                            if self.security_manager.record_scan_attempt(self.client_ip, 'invalid_method'):
                                logger.warning(f"{self.name}: 🛡️已自动封禁无效方法攻击IP: {self.client_ip}")
                        except Exception as e:
                            logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")
                    return False

        except Exception as e:
            logger.error(f"{self.name}: 客户端{self.client_ip} {self.location_info}握手失败，错误信息：{e}")

            # 如果安全启用，记录异常握手失败
            if self.client_ip and self.security_enabled and self.security_manager:
                try:
                    if self.security_manager.record_scan_attempt(self.client_ip, 'malformed_request'):
                        logger.warning(f"{self.name}: 🛡️已自动封禁异常握手攻击IP: {self.client_ip}")
                except Exception as e:
                    logger.debug(f"{self.name}: 记录扫描尝试失败: {e}")

            return False

    def handle_username_password_auth(self, client_socket: socket.socket) -> bool:
        """处理用户名密码认证"""
        try:
            # 读取认证版本
            data = client_socket.recv(2)
            if len(data) < 2 or data[0] != 0x01:
                logger.warning(f"{self.name}: 客户端({self.client_ip} {self.location_info})用户认证失败：无效的认证版本")
                client_socket.sendall(b'\x01\x01')  # 认证失败

                # 如果安全启用，记录认证失败
                if self.client_ip and self.security_enabled and self.security_manager:
                    try:
                        self.security_manager.record_auth_failure(self.client_ip, protocol='socks5')
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录认证失败失败: {e}")

                return False

            # 读取用户名长度和用户名
            username_len = data[1]
            username = client_socket.recv(username_len).decode('utf-8')

            # 读取密码长度和密码
            password_len_data = client_socket.recv(1)
            if not password_len_data:
                client_socket.sendall(b'\x01\x01')

                # 如果安全启用，记录认证失败
                if self.client_ip and self.security_enabled and self.security_manager:
                    try:
                        self.security_manager.record_auth_failure(self.client_ip, protocol='socks5')
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录认证失败失败: {e}")

                return False

            password_len = password_len_data[0]
            password = client_socket.recv(password_len).decode('utf-8')

            # 验证用户名和密码
            if self.user_manager and self.user_manager.verify_user_credentials(username, password):
                client_socket.sendall(b'\x01\x00')  # 认证成功
                self.current_user = username
                logger.info(f"{self.name}: ✅用户认证成功 - 客户端: {self.client_ip} {self.location_info} [用户名: {username}]")

                # 安全管理记录认证成功
                if self.security_enabled and self.security_manager and self.client_ip:
                    try:
                        self.security_manager.record_auth_success(self.client_ip)
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录认证成功失败: {e}")

                return True

            else:
                client_socket.sendall(b'\x01\x01')  # 认证失败
                logger.warning(f"{self.name}: ❌用户认证失败 - 客户端: {self.client_ip} {self.location_info} [验证名： {username}, 验证密码：{password}]")

                # 安全管理记录认证失败
                if self.security_enabled and self.security_manager and self.client_ip:
                    try:
                        self.security_manager.record_auth_failure(self.client_ip, protocol='socks5')
                    except Exception as e:
                        logger.debug(f"{self.name}: 记录认证失败失败: {e}")

                return False

        except Exception as e:
            logger.error(f"{self.name}: 用户认证处理失败 - 客户端: {self.client_ip} {self.location_info}: {e}")
            # 异常时也记录安全管理认证失败
            if self.security_enabled and self.security_manager and self.client_ip:
                try:
                    self.security_manager.record_auth_failure(self.client_ip, protocol='socks5')
                except Exception as e:
                    logger.debug(f"{self.name}: 记录认证失败失败: {e}")

            try:
                client_socket.sendall(b'\x01\x01')  # 认证失败
            except:
                pass
            return False


    def recv_all(self, sock: socket.socket, n: int) -> bytes:
        """处理粘包的辅助方法，确保读取 n 字节"""
        data = b''
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError(f"在Socket关闭之前未接收到所有{n}字节数据")
            data += chunk
        return data

    def parse_socks5_request(self, client_socket: socket.socket) -> Tuple[str, int, Optional[str]]:
        """解析SOCKS5请求"""
        try:
            header = self.recv_all(client_socket, 4)
            if len(header) < 4:
                raise ValueError("客户端请求头长度不足4字节")

            ver, cmd, rsv, addr_type = header

            if ver != 0x05:
                raise ValueError("客户端请求SOCKS版本必须为0x05")
            if rsv != 0x00:
                raise ValueError("客户端请求RSV字段必须为0x00")
            if cmd != 0x01:
                raise ValueError("客户端请求只支持CONNECT命令")

            if addr_type == 0x01:  # IPv4
                ip_data = self.recv_all(client_socket, 4)
                target_ip = socket.inet_ntoa(ip_data)
                port_data = self.recv_all(client_socket, 2)
                target_port = struct.unpack('!H', port_data)[0]
                domain = "IP请求"

            elif addr_type == 0x03:  # 域名
                domain_len = self.recv_all(client_socket, 1)[0]
                domain = self.recv_all(client_socket, domain_len).decode()
                port_data = self.recv_all(client_socket, 2)
                target_port = struct.unpack('!H', port_data)[0]

                # DNS解析
                try:
                    target_ip = self.resolve_dns(domain)
                    if not target_ip:
                        raise ValueError(f"{self.name}: resolve_dns方法未解析到dns")

                except Exception as e:
                    logger.error(f"{self.name}: DNS解析失败 {domain}: {e}")
                    raise

            else:
                logger.warning(f"{self.name}: 目标请求解析失败：不支持的地址类型: {addr_type}")
                self.send_socks5_response(client_socket, False)
                raise

            return target_ip, target_port, domain

        except Exception as e:
            logger.error(f"{self.name}: 客户端({self.client_ip} {self.location_info})请求解析失败: {e}")
            raise

    def resolve_dns(self, hostname: str) -> str:
        """
        通过DNS解析器解析域名
        """
        try:

            if self.dns_resolver:
                # 存在dns解析器时，使用dns解析器
                return self.dns_resolver.resolve(hostname, self.egress_ip)
            else:
                # 否则使用默认系统dns解析
                return self.resolve_dns_fallback(hostname)
        except Exception as e:
            logger.error(f"{self.name}: DNS解析失败 {hostname}: {e}")
            raise

    def resolve_dns_fallback(self, hostname: str) -> str:
        """
        备用DNS解析方法：使用系统DNS解析
        """
        try:
            logger.debug(f"{self.name}: 使用系统DNS解析: {hostname}")
            result = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
            if result:
                hostname_ip = result[0][4][0]
                logger.debug(f"{self.name}: 系统DNS解析成功: {hostname} -> {hostname_ip}")
                return str(hostname_ip)
            else:
                raise RuntimeError(f"{self.name}: 系统DNS解析返回空结果")
        except Exception as e:
            logger.error(f"{self.name}: 系统DNS解析失败: {e}")
            raise RuntimeError(f"{self.name}: 系统DNS解析失败: {e}")

    def send_socks5_response(self, client_socket: socket.socket, success: bool = True):
        """发送SOCKS成功或失败响应"""
        try:
            if success:
                response = b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00'
            else:
                response = b'\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00'

            client_socket.sendall(response)
        except Exception as e:
            logger.error(f"{self.name}: 向客户端({self.client_ip})发送SOCKS5响应失败: {e}")

    def forward_data(self, source: socket.socket, destination: socket.socket, connection_id: str) -> Tuple[int, int]:
        """在两个 socket 之间双向转发数据，返回 (发送字节数, 接收字节数)"""
        logger.debug(f"{self.name}: forward_data开始数据转发...")

        total_sent_to_client = 0      # 发送到客户端的流量
        total_received_from_client = 0  # 从客户端接收的流量

        try:
            while True:
                rlist, _, _ = select.select([source, destination], [], [], 60)

                if not rlist:
                    logger.debug(f"{self.name}: forward_data转发过程超时 (60s), 关闭连接。")
                    break

                for sock in rlist:
                    try:
                        data = sock.recv(4096)

                        if not data:
                            logger.debug(f"{self.name}: forward_data转发过程中接收到EOF，连接被对端关闭。")
                            return total_sent_to_client, total_received_from_client

                        if sock is source:
                            # 从客户端接收，发往目标服务器

                            try:
                                destination.sendall(data)

                                # 记录从客户端接收的流量
                                received_from_client_once = len(data)
                                total_received_from_client += received_from_client_once  # 从客户端接收的流量

                                if self.stats_enabled and self.stats_manager:
                                    self.stats_manager.record_traffic(
                                        bytes_sent=0,                    # 没有发送
                                        bytes_received=received_from_client_once,  # 从客户端接收
                                        protocol='socks5',
                                        country=self.location_info,
                                        proxy_name=self.name,
                                        ip=self.client_ip,
                                        user=self.current_user,
                                        connection_id=connection_id,
                                    )


                            except (socket.error, OSError) as e:
                                logger.debug(f"{self.name}: forward_data转发过程中客户端数据未能发送到远程目标: {e}")
                                return total_sent_to_client, total_received_from_client

                        else:
                            try:
                                # 从目标服务器接收，发往客户端
                                source.sendall(data)

                                sent_to_client_once = len(data)
                                total_sent_to_client += sent_to_client_once  # 发送给客户端的流量

                                # 记录发送到客户端的流量
                                if self.stats_enabled and self.stats_manager:
                                    self.stats_manager.record_traffic(
                                        bytes_sent=sent_to_client_once,           # 发送到客户端
                                        bytes_received=0,               # 没有接收
                                        protocol='socks5',
                                        country=self.location_info,
                                        proxy_name=self.name,
                                        ip=self.client_ip,
                                        user=self.current_user,
                                        connection_id=connection_id,
                                    )


                            except (socket.error, OSError) as e:
                                logger.debug(f"{self.name}: forward_data转发过程中远程目标数据未能发送到客户端: {e}")
                                return total_sent_to_client, total_received_from_client

                    except (socket.error, OSError) as e:
                        logger.debug(f"{self.name}: forward_data转发过程中socket错误: {e}")
                        return total_sent_to_client, total_received_from_client

        except Exception as e:
            logger.error(f"{self.name}: 数据转发过程中发生未处理错误: {e}")
            raise
        finally:
            # 确保sockets关闭
            for sock in [source, destination]:
                if sock:
                    try:
                        sock.close()
                    except (OSError, socket.error):
                        pass

        return total_sent_to_client, total_received_from_client

    def start(self):
        """启动SOCKS5代理服务器"""
        if self.running:
            logger.warning(f"{self.name}: SOCKS5代理服务器已经在运行")
            return True

        if self.egress_ip is None or self.egress_port is None:
            logger.error(f"{self.name}: SOCKS5服务器必须提供出口地址和端口 ")
            return False

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.listen_host, self.listen_port))
        self.server_socket.listen(100)

        self.running = True
        status = "有认证 " if self.auth_enabled else "无认证 "
        status += "有安全管理 " if self.security_enabled else "无安全管理 "
        status += "有连接统计 " if self.stats_enabled else "无连接统计 "
        status += f"有proxy_protocol: {self.proxy_protocol}" if self.proxy_protocol else "无proxy_protocol"
        logger.info(f"{self.name}: SOCKS5代理服务器启动，监听地址： {self.listen_host}:{self.listen_port}, 网络出口： {self.egress_ip}:{self.egress_port}，功能状态：{status}")

        try:
            while self.running:
                try:
                    client_socket, client_addr = self.server_socket.accept()
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_addr),
                        daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
                except OSError as e:
                    if self.running:
                        logger.error(f"{self.name}: 监听过程中等待客户端连接时发生错误: {e}")
                        self.stop()
                    break

        except Exception as e:
            logger.error(f"{self.name}: SOCKS5代理服务器运行出错，正在关闭...: {e}")
            self.stop()

    def stop(self):
        """停止代理服务器"""
        logger.info(f"{self.name}: SOCKS5代理服务器正在停止...")
        self.running = False

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info(f"{self.name}: SOCKS5代理服务器已停止")

    def get_config_info(self):
        """获取配置信息"""
        return {
            'name': self.name,
            'listen_host': self.listen_host,
            'listen_port': self.listen_port,
            'egress_ip': self.egress_ip,
            'egress_port': self.egress_port,
            'auth_enabled': self.auth_enabled,
            'proxy_protocol': self.proxy_protocol,
            'security_enabled': self.security_enabled,
            'stats_enabled': self.stats_enabled,
        }

    def get_listen_port(self):
        """获取服务器监听的端口"""
        if self.server_socket:
            return self.server_socket.getsockname()[1]
        return self.listen_port

    # def get_health_status(self) -> bool:
    #     """获取健康状态"""
    #     if self.health_check_mode and hasattr(self, 'health_check_passed'):
    #         return self.health_check_passed
    #     return False
