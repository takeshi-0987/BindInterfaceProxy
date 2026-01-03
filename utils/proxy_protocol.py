# -*- coding: utf-8 -*-
"""
Module: proxy_protocol.py
Author: Takeshi
Date: 2025-11-08

Description:
    Proxy Protocol 接收器和生成器
    1. 接收器：用于解析 frpc 发送的 Proxy Protocol 头，获取真实客户端IP
    2. 生成器：用于生成 Proxy Protocol 头（V1和带扩展的V2）
"""

import socket
import struct
import json
import logging
from typing import Tuple, Optional, Dict, Any, List
from enum import IntEnum

logger = logging.getLogger(__name__)

class PP2Command(IntEnum):
    """Proxy Protocol V2 命令"""
    LOCAL = 0x00
    PROXY = 0x01

class PP2AddressFamily(IntEnum):
    """Proxy Protocol V2 地址族"""
    UNSPEC = 0x00
    INET = 0x01      # IPv4
    INET6 = 0x02     # IPv6
    UNIX = 0x03      # Unix socket

class PP2TransportProtocol(IntEnum):
    """Proxy Protocol V2 传输协议"""
    UNSPEC = 0x00
    STREAM = 0x01    # TCP
    DGRAM = 0x02     # UDP

class PP2TLVType(IntEnum):
    """Proxy Protocol V2 TLV 类型 (标准+自定义)"""
    # 标准类型 (0x00-0x1F)
    PP2_TYPE_ALPN = 0x01
    PP2_TYPE_AUTHORITY = 0x02
    PP2_TYPE_CRC32C = 0x03
    PP2_TYPE_NOOP = 0x04
    PP2_TYPE_SSL = 0x20

    # HAProxy 扩展类型 (0x20-0x2F)
    PP2_TYPE_NETNS = 0x30

    # 自定义类型 (0xE0-0xEF)
    PP2_TYPE_CUSTOM_GEO = 0xE0      # 地理位置信息
    PP2_TYPE_CUSTOM_USER = 0xE1     # 用户信息
    PP2_TYPE_CUSTOM_TIMESTAMP = 0xE2 # 时间戳
    PP2_TYPE_CUSTOM_SESSION = 0xE3   # 会话ID
    PP2_TYPE_CUSTOM_UA = 0xE4       # User-Agent
    PP2_TYPE_CUSTOM_HTTP_METHOD = 0xE5 # HTTP方法

class ProxyProtocolReceiver:
    """Proxy Protocol 接收器"""

    @staticmethod
    def parse_v1_header(data: bytes) -> Optional[Dict]:
        """解析 Proxy Protocol v1 头"""
        try:
            header_str = data.decode('ascii', errors='ignore')
            if not header_str.startswith('PROXY '):
                return None

            parts = header_str.strip().split()
            if len(parts) < 6:
                return None

            protocol = parts[1]  # TCP4, TCP6, UNKNOWN
            if protocol == 'UNKNOWN':
                return {
                    'version': 'v1',
                    'protocol': 'UNKNOWN',
                    'header_length': len(data)
                }

            client_ip = parts[2]
            server_ip = parts[3]
            client_port = int(parts[4])
            server_port = int(parts[5])

            return {
                'version': 'v1',
                'protocol': protocol,
                'client_ip': client_ip,
                'client_port': client_port,
                'server_ip': server_ip,
                'server_port': server_port,
                'header_length': len(data)
            }
        except Exception as e:
            logger.error(f"解析 PROXY 协议 v1 头时出错: {e}")
            return None

    @staticmethod
    def parse_v2_header(data: bytes) -> Optional[Dict]:
        """解析完整的 Proxy Protocol v2 头（必须 >=16 字节）"""
        try:
            if len(data) < 16:
                return None

            signature = b"\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A"
            if data[:12] != signature:
                return None

            version_command = data[12]
            version = version_command >> 4
            command = version_command & 0x0F

            if version != 2:
                return None

            family_protocol = data[13]
            address_family = family_protocol >> 4
            protocol = family_protocol & 0x0F

            data_length = struct.unpack("!H", data[14:16])[0]

            # 验证总长度是否匹配
            if len(data) != 16 + data_length:
                logger.warning("PROXY v2 头长度不匹配: 预期 %d, 实际 %d",
                               16 + data_length, len(data))
                return None

            result = {
                'version': 'v2',
                'command': 'LOCAL' if command == 0x00 else 'PROXY',
                'address_family': address_family,
                'transport_protocol': protocol,
                'header_length': 16 + data_length,
                'tlvs': {}
            }

            if command == 0x01:  # PROXY
                if address_family == 0x01 and protocol == 0x01:  # TCP/IPv4
                    if data_length < 12:
                        return None

                    client_ip = socket.inet_ntop(socket.AF_INET, data[16:20])
                    server_ip = socket.inet_ntop(socket.AF_INET, data[20:24])
                    client_port = struct.unpack("!H", data[24:26])[0]
                    server_port = struct.unpack("!H", data[26:28])[0]

                    result.update({
                        'protocol': 'TCP4',
                        'client_ip': client_ip,
                        'client_port': client_port,
                        'server_ip': server_ip,
                        'server_port': server_port,
                    })

                    # 解析TLV
                    if data_length > 12:
                        tlv_data = data[28:28 + (data_length - 12)]
                        result['tlvs'] = ProxyProtocolGenerator.parse_tlv_data(tlv_data)

                elif address_family == 0x02 and protocol == 0x01:  # TCP/IPv6
                    if data_length < 36:
                        return None

                    client_ip = socket.inet_ntop(socket.AF_INET6, data[16:32])
                    server_ip = socket.inet_ntop(socket.AF_INET6, data[32:48])
                    client_port = struct.unpack("!H", data[48:50])[0]
                    server_port = struct.unpack("!H", data[50:52])[0]

                    result.update({
                        'protocol': 'TCP6',
                        'client_ip': client_ip,
                        'client_port': client_port,
                        'server_ip': server_ip,
                        'server_port': server_port,
                    })

                    # 解析TLV
                    if data_length > 36:
                        tlv_data = data[52:52 + (data_length - 36)]
                        result['tlvs'] = ProxyProtocolGenerator.parse_tlv_data(tlv_data)

            return result

        except Exception as e:
            logger.error(f"解析 PROXY 协议 v2 头时出错: {e}")
            return None

    @staticmethod
    def receive_and_parse(client_sock, proxy_protocol_version: Optional[str]) -> Tuple[Optional[Dict], bytes]:
        """接收并解析 Proxy Protocol 头"""
        if not proxy_protocol_version:
            return None, b""

        original_timeout = client_sock.gettimeout()
        try:
            client_sock.settimeout(2.0)

            if proxy_protocol_version == 'v1':
                data = b""
                while b"\r\n" not in data:
                    chunk = client_sock.recv(1)
                    if not chunk:
                        return None, b""
                    data += chunk
                    if len(data) > 108:  # PROXY v1 最大 108 字节
                        return None, b""

                result = ProxyProtocolReceiver.parse_v1_header(data)
                return result, data if result else b""

            elif proxy_protocol_version == 'v2':
                # 读取前 16 字节
                header_16 = b""
                while len(header_16) < 16:
                    chunk = client_sock.recv(16 - len(header_16))
                    if not chunk:
                        return None, b""
                    header_16 += chunk

                signature = b"\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A"
                if header_16[:12] != signature:
                    return None, b""

                data_length = struct.unpack("!H", header_16[14:16])[0]
                total_length = 16 + data_length

                if data_length > 255:
                    logger.warning("PROXY v2 数据过长: %d", data_length)
                    return None, b""

                remaining = b""
                to_read = data_length
                while to_read > 0:
                    chunk = client_sock.recv(to_read)
                    if not chunk:
                        return None, b""
                    remaining += chunk
                    to_read -= len(chunk)

                full_data = header_16 + remaining
                result = ProxyProtocolReceiver.parse_v2_header(full_data)
                return result, full_data if result else b""

            else:
                return None, b""

        except socket.timeout:
            logger.debug("接收 PROXY 协议头时超时")
            return None, b""
        except Exception as e:
            logger.error(f"接收 PROXY 协议头时出错: {e}")
            return None, b""
        finally:
            try:
                client_sock.settimeout(original_timeout)
            except OSError:
                pass


class ProxyProtocolGenerator:
    """Proxy Protocol 生成器"""

    # V2 签名
    PP2_SIGNATURE = b"\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A"

    @staticmethod
    def build_v1_header(
        src_ip: str,
        dst_ip: str,
        src_port: int = 0,
        dst_port: int = 0,
        protocol: str = "TCP4"
    ) -> bytes:
        """
        构建 Proxy Protocol v1 头

        Args:
            src_ip: 源IP地址
            dst_ip: 目标IP地址
            src_port: 源端口
            dst_port: 目标端口
            protocol: 协议类型 (TCP4, TCP6, UNKNOWN)

        Returns:
            bytes: V1头数据
        """
        if protocol == "UNKNOWN":
            return b"PROXY UNKNOWN\r\n"

        if protocol not in ["TCP4", "TCP6"]:
            raise ValueError(f"不支持的协议类型: {protocol}")

        # 验证IP地址格式
        try:
            if protocol == "TCP4":
                socket.inet_pton(socket.AF_INET, src_ip)
                socket.inet_pton(socket.AF_INET, dst_ip)
            else:  # TCP6
                socket.inet_pton(socket.AF_INET6, src_ip)
                socket.inet_pton(socket.AF_INET6, dst_ip)
        except socket.error:
            raise ValueError(f"无效的{protocol}地址: {src_ip} -> {dst_ip}")

        # 验证端口
        if not (0 <= src_port <= 65535):
            raise ValueError(f"无效的源端口: {src_port}")
        if not (0 <= dst_port <= 65535):
            raise ValueError(f"无效的目标端口: {dst_port}")

        # 构建V1头
        header = f"PROXY {protocol} {src_ip} {dst_ip} {src_port} {dst_port}\r\n"
        return header.encode('ascii')

    @staticmethod
    def build_v2_header(
        command: PP2Command = PP2Command.PROXY,
        src_ip: str = "0.0.0.0",
        dst_ip: str = "0.0.0.0",
        src_port: int = 0,
        dst_port: int = 0,
        address_family: PP2AddressFamily = PP2AddressFamily.INET,
        transport_protocol: PP2TransportProtocol = PP2TransportProtocol.STREAM,
        tlvs: Optional[List[Dict]] = None
    ) -> bytes:
        """
        构建 Proxy Protocol v2 头（带TLV扩展）

        Args:
            command: 命令 (LOCAL/PROXY)
            src_ip: 源IP地址
            dst_ip: 目标IP地址
            src_port: 源端口
            dst_port: 目标端口
            address_family: 地址族 (INET/INET6/UNIX)
            transport_protocol: 传输协议 (STREAM/DGRAM)
            tlvs: TLV扩展列表

        Returns:
            bytes: V2头数据
        """
        # 验证IP地址
        try:
            if address_family == PP2AddressFamily.INET:
                src_addr = socket.inet_pton(socket.AF_INET, src_ip)
                dst_addr = socket.inet_pton(socket.AF_INET, dst_ip)
                addr_data_len = 12  # 4+4+2+2
            elif address_family == PP2AddressFamily.INET6:
                src_addr = socket.inet_pton(socket.AF_INET6, src_ip)
                dst_addr = socket.inet_pton(socket.AF_INET6, dst_ip)
                addr_data_len = 36  # 16+16+2+2
            elif address_family == PP2AddressFamily.UNIX:
                # UNIX socket地址（108字节）
                src_addr = src_ip.encode('ascii').ljust(108, b'\x00')
                dst_addr = dst_ip.encode('ascii').ljust(108, b'\x00')
                addr_data_len = 216  # 108+108
            else:
                raise ValueError(f"不支持的地址族: {address_family}")
        except socket.error:
            raise ValueError(f"无效的IP地址: {src_ip} -> {dst_ip}")

        # 验证端口
        if not (0 <= src_port <= 65535):
            raise ValueError(f"无效的源端口: {src_port}")
        if not (0 <= dst_port <= 65535):
            raise ValueError(f"无效的目标端口: {dst_port}")

        # 构建TLV数据
        tlv_data = b""
        if tlvs:
            for tlv in tlvs:
                tlv_bytes = ProxyProtocolGenerator.build_tlv(
                    tlv_type=tlv.get('type'),
                    tlv_value=tlv.get('value')
                )
                tlv_data += tlv_bytes

        # 计算总长度
        total_length = addr_data_len + len(tlv_data)

        # 构建头部
        header = ProxyProtocolGenerator.PP2_SIGNATURE

        # 版本(2) + 命令
        version_command = (2 << 4) | command.value
        header += struct.pack("B", version_command)

        # 地址族 + 传输协议
        family_protocol = (address_family.value << 4) | transport_protocol.value
        header += struct.pack("B", family_protocol)

        # 数据长度
        header += struct.pack("!H", total_length)

        # 地址数据
        if address_family in [PP2AddressFamily.INET, PP2AddressFamily.INET6]:
            header += src_addr + dst_addr
            header += struct.pack("!H", src_port)
            header += struct.pack("!H", dst_port)
        elif address_family == PP2AddressFamily.UNIX:
            header += src_addr + dst_addr

        # TLV数据
        header += tlv_data

        return header

    @staticmethod
    def build_tlv(tlv_type: int, tlv_value: Any) -> bytes:
        """
        构建单个TLV

        Args:
            tlv_type: TLV类型 (0x00-0xFF)
            tlv_value: TLV值，可以是字符串、字节、字典等

        Returns:
            bytes: TLV数据
        """
        if not (0 <= tlv_type <= 255):
            raise ValueError(f"TLV类型必须在0-255之间: {tlv_type}")

        # 根据类型处理值
        if isinstance(tlv_value, str):
            value_bytes = tlv_value.encode('utf-8')
        elif isinstance(tlv_value, dict):
            value_bytes = json.dumps(tlv_value, ensure_ascii=False).encode('utf-8')
        elif isinstance(tlv_value, int):
            value_bytes = struct.pack("!I", tlv_value)  # 32位整数
        elif isinstance(tlv_value, float):
            value_bytes = struct.pack("!d", tlv_value)  # 双精度浮点数
        elif isinstance(tlv_value, bytes):
            value_bytes = tlv_value
        else:
            value_bytes = str(tlv_value).encode('utf-8')

        # 构建TLV
        tlv = struct.pack("B", tlv_type)  # 类型
        tlv += struct.pack("!H", len(value_bytes))  # 长度
        tlv += value_bytes  # 值

        return tlv

    @staticmethod
    def parse_tlv_data(tlv_data: bytes) -> Dict[int, Any]:
        """
        解析TLV数据

        Args:
            tlv_data: 原始TLV数据

        Returns:
            Dict: 解析后的TLV字典
        """
        result = {}
        idx = 0

        while idx < len(tlv_data):
            if idx + 3 > len(tlv_data):  # 至少需要类型+长度
                break

            tlv_type = tlv_data[idx]
            tlv_length = struct.unpack("!H", tlv_data[idx+1:idx+3])[0]

            if idx + 3 + tlv_length > len(tlv_data):
                break

            tlv_value = tlv_data[idx+3:idx+3+tlv_length]

            # 根据类型解析值
            parsed_value = ProxyProtocolGenerator._parse_tlv_value(tlv_type, tlv_value)
            result[tlv_type] = parsed_value

            idx += 3 + tlv_length

        return result

    @staticmethod
    def _parse_tlv_value(tlv_type: int, tlv_value: bytes) -> Any:
        """根据TLV类型解析值"""
        try:
            # 自定义类型
            if tlv_type == PP2TLVType.PP2_TYPE_CUSTOM_GEO:
                return json.loads(tlv_value.decode('utf-8'))
            elif tlv_type == PP2TLVType.PP2_TYPE_CUSTOM_USER:
                return tlv_value.decode('utf-8')
            elif tlv_type == PP2TLVType.PP2_TYPE_CUSTOM_TIMESTAMP:
                return float(tlv_value.decode('utf-8'))
            elif tlv_type == PP2TLVType.PP2_TYPE_CUSTOM_SESSION:
                return tlv_value.decode('utf-8')
            elif tlv_type == PP2TLVType.PP2_TYPE_CUSTOM_UA:
                return tlv_value.decode('utf-8')
            elif tlv_type == PP2TLVType.PP2_TYPE_CUSTOM_HTTP_METHOD:
                return tlv_value.decode('utf-8')

            # 标准类型
            elif tlv_type == PP2TLVType.PP2_TYPE_ALPN:
                return tlv_value.decode('ascii')
            elif tlv_type == PP2TLVType.PP2_TYPE_AUTHORITY:
                return tlv_value.decode('ascii')
            elif tlv_type == PP2TLVType.PP2_TYPE_CRC32C:
                return struct.unpack("!I", tlv_value)[0] if len(tlv_value) == 4 else tlv_value.hex()

            # 默认返回字节或字符串
            try:
                return tlv_value.decode('utf-8')
            except UnicodeDecodeError:
                return tlv_value.hex()

        except Exception:
            return tlv_value.hex()  # 解析失败返回十六进制

    @staticmethod
    def build_enhanced_v2_header(
        src_ip: str,
        dst_ip: str,
        src_port: int = 0,
        dst_port: int = 0,
        geo_info: Optional[Dict] = None,
        user_info: Optional[Dict] = None,
        timestamp: Optional[float] = None,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        http_method: Optional[str] = None
    ) -> bytes:
        """
        构建增强的V2头（包含常用自定义TLV）

        Args:
            src_ip: 源IP地址
            dst_ip: 目标IP地址
            src_port: 源端口
            dst_port: 目标端口
            geo_info: 地理位置信息字典
            user_info: 用户信息字典
            timestamp: 时间戳
            session_id: 会话ID
            user_agent: User-Agent
            http_method: HTTP方法

        Returns:
            bytes: 增强的V2头
        """
        tlvs = []

        # 添加地理位置TLV
        if geo_info:
            tlvs.append({
                'type': PP2TLVType.PP2_TYPE_CUSTOM_GEO,
                'value': geo_info
            })

        # 添加用户信息TLV
        if user_info:
            tlvs.append({
                'type': PP2TLVType.PP2_TYPE_CUSTOM_USER,
                'value': user_info
            })

        # 添加时间戳TLV
        if timestamp is None:
            import time
            timestamp = time.time()
        tlvs.append({
            'type': PP2TLVType.PP2_TYPE_CUSTOM_TIMESTAMP,
            'value': str(timestamp)
        })

        # 添加会话ID TLV
        if session_id:
            tlvs.append({
                'type': PP2TLVType.PP2_TYPE_CUSTOM_SESSION,
                'value': session_id
            })

        # 添加User-Agent TLV
        if user_agent:
            tlvs.append({
                'type': PP2TLVType.PP2_TYPE_CUSTOM_UA,
                'value': user_agent
            })

        # 添加HTTP方法TLV
        if http_method:
            tlvs.append({
                'type': PP2TLVType.PP2_TYPE_CUSTOM_HTTP_METHOD,
                'value': http_method
            })

        # 构建V2头
        return ProxyProtocolGenerator.build_v2_header(
            command=PP2Command.PROXY,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            address_family=PP2AddressFamily.INET,
            transport_protocol=PP2TransportProtocol.STREAM,
            tlvs=tlvs
        )


# 使用示例
if __name__ == "__main__":
    # 示例1: 生成V1头
    v1_header = ProxyProtocolGenerator.build_v1_header(
        src_ip="192.168.1.100",
        dst_ip="10.0.0.1",
        src_port=12345,
        dst_port=443
    )
    print(f"V1 Header: {v1_header.decode('ascii')}")

    # 示例2: 生成V2头
    v2_header = ProxyProtocolGenerator.build_v2_header(
        src_ip="192.168.1.100",
        dst_ip="10.0.0.1",
        src_port=12345,
        dst_port=443
    )
    print(f"V2 Header length: {len(v2_header)} bytes")
    print(f"V2 Header hex: {v2_header.hex()}")

    # 示例3: 生成增强的V2头
    enhanced_v2_header = ProxyProtocolGenerator.build_enhanced_v2_header(
        src_ip="192.168.1.100",
        dst_ip="10.0.0.1",
        src_port=12345,
        dst_port=443,
        geo_info={"country": "China", "city": "Beijing", "isp": "China Telecom"},
        user_info={"username": "takeshi", "role": "admin"},
        session_id="abc123def456",
        user_agent="Mozilla/5.0",
        http_method="GET"
    )
    print(f"Enhanced V2 Header length: {len(enhanced_v2_header)} bytes")

    # 示例4: 解析V2头
    parsed = ProxyProtocolReceiver.parse_v2_header(enhanced_v2_header)
    if parsed:
        print(f"Parsed client IP: {parsed.get('client_ip')}")
        print(f"TLVs: {json.dumps(parsed.get('tlvs'), ensure_ascii=False, indent=2)}")
