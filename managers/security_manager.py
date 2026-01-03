# -*- coding: utf-8 -*-
"""
Module: security_manager.py
Author: Takeshi
Date: 2025-11-25

Description:
    安全管理器
"""

import ipaddress
import json
import logging
import time
import threading
import csv
import os
from datetime import datetime
from typing import Set, Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

from defaults.security_default import SecurityConfig

logger = logging.getLogger(__name__)


class ScanType(Enum):
    """扫描类型枚举"""
    INVALID_VERSION = "invalid_version"
    INVALID_METHOD = "invalid_method"
    RAPID_CONNECTIONS = "rapid_connections"
    MALFORMED_REQUEST = "malformed_request"
    AUTH_FAILURE = "auth_failure"
    INVALID_HTTP_METHOD = "invalid_http_method"
    MALFORMED_CONNECT = "malformed_connect"
    INVALID_PORT = "invalid_port"
    SUSPICIOUS_HEADERS = "suspicious_headers"


@dataclass
class IPEntry:
    """IP条目数据类"""
    ip: str
    remark: str = ""
    created_at: str = ""
    created_by: str = ""  # 格式: source:method:identifier
    protocol: str = ""    # 记录封禁来源协议


class OperationSource:
    """操作来源定义"""
    # 来源类型
    SYSTEM = "system"
    USER = "user"
    CLI = "cli"
    IMPORT = "import"
    MIGRATION = "migration"

    # 操作方法
    AUTO = "auto"
    MANUAL = "manual"
    COMMAND = "command"

    # 具体原因/标识
    AUTH_FAILURE = "auth_failure"
    ADMIN = "admin"
    BATCH_IMPORT = "batch_import"
    SCAN_DETECTION = "scan_detection"

    @classmethod
    def format_created_by(cls, source: str, method: str, identifier: str = "") -> str:
        """格式化 created_by 字段"""
        parts = [source, method]
        if identifier:
            parts.append(identifier)
        return ":".join(parts)

    @classmethod
    def parse_created_by(cls, created_by: str) -> dict:
        """解析 created_by 字段"""
        parts = created_by.split(":")
        if len(parts) >= 2:
            return {
                "source": parts[0],
                "method": parts[1],
                "identifier": parts[2] if len(parts) > 2 else ""
            }
        return {"source": created_by, "method": "", "identifier": ""}

    @classmethod
    def get_display_name(cls, created_by: str) -> str:
        """获取用于显示的操作来源名称"""
        parsed = cls.parse_created_by(created_by)

        source_map = {
            cls.SYSTEM: "系统",
            cls.USER: "用户",
            cls.CLI: "命令行",
            cls.IMPORT: "导入",
            cls.MIGRATION: "迁移"
        }

        method_map = {
            cls.AUTO: "自动",
            cls.MANUAL: "手动",
            cls.COMMAND: "命令"
        }

        source_name = source_map.get(parsed["source"], parsed["source"])
        method_name = method_map.get(parsed["method"], parsed["method"])

        if parsed["identifier"]:
            if parsed["source"] == cls.SYSTEM and parsed["method"] == cls.AUTO:
                reason_map = {
                    cls.AUTH_FAILURE: "认证失败",
                    cls.SCAN_DETECTION: "扫描检测",
                    "rate_limit": "速率限制"
                }
                reason = reason_map.get(parsed["identifier"], parsed["identifier"])
                return f"系统自动 ({reason})"
            elif parsed["identifier"] == cls.ADMIN:
                # 用户手动操作不显示额外标识
                if parsed["source"] == cls.USER and parsed["method"] == cls.MANUAL:
                    return "用户手动"
                else:
                    # 暂不显示ADMIN标识符
                    return f"{source_name}{method_name}"
            else:
                # 用户手动操作不显示额外标识
                if parsed["source"] == cls.USER and parsed["method"] == cls.MANUAL:
                    return "用户手动"
                else:
                    return f"{source_name}{method_name} ({parsed['identifier']})"
        else:
            # 用户手动操作不显示额外标识
            if parsed["source"] == cls.USER and parsed["method"] == cls.MANUAL:
                return "用户手动"
            else:
                return f"{source_name}{method_name}"


class IPSegment:
    """IP段管理类"""

    def __init__(self):
        self.single_ips: Set[str] = set()
        self.cidr_networks: List[ipaddress.IPv4Network] = []
        self.ip_ranges: List[Tuple[ipaddress.IPv4Address, ipaddress.IPv4Address]] = []

    def add_ip(self, ip_spec: str) -> bool:
        """添加IP或IP段"""
        ip_spec = ip_spec.strip()

        if not ip_spec or ip_spec.startswith('#'):
            return False

        try:
            # CIDR格式
            if '/' in ip_spec:
                network = ipaddress.IPv4Network(ip_spec, strict=False)
                self.cidr_networks.append(network)
                return True

            # IP范围格式
            elif '-' in ip_spec:
                parts = ip_spec.split('-')
                if len(parts) == 2:
                    start_ip = ipaddress.IPv4Address(parts[0].strip())
                    end_ip = ipaddress.IPv4Address(parts[1].strip())
                    if start_ip <= end_ip:
                        self.ip_ranges.append((start_ip, end_ip))
                        return True
                    else:
                        logger.error(f"IP范围无效: {ip_spec} (起始IP大于结束IP)")
                        return False
                else:
                    logger.error(f"IP范围格式错误: {ip_spec}")
                    return False

            # 单个IP地址
            else:
                ip = ipaddress.IPv4Address(ip_spec)
                self.single_ips.add(str(ip))
                return True

        except (ipaddress.AddressValueError, ValueError) as e:
            logger.error(f"IP格式无效: {ip_spec} - {e}")
            return False

    def contains(self, ip: str) -> bool:
        """检查IP是否在段内"""
        try:
            target_ip = ipaddress.IPv4Address(ip)

            # 检查单个IP
            if ip in self.single_ips:
                return True

            # 检查CIDR网络
            for network in self.cidr_networks:
                if target_ip in network:
                    return True

            # 检查IP范围
            for start_ip, end_ip in self.ip_ranges:
                if start_ip <= target_ip <= end_ip:
                    return True

            return False

        except ipaddress.AddressValueError:
            return False

    def remove_entry(self, ip_spec: str) -> bool:
        """移除指定的IP或IP段"""
        ip_spec = ip_spec.strip()

        try:
            # CIDR格式
            if '/' in ip_spec:
                network = ipaddress.IPv4Network(ip_spec, strict=False)
                if network in self.cidr_networks:
                    self.cidr_networks.remove(network)
                    return True

            # IP范围格式
            elif '-' in ip_spec:
                parts = ip_spec.split('-')
                if len(parts) == 2:
                    start_ip = ipaddress.IPv4Address(parts[0].strip())
                    end_ip = ipaddress.IPv4Address(parts[1].strip())

                    for i, (range_start, range_end) in enumerate(self.ip_ranges):
                        if range_start == start_ip and range_end == end_ip:
                            self.ip_ranges.pop(i)
                            return True

            # 单个IP地址
            else:
                ip = ipaddress.IPv4Address(ip_spec)
                ip_str = str(ip)
                if ip_str in self.single_ips:
                    self.single_ips.remove(ip_str)
                    return True

            return False

        except (ipaddress.AddressValueError, ValueError):
            return False

    def get_all_entries(self) -> List[str]:
        """获取所有条目的字符串表示"""
        entries = []
        entries.extend(sorted(self.single_ips))
        entries.extend(str(network) for network in self.cidr_networks)
        entries.extend(f"{start}-{end}" for start, end in self.ip_ranges)
        return entries


# ========== 安全管理器主类 ==========

class SecurityManager:
    """代理服务器安全管理器"""

    def __init__(self, config: SecurityConfig):
        """
        初始化安全管理器

        Args:
            config: 安全管理器配置
        """
        self.config = config

        # 文件路径
        self.blacklist_file = Path(self.config.core.blacklist_file)
        self.whitelist_file = Path(self.config.core.whitelist_file)
        self.ban_history_file = Path(self.config.core.ban_history_file)
        self.active_bans_file = Path("data/.active_bans.json")    # 临时的活跃封禁文件，读取后删除

        # 确保目录存在
        for file_path in [self.blacklist_file, self.whitelist_file,
                        self.active_bans_file, self.ban_history_file]:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据结构
        self.blacklist = IPSegment()
        self.whitelist = IPSegment()
        self.blacklist_entries: Dict[str, IPEntry] = {}
        self.whitelist_entries: Dict[str, IPEntry] = {}

        # 临时封禁相关
        self.failed_attempts: Dict[str, int] = {}
        self.temp_bans: Dict[str, Dict] = {}
        self.ban_history: List[Dict] = []

        # 扫描防护相关
        self.scan_attempts: Dict[str, Dict] = {}
        self.connection_timestamps: Dict[str, List[float]] = {}
        self._last_scan_cleanup = time.time()

        # 扫描类型映射
        self.scan_type_names = {
            ScanType.INVALID_VERSION.value: '无效SOCKS版本',
            ScanType.INVALID_METHOD.value: '无效认证方法',
            ScanType.RAPID_CONNECTIONS.value: '快速连续连接',
            ScanType.MALFORMED_REQUEST.value: '畸形请求',
            ScanType.AUTH_FAILURE.value: '认证失败',
            ScanType.INVALID_HTTP_METHOD.value: '无效HTTP方法',
            ScanType.MALFORMED_CONNECT.value: '畸形CONNECT请求',
            ScanType.INVALID_PORT.value: '无效端口号',
            ScanType.SUSPICIOUS_HEADERS.value: '可疑HTTP头',
        }

        # 锁和线程
        self._lock = threading.RLock()
        self._scan_lock = threading.RLock()
        self._cleanup_thread = None
        self._running = False
        self._stop_event = threading.Event()

        # 初始化
        self._ensure_files_exist()
        self._load_lists()
        self._load_active_bans()
        self._load_ban_history()
        self._start_cleanup_thread()

    # ========== 核心功能 ==========

    def is_ip_allowed(self, ip: str) -> bool:
        """检查IP是否允许访问"""
        with self._lock:
            current_time = time.time()

            # 1. 检查临时封禁
            if ip in self.temp_bans:
                unban_time = self.temp_bans[ip].get('unban_time', 0)
                if current_time < unban_time:
                    return False
                else:
                    self._cleanup_expired_bans()

            # 2. 白名单检查（最高优先级）
            if self.whitelist.contains(ip):
                return True

            # 3. 黑名单检查
            if self.blacklist.contains(ip):
                return False

            # 4. 根据模式决定
            if self.config.core.mode == 'whitelist':
                return False
            else:
                return True

    def get_security_status(self, ip: str) -> Dict:
        """获取IP的安全状态"""
        with self._lock:
            current_time = time.time()

            # 检查临时封禁
            is_banned = False
            unban_time = 0
            ban_info = None

            if ip in self.temp_bans:
                ban_info = self.temp_bans[ip]
                unban_time = ban_info.get('unban_time', 0)
                is_banned = current_time < unban_time

            # 获取扫描信息
            scan_info = self._get_scan_attempts_info(ip)

            return {
                'ip': ip,
                'in_whitelist': self.whitelist.contains(ip),
                'in_blacklist': self.blacklist.contains(ip),
                'failed_attempts': self.failed_attempts.get(ip, 0),
                'temp_banned': is_banned,
                'unban_time': unban_time,
                'remaining_seconds': int(unban_time - current_time) if is_banned else 0,
                'unban_time_human': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(unban_time)) if is_banned else None,
                'ban_remark': ban_info.get('remark', '') if ban_info else '',
                'ban_protocol': ban_info.get('protocol', '') if ban_info else '',
                'scan_attempts': scan_info.get('count', 0),
                'scan_types': list(scan_info.get('scan_types', [])),
                'last_scan_attempt': scan_info.get('last_attempt', 0)
            }

    def record_auth_failure(self, ip: str, protocol: str = 'http'):
        """记录认证失败"""
        with self._lock:
            # 检查认证失败检测是否启用
            if not self.config.auth_failure_detection.enabled:
                return

            # 获取该协议的认证设置
            if protocol.lower() in ['http', 'https']:
                max_failures = self.config.auth_failure_detection.http_max_failures
                ban_duration = self.config.auth_failure_detection.http_ban_duration
            else:  # socks协议
                max_failures = self.config.auth_failure_detection.socks_max_failures
                ban_duration = self.config.auth_failure_detection.socks_ban_duration

            # 记录失败次数
            self.failed_attempts[ip] = self.failed_attempts.get(ip, 0) + 1
            failures = self.failed_attempts[ip]

            logger.warning(f"IP {ip} ({protocol}) 认证失败次数: {failures}/{max_failures}")

            # 达到失败次数上限，自动封禁
            if failures >= max_failures:
                remark = f"{protocol.upper()}认证失败超过限制"
                created_by = OperationSource.format_created_by(
                    OperationSource.SYSTEM,
                    OperationSource.AUTO,
                    OperationSource.AUTH_FAILURE
                )
                self._add_temp_ban(ip, remark, created_by, ban_duration, protocol)

    def record_auth_success(self, ip: str):
        """记录认证成功，重置失败计数"""
        with self._lock:
            if ip in self.failed_attempts:
                del self.failed_attempts[ip]
                logger.debug(f"IP {ip} 认证成功，重置失败计数")

    def record_connection(self, ip: str, protocol: str = 'http') -> bool:
        """记录连接时间，返回是否触发了封禁"""
        with self._scan_lock:
            # 检查快速连接检测是否启用
            if not self.config.advanced.rapid_connection_detection.enabled:
                return False

            current_time = time.time()

            # 获取该协议的快速连接设置
            if protocol.lower() in ['http', 'https']:
                threshold = self.config.advanced.rapid_connection_detection.http_threshold
                window = self.config.advanced.rapid_connection_detection.http_window
            else:  # socks协议
                threshold = self.config.advanced.rapid_connection_detection.socks_threshold
                window = self.config.advanced.rapid_connection_detection.socks_window

            # 初始化时间戳列表
            if ip not in self.connection_timestamps:
                self.connection_timestamps[ip] = []

            # 添加当前时间戳
            self.connection_timestamps[ip].append(current_time)

            # 只保留时间窗口内的记录
            self.connection_timestamps[ip] = [
                ts for ts in self.connection_timestamps[ip]
                if current_time - ts <= window
            ]

            # 检查是否超过阈值
            if len(self.connection_timestamps[ip]) >= threshold:
                return self.record_scan_attempt(ip, ScanType.RAPID_CONNECTIONS.value)

            return False

    # ========== 扫描防护功能 ==========

    def record_scan_attempt(self, ip: str, scan_type: str) -> bool:
        """记录扫描尝试"""
        with self._scan_lock:
            # 检查扫描防护是否启用
            if not self.config.advanced.enable_scan_protection:
                return False

            # 检查是否启用该类型的扫描检测
            if not self._is_detection_enabled(scan_type):
                return False

            current_time = time.time()

            # 清理旧的扫描记录
            if current_time - self._last_scan_cleanup > self.config.advanced.scan_cleanup_interval:
                self._cleanup_old_scan_records()
                self._last_scan_cleanup = current_time

            # 初始化IP记录
            if ip not in self.scan_attempts:
                self.scan_attempts[ip] = {
                    'count': 0,
                    'last_attempt': 0,
                    'scan_types': set(),
                    'attempts': []
                }

            # 记录扫描尝试
            self.scan_attempts[ip]['count'] += 1
            self.scan_attempts[ip]['last_attempt'] = current_time
            self.scan_attempts[ip]['scan_types'].add(scan_type)
            self.scan_attempts[ip]['attempts'].append({
                'time': current_time,
                'type': scan_type
            })

            # 检查是否超过阈值
            if self.scan_attempts[ip]['count'] >= self.config.advanced.max_scan_attempts:
                return self._trigger_scan_ban(ip, scan_type)

            return False

    def _is_detection_enabled(self, detection_type: str) -> bool:
        """检查特定检测是否启用"""
        detection_map = {
            ScanType.INVALID_VERSION.value: self.config.advanced.enable_invalid_version_detection,
            ScanType.INVALID_METHOD.value: self.config.advanced.enable_invalid_method_detection,
            ScanType.RAPID_CONNECTIONS.value: self.config.advanced.rapid_connection_detection.enabled,
            ScanType.MALFORMED_REQUEST.value: self.config.advanced.enable_malformed_request_detection,
            ScanType.INVALID_HTTP_METHOD.value: self.config.advanced.enable_invalid_http_method_detection,
            ScanType.MALFORMED_CONNECT.value: self.config.advanced.enable_malformed_connect_detection,
            ScanType.INVALID_PORT.value: self.config.advanced.enable_invalid_port_detection,
            ScanType.SUSPICIOUS_HEADERS.value: self.config.advanced.enable_suspicious_headers_detection,
        }

        return detection_map.get(detection_type, False)

    def _trigger_scan_ban(self, ip: str, scan_type: str) -> bool:
        """触发扫描封禁"""
        # 获取封禁时长
        ban_duration = self.config.advanced.scan_ban_duration

        # 获取扫描类型描述
        scan_description = self.scan_type_names.get(scan_type, scan_type)

        # 格式化操作来源
        created_by = OperationSource.format_created_by(
            OperationSource.SYSTEM,
            OperationSource.AUTO,
            OperationSource.SCAN_DETECTION
        )

        remark = f"扫描攻击检测: {scan_description}"

        # 添加封禁
        self._add_temp_ban(ip, remark, created_by, ban_duration, "scan")

        logger.warning(f"🔥检测到扫描攻击 - IP {ip} 已被自动封禁")
        logger.info(f"扫描类型: {scan_description}, 封禁时长: {ban_duration}秒")

        # 封禁后清理该IP的扫描记录
        if ip in self.scan_attempts:
            del self.scan_attempts[ip]
        if ip in self.connection_timestamps:
            del self.connection_timestamps[ip]

        return True

    # ========== 黑白名单管理 ==========

    def add_to_blacklist(self, ip_spec: str, remark: str = "", created_by: str = None) -> bool:
        """添加到黑名单"""
        with self._lock:
            if self.blacklist.add_ip(ip_spec):
                if created_by is None:
                    created_by = OperationSource.format_created_by(
                        OperationSource.USER,
                        OperationSource.MANUAL,
                        OperationSource.ADMIN
                    )

                entry = IPEntry(
                    ip=ip_spec,
                    remark=remark,
                    created_at=datetime.now().isoformat(),
                    created_by=created_by
                )
                self.blacklist_entries[ip_spec] = entry
                self._save_blacklist()
                logger.info(f"已添加到黑名单: {ip_spec}")
                return True
            return False

    def remove_from_blacklist(self, ip_spec: str) -> bool:
        """从黑名单移除"""
        with self._lock:
            if self.blacklist.remove_entry(ip_spec):
                if ip_spec in self.blacklist_entries:
                    del self.blacklist_entries[ip_spec]
                self._save_blacklist()
                logger.info(f"已从黑名单移除: {ip_spec}")
                return True
            return False

    def add_to_whitelist(self, ip_spec: str, remark: str = "", created_by: str = None) -> bool:
        """添加到白名单"""
        with self._lock:
            if self.whitelist.add_ip(ip_spec):
                if created_by is None:
                    created_by = OperationSource.format_created_by(
                        OperationSource.USER,
                        OperationSource.MANUAL,
                        OperationSource.ADMIN
                    )

                entry = IPEntry(
                    ip=ip_spec,
                    remark=remark,
                    created_at=datetime.now().isoformat(),
                    created_by=created_by
                )
                self.whitelist_entries[ip_spec] = entry
                self._save_whitelist()
                logger.info(f"已添加到白名单: {ip_spec}")
                return True
            return False

    def remove_from_whitelist(self, ip_spec: str) -> bool:
        """从白名单移除"""
        with self._lock:
            if self.whitelist.remove_entry(ip_spec):
                if ip_spec in self.whitelist_entries:
                    del self.whitelist_entries[ip_spec]
                self._save_whitelist()
                logger.info(f"已从白名单移除: {ip_spec}")
                return True
            return False

    def get_blacklist_entries(self) -> List[Dict]:
        """获取黑名单所有条目"""
        with self._lock:
            return [
                {
                    "ip": entry.ip,
                    "remark": entry.remark,
                    "created_at": entry.created_at,
                    "created_by": entry.created_by
                }
                for entry in self.blacklist_entries.values()
            ]

    def get_whitelist_entries(self) -> List[Dict]:
        """获取白名单所有条目"""
        with self._lock:
            return [
                {
                    "ip": entry.ip,
                    "remark": entry.remark,
                    "created_at": entry.created_at,
                    "created_by": entry.created_by
                }
                for entry in self.whitelist_entries.values()
            ]

    # ========== 临时封禁管理 ==========

    def _add_temp_ban(self, ip: str, remark: str, created_by: str, duration: int, protocol: str = ""):
        """添加临时封禁（内部方法）"""
        unban_time = time.time() + duration

        ban_info = {
            'ip': ip,
            'failed_attempts': self.failed_attempts.get(ip, 0),
            'unban_time': unban_time,
            'remark': remark,
            'created_at': datetime.now().isoformat(),
            'created_by': created_by,
            'duration': duration,
            'protocol': protocol
        }

        # 添加到活跃封禁
        self.temp_bans[ip] = ban_info

        # 添加历史记录
        if self.config.core.keep_ban_history:
            self._add_to_ban_history(ban_info)

        # 保存活跃封禁（仅当有活跃封禁时才保存）
        self._save_active_bans_if_needed()

        logger.warning(f"IP {ip} 已被临时封禁 {duration}秒，原因: {remark}")

    def add_temp_ban(self, ip: str, remark: str = "手动封禁", created_by: str = None):
        """添加临时封禁（公开方法）"""
        with self._lock:
            if created_by is None:
                created_by = OperationSource.format_created_by(
                    OperationSource.USER,
                    OperationSource.MANUAL,
                    OperationSource.ADMIN
                )

            # 使用HTTP配置的封禁时长作为默认
            duration = self.config.auth_failure_detection.http_ban_duration
            self._add_temp_ban(ip, remark, created_by, duration, "manual")

    def remove_temp_ban(self, ip: str, reason: str = "手动移除", removed_by: str = None) -> bool:
        """移除临时封禁"""
        with self._lock:
            if ip in self.temp_bans:
                ban_info = self.temp_bans[ip]

                if removed_by is None:
                    removed_by = OperationSource.format_created_by(
                        OperationSource.USER,
                        OperationSource.MANUAL,
                        OperationSource.ADMIN
                    )

                # 更新历史记录
                if self.config.core.keep_ban_history:
                    self._update_ban_history_entry(ip, removed_by, reason)

                # 移除活跃封禁
                del self.temp_bans[ip]

                # 重置失败计数
                if ip in self.failed_attempts:
                    del self.failed_attempts[ip]

                # 保存活跃封禁（仅当有活跃封禁时才保存）
                self._save_active_bans_if_needed()

                logger.info(f"已移除临时封禁: {ip}, 原因: {reason}")
                return True
            return False

    def move_to_blacklist(self, ip: str, remark: str = "", created_by: str = None) -> bool:
        """将临时封禁移到黑名单"""
        with self._lock:
            if ip in self.temp_bans:
                # 获取原始信息
                original_remark = self.temp_bans[ip].get('remark', '自动封禁')
                original_created_by = self.temp_bans[ip].get('created_by', '')
                protocol_info = self.temp_bans[ip].get('protocol', '')

                # 组合新的备注
                if protocol_info:
                    new_remark = f"{protocol_info} - {remark}" if remark else f"{protocol_info} - {original_remark}"
                else:
                    new_remark = f"{remark}（由临时封禁移入，原因为：{original_remark}）" if remark else f"由临时封禁移入，原因为：{original_remark}"

                # 设置操作来源
                if created_by is None:
                    created_by = OperationSource.format_created_by(
                        OperationSource.USER,
                        OperationSource.MANUAL,
                        "temp_to_blacklist"
                    )

                # 移除临时封禁
                self.remove_temp_ban(ip, "移至黑名单", created_by)

                # 添加到黑名单
                if self.add_to_blacklist(ip, new_remark, created_by):
                    logger.info(f"已将 {ip} 从临时封禁移至黑名单")
                    return True
            return False

    def get_temp_ban_entries(self) -> List[Dict]:
        """获取所有活跃的临时封禁条目"""
        with self._lock:
            current_time = time.time()
            entries = []

            for ban_info in self.temp_bans.values():
                unban_time = ban_info.get('unban_time', 0)
                if unban_time > current_time:
                    entries.append(ban_info)

            entries.sort(key=lambda x: x.get('unban_time', 0))
            return entries

    def get_ban_history(self, limit: int = 100) -> List[Dict]:
        """获取封禁历史记录"""
        with self._lock:
            if not self.config.core.keep_ban_history:
                return []

            # 从CSV文件读取全部历史记录
            history = self._load_ban_history()
            if len(history) > limit:
                return history[-limit:]
            return history

    def clear_ban_history(self) -> bool:
        """清空所有封禁历史记录"""
        with self._lock:
            try:
                if not self.config.core.keep_ban_history:
                    logger.warning("历史记录功能未启用，无需清空")
                    return True

                # 清空CSV文件
                self._save_ban_history([])
                logger.info("已清空所有封禁历史记录")
                return True

            except Exception as e:
                logger.error(f"清空封禁历史记录失败: {e}")
                return False

    # ========== 文件操作 ==========

    def _ensure_files_exist(self):
        """确保文件存在"""
        if not self.blacklist_file.exists():
            self._create_default_file(self.blacklist_file, "黑名单", [

            ])

        if not self.whitelist_file.exists():
            self._create_default_file(self.whitelist_file, "白名单", [

            ])

        if not self.ban_history_file.exists():
            self._create_default_ban_history_file()

    def _create_default_file(self, file_path: Path, description: str, entries: List[Dict]):
        """创建默认文件"""
        data = {
            "metadata": {
                "version": "1.0",
                "description": f"{description}配置文件",
                "created_at": datetime.now().isoformat()
            },
            "entries": entries
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"创建默认{description}文件: {file_path}")

    def _create_default_ban_history_file(self):
        """创建默认封禁历史CSV文件"""
        with open(self.ban_history_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ip', 'failed_attempts', 'unban_time', 'remark', 'created_at',
                'created_by', 'duration', 'protocol', 'removed_at', 'removed_by', 'removed_reason'
            ])

    def _load_lists(self):
        """加载黑白名单"""
        try:
            # 加载黑名单
            if self.blacklist_file.exists():
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.blacklist_entries.clear()
                for entry_data in data.get('entries', []):
                    ip_spec = entry_data.get('ip', '').strip()
                    if ip_spec and self.blacklist.add_ip(ip_spec):
                        created_by = entry_data.get('created_by', 'system:auto:legacy')
                        entry = IPEntry(
                            ip=ip_spec,
                            remark=entry_data.get('remark', ''),
                            created_at=entry_data.get('created_at', ''),
                            created_by=created_by
                        )
                        self.blacklist_entries[ip_spec] = entry

                logger.info(f"已加载黑名单: {len(self.blacklist_entries)} 条记录")

            # 加载白名单
            if self.whitelist_file.exists():
                with open(self.whitelist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.whitelist_entries.clear()
                for entry_data in data.get('entries', []):
                    ip_spec = entry_data.get('ip', '').strip()
                    if ip_spec and self.whitelist.add_ip(ip_spec):
                        created_by = entry_data.get('created_by', 'system:auto:legacy')
                        entry = IPEntry(
                            ip=ip_spec,
                            remark=entry_data.get('remark', ''),
                            created_at=entry_data.get('created_at', ''),
                            created_by=created_by
                        )
                        self.whitelist_entries[ip_spec] = entry

                logger.info(f"已加载白名单: {len(self.whitelist_entries)} 条记录")

        except Exception as e:
            logger.error(f"加载黑白名单失败: {e}")

    def _save_blacklist(self):
        """保存黑名单"""
        try:
            data = {
                "metadata": {
                    "version": "1.0",
                    "description": "黑名单配置文件",
                    "updated_at": datetime.now().isoformat(),
                    "total_entries": len(self.blacklist_entries)
                },
                "entries": [
                    {
                        "ip": entry.ip,
                        "remark": entry.remark,
                        "created_at": entry.created_at,
                        "created_by": entry.created_by
                    }
                    for entry in self.blacklist_entries.values()
                ]
            }

            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            logger.error(f"保存黑名单失败: {e}")

    def _save_whitelist(self):
        """保存白名单"""
        try:
            data = {
                "metadata": {
                    "version": "1.0",
                    "description": "白名单配置文件",
                    "updated_at": datetime.now().isoformat(),
                    "total_entries": len(self.whitelist_entries)
                },
                "entries": [
                    {
                        "ip": entry.ip,
                        "remark": entry.remark,
                        "created_at": entry.created_at,
                        "created_by": entry.created_by
                    }
                    for entry in self.whitelist_entries.values()
                ]
            }

            with open(self.whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            logger.error(f"保存白名单失败: {e}")

    def _load_active_bans(self):
        """从临时文件加载活跃封禁"""
        try:
            if not self.active_bans_file.exists():
                return

            with open(self.active_bans_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            current_time = time.time()
            self.temp_bans.clear()

            # 加载活跃封禁
            for ban_info in data.get('active_bans', []):
                ip = ban_info.get('ip', '')
                unban_time = ban_info.get('unban_time', 0)

                if ip and unban_time > current_time:
                    self.temp_bans[ip] = ban_info

            logger.info(f"已加载活跃封禁: {len(self.temp_bans)} 条记录")

            # 加载后删除临时文件
            os.remove(self.active_bans_file)
            logger.info(f"已删除临时文件: {self.active_bans_file}")

        except Exception as e:
            logger.error(f"加载活跃封禁失败: {e}")

    def _save_active_bans_if_needed(self):
        """保存活跃封禁到临时文件（仅当有活跃封禁时）"""
        try:
            if not self.temp_bans:
                # 如果没有活跃封禁，删除临时文件（如果存在）
                if self.active_bans_file.exists():
                    os.remove(self.active_bans_file)
                return

            current_time = time.time()
            active_bans = []

            # 准备活跃封禁数据（只保存未过期的）
            for ban_info in self.temp_bans.values():
                unban_time = ban_info.get('unban_time', 0)
                if unban_time > current_time:
                    active_bans.append(ban_info)

            if not active_bans:
                # 如果没有未过期的封禁，删除临时文件（如果存在）
                if self.active_bans_file.exists():
                    os.remove(self.active_bans_file)
                return

            data = {
                "metadata": {
                    "version": "1.0",
                    "description": "活跃封禁临时文件",
                    "updated_at": datetime.now().isoformat(),
                    "active_entries": len(active_bans)
                },
                "active_bans": active_bans
            }

            with open(self.active_bans_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            logger.error(f"保存活跃封禁失败: {e}")

    def _load_ban_history(self) -> List[Dict]:
        """从CSV文件加载封禁历史"""
        history = []

        if not self.ban_history_file.exists():
            return history

        try:
            with open(self.ban_history_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 转换类型
                    try:
                        row['failed_attempts'] = int(row.get('failed_attempts', 0))
                        row['unban_time'] = float(row.get('unban_time', 0))
                        row['duration'] = int(row.get('duration', 0))
                    except (ValueError, TypeError):
                        pass
                    history.append(row)

            # 限制历史记录数量
            max_size = self.config.core.max_history_size
            if len(history) > max_size:
                history = history[-max_size:]
                # 保存裁剪后的历史记录
                self._save_ban_history(history)

            return history

        except Exception as e:
            logger.error(f"加载封禁历史失败: {e}")
            return []

    def _save_ban_history(self, history: List[Dict]):
        """保存封禁历史到CSV文件"""
        if not self.config.core.keep_ban_history:
            return

        try:
            fieldnames = [
                'ip', 'failed_attempts', 'unban_time', 'remark', 'created_at',
                'created_by', 'duration', 'protocol', 'removed_at', 'removed_by', 'removed_reason'
            ]

            with open(self.ban_history_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for entry in history:
                    writer.writerow(entry)

        except Exception as e:
            logger.error(f"保存封禁历史失败: {e}")

    def _add_to_ban_history(self, ban_info: Dict):
        """添加封禁记录到历史"""
        if not self.config.core.keep_ban_history:
            return

        # 加载现有历史
        history = self._load_ban_history()

        # 准备新记录
        history_entry = ban_info.copy()
        history_entry['removed_at'] = None
        history_entry['removed_by'] = None
        history_entry['removed_reason'] = None

        # 添加到历史
        history.append(history_entry)

        # 限制历史记录数量
        max_size = self.config.core.max_history_size
        if len(history) > max_size:
            history = history[-max_size:]

        # 保存历史
        self._save_ban_history(history)

    def _update_ban_history_entry(self, ip: str, removed_by: str, removed_reason: str):
        """更新封禁历史记录"""
        if not self.config.core.keep_ban_history:
            return

        # 加载现有历史
        history = self._load_ban_history()

        # 更新最近一条匹配的记录
        for i in range(len(history)-1, -1, -1):
            entry = history[i]
            if entry.get('ip') == ip and not entry.get('removed_at'):
                entry['removed_at'] = datetime.now().isoformat()
                entry['removed_by'] = removed_by
                entry['removed_reason'] = removed_reason
                break

        # 保存历史
        self._save_ban_history(history)

    # ========== 清理功能 ==========

    def _cleanup_expired_bans(self):
        """清理过期的临时封禁记录"""
        with self._lock:
            current_time = time.time()
            expired_ips = []

            for ip, ban_info in self.temp_bans.items():
                unban_time = ban_info.get('unban_time', 0)
                if unban_time <= current_time:
                    expired_ips.append((ip, ban_info))

            if expired_ips:
                for ip, ban_info in expired_ips:
                    # 更新历史记录
                    if self.config.core.keep_ban_history:
                        self._update_ban_history_entry(ip, None, '自动过期')

                    # 移除活跃封禁
                    del self.temp_bans[ip]
                    if ip in self.failed_attempts:
                        del self.failed_attempts[ip]

                # 保存活跃封禁
                self._save_active_bans_if_needed()

                logger.debug(f"已清理 {len(expired_ips)} 个过期的临时封禁")

    def _cleanup_old_scan_records(self):
        """清理旧的扫描记录"""
        current_time = time.time()
        scan_cleanup_interval = self.config.advanced.scan_cleanup_interval

        # 清理扫描尝试记录
        expired_ips = []
        for ip, data in self.scan_attempts.items():
            data['attempts'] = [attempt for attempt in data['attempts']
                              if current_time - attempt['time'] <= scan_cleanup_interval]

            data['count'] = len(data['attempts'])
            data['scan_types'] = set(attempt['type'] for attempt in data['attempts'])

            if data['count'] == 0:
                expired_ips.append(ip)

        for ip in expired_ips:
            del self.scan_attempts[ip]

        # 清理连接时间记录
        for ip in list(self.connection_timestamps.keys()):
            # 使用HTTP窗口作为默认清理窗口
            window = self.config.advanced.rapid_connection_detection.http_window
            self.connection_timestamps[ip] = [
                ts for ts in self.connection_timestamps[ip]
                if current_time - ts <= window
            ]
            if not self.connection_timestamps[ip]:
                del self.connection_timestamps[ip]

    # ========== 辅助功能 ==========

    def _get_scan_attempts_info(self, ip: str) -> Dict:
        """获取扫描尝试信息"""
        with self._scan_lock:
            return self.scan_attempts.get(ip, {})

    def get_stats(self) -> Dict:
        """获取安全统计信息"""
        with self._lock:
            # 加载历史记录以获取准确数量
            history_count = 0
            if self.config.core.keep_ban_history:
                history = self._load_ban_history()
                history_count = len(history)

            return {
                'whitelist_entries': len(self.whitelist_entries),
                'blacklist_entries': len(self.blacklist_entries),
                'temp_bans_count': len(self.temp_bans),
                'failed_attempts_count': len(self.failed_attempts),
                'ban_history_count': history_count,
                'security_mode': self.config.core.mode,
                'scan_protection_enabled': self.config.advanced.enable_scan_protection,
                'rapid_connection_detection_enabled': self.config.advanced.rapid_connection_detection.enabled,
                'auth_failure_detection_enabled': self.config.auth_failure_detection.enabled
            }

    def get_entry_display_info(self, entry: Dict) -> Dict:
        """获取条目的显示信息"""
        display_info = entry.copy()

        created_by = entry.get('created_by', '')
        if created_by:
            display_info['created_by_display'] = OperationSource.get_display_name(created_by)
            parsed = OperationSource.parse_created_by(created_by)
            display_info.update(parsed)
        else:
            display_info['created_by_display'] = "未知来源"

        return display_info

    # ========== 线程管理 ==========

    def _start_cleanup_thread(self):
        """启动清理线程"""
        self._running = True
        self._stop_event.clear()  # 重置事件状态

        def cleanup_worker():
            while self._running:
                # 使用 wait() 代替 sleep()，可被事件唤醒
                if self._stop_event.wait(timeout=self.config.core.cleanup_interval):
                    # 被 stop_event.set() 唤醒，立即退出循环
                    break

                try:
                    self._cleanup_expired_bans()
                except Exception as e:
                    logger.error(f"清理线程错误: {e}")

        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()

    def stop(self):
        """停止安全管理器"""
        logger.debug("开始停止安全管理器...")

        self._running = False
        self._stop_event.set()  # 立即唤醒线程

        # 短暂等待
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=0.5)

        # 保存活跃封禁到临时文件
        try:
            self._save_active_bans_if_needed()
            logger.info("已保存活跃封禁数据到临时文件")
        except Exception as e:
            logger.error(f"保存活跃封禁数据失败: {e}")
