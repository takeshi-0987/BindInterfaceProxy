# -*- coding: utf-8 -*-
"""
Module: security_default.py
Author: Takeshi
Date: 2025-12-25

Description:
    安全管理默认配置
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class CoreSecurityConfig:
    """
    核心安全配置

    Attributes:
        mode (str): 安全模式，可选值：
            - 'blacklist': 仅黑名单模式 - 只有黑名单中的IP被拒绝，其他都允许
            - 'whitelist': 仅白名单模式 - 只有白名单中的IP被允许，其他都拒绝
            - 'mixed': 混合模式 - 先检查白名单（最高优先级），再检查黑名单
            默认: 'mixed'

        blacklist_file (str): 黑名单文件路径，存储永久封禁的IP地址/IP段
            支持格式：单个IP、CIDR网段、IP范围
            示例：'192.168.1.100', '10.0.0.0/24', '172.16.1.1-172.16.1.50'
            默认: 'data/blacklist.json'

        whitelist_file (str): 白名单文件路径，存储受信任的IP地址/IP段
            格式同黑名单，但具有最高优先级
            默认: 'data/whitelist.json'

        ban_history_file (str): 封禁历史文件路径，存储临时封禁记录和封禁历史
            包含活跃封禁和封禁历史记录
            默认: 'data/ban_history.csv'

        cleanup_interval (int): 清理线程运行间隔（秒）
            定期清理过期的临时封禁记录
            默认: 300秒（5分钟）

        keep_ban_history (bool): 是否保存临时封禁历史记录
            True: 记录所有封禁和解封操作，便于审计
            False: 不记录历史，只保留活跃封禁
            默认: True

        max_history_size (int): 最大历史记录条数
            防止历史记录文件过大，达到限制时会自动清理最旧的记录
            默认: 100条
    """

    mode: str = 'mixed'
    blacklist_file: str = 'data/blacklist.json'
    whitelist_file: str = 'data/whitelist.json'
    ban_history_file: str = 'data/ban_history.csv'
    cleanup_interval: int = 300
    keep_ban_history: bool = True
    max_history_size: int = 100

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式，便于序列化"""
        return {
            'mode': self.mode,
            'blacklist_file': self.blacklist_file,
            'whitelist_file': self.whitelist_file,
            'ban_history_file': self.ban_history_file,
            'cleanup_interval': self.cleanup_interval,
            'keep_ban_history': self.keep_ban_history,
            'max_history_size': self.max_history_size
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CoreSecurityConfig':
        """从字典创建配置实例"""
        return cls(
            mode=data.get('mode', 'mixed'),
            blacklist_file=data.get('blacklist_file', 'data/blacklist.json'),
            whitelist_file=data.get('whitelist_file', 'data/whitelist.json'),
            ban_history_file=data.get('ban_history_file', 'data/ban_history.json'),
            cleanup_interval=data.get('cleanup_interval', 300),
            keep_ban_history=data.get('keep_ban_history', True),
            max_history_size=data.get('max_history_size', 100)
        )


@dataclass
class AuthFailureDetectionConfig:
    """
    认证失败检测配置

    控制HTTP和SOCKS协议的认证失败检测参数。
    当同一IP在短时间内认证失败次数达到阈值时，会被临时封禁。

    Attributes:
        enabled (bool): 是否启用认证失败检测
            总开关，关闭时不会进行认证失败检测和自动封禁
            默认: True

        http_max_failures (int): HTTP最大认证失败次数
            同一IP在短时间内允许的HTTP认证失败次数
            达到此值将触发临时封禁
            默认: 10次

        http_ban_duration (int): HTTP认证失败封禁时长（秒）
            HTTP协议触发封禁后的禁止访问时长
            默认: 3600秒（1小时）

        socks_max_failures (int): SOCKS最大认证失败次数
            同一IP在短时间内允许的SOCKS认证失败次数
            SOCKS协议通常要求更严格，所以阈值比HTTP低
            默认: 5次

        socks_ban_duration (int): SOCKS认证失败封禁时长（秒）
            SOCKS协议触发封禁后的禁止访问时长
            通常比HTTP更长
            默认: 3600秒（1小时）
    """

    enabled: bool = True
    http_max_failures: int = 10
    http_ban_duration: int = 3600
    socks_max_failures: int = 5
    socks_ban_duration: int = 3600

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式"""
        return {
            'enabled': self.enabled,
            'http_max_failures': self.http_max_failures,
            'http_ban_duration': self.http_ban_duration,
            'socks_max_failures': self.socks_max_failures,
            'socks_ban_duration': self.socks_ban_duration
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthFailureDetectionConfig':
        """从字典创建配置实例"""
        return cls(
            enabled=data.get('enabled', True),
            http_max_failures=data.get('http_max_failures', 10),
            http_ban_duration=data.get('http_ban_duration', 1800),
            socks_max_failures=data.get('socks_max_failures', 5),
            socks_ban_duration=data.get('socks_ban_duration', 3600)
        )


@dataclass
class RapidConnectionDetectionConfig:
    """
    快速连接检测配置

    检测短时间内的大量连接（DDoS/暴力破解）。
    监控单位时间内的连接频率，超过阈值时触发防护。

    Attributes:
        enabled (bool): 是否启用快速连接检测
            总开关，关闭时不会进行快速连接检测
            默认: False

        http_threshold (int): HTTP快速连接检测阈值
            在http_window时间内允许的最大HTTP连接数
            超过此阈值会触发扫描检测
            默认: 150次

        http_window (int): HTTP快速连接检测时间窗口（秒）
            统计HTTP连接数的时间范围
            默认: 60秒

        socks_threshold (int): SOCKS快速连接检测阈值
            在socks_window时间内允许的最大SOCKS连接数
            SOCKS协议的正常连接频率较低，阈值设置比HTTP小
            默认: 30次

        socks_window (int): SOCKS快速连接检测时间窗口（秒）
            统计SOCKS连接数的时间范围
            默认: 60秒
    """

    enabled: bool = False
    http_threshold: int = 200
    http_window: int = 60
    socks_threshold: int = 50
    socks_window: int = 60

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式"""
        return {
            'enabled': self.enabled,
            'http_threshold': self.http_threshold,
            'http_window': self.http_window,
            'socks_threshold': self.socks_threshold,
            'socks_window': self.socks_window
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RapidConnectionDetectionConfig':
        """从字典创建配置实例"""
        return cls(
            enabled=data.get('enabled', False),
            http_threshold=data.get('http_threshold', 150),
            http_window=data.get('http_window', 60),
            socks_threshold=data.get('socks_threshold', 30),
            socks_window=data.get('socks_window', 60)
        )


@dataclass
class AdvancedSecurityConfig:
    """
    高级安全配置 - 扫描防护和异常检测(测试功能，谨慎开启)

    这些功能用于检测和防御各种扫描攻击和异常行为。
    所有检测功能都依赖enable_scan_protection总开关。

    Attributes:
        # 扫描防护总开关
        enable_scan_protection (bool): 是否启用扫描防护
            总开关，关闭时所有高级检测功能都不生效
            默认: False（建议在测试稳定后启用）

        max_scan_attempts (int): 最大扫描尝试次数
            同一IP在scan_cleanup_interval时间内允许的扫描尝试次数
            超过此值将触发封禁
            默认: 5次

        scan_ban_duration (int): 扫描攻击封禁时长（秒）
            触发扫描防护后的封禁时间
            默认: 3600秒（1小时）

        scan_cleanup_interval (int): 扫描记录清理间隔（秒）
            清理旧的扫描尝试记录的时间间隔
            默认: 3600秒（1小时）

        # 具体检测功能开关
        enable_invalid_version_detection (bool): 启用无效版本检测
            检测SOCKS协议中的无效版本号
            默认: False

        enable_invalid_method_detection (bool): 启用无效方法检测
            检测SOCKS协议中的无效认证方法
            默认: False

        enable_malformed_request_detection (bool): 启用畸形请求检测
            检测格式错误的HTTP/SOCKS请求
            默认: False

        enable_invalid_http_method_detection (bool): 启用无效HTTP方法检测
            检测非标准的HTTP方法（可能为攻击尝试）
            默认: False

        enable_malformed_connect_detection (bool): 启用畸形CONNECT请求检测
            检测格式错误的HTTP CONNECT请求
            默认: False

        enable_invalid_port_detection (bool): 启用无效端口检测
            检测异常的目标端口号（如0、负数、过大值）
            默认: False

        enable_suspicious_headers_detection (bool): 启用可疑HTTP头检测
            检测包含可疑内容的HTTP头部
            默认: False

        # 子配置
        rapid_connection_detection: RapidConnectionDetectionConfig = field(
            default_factory=RapidConnectionDetectionConfig
        )
    """

    enable_scan_protection: bool = False
    max_scan_attempts: int = 5
    scan_ban_duration: int = 3600
    scan_cleanup_interval: int = 3600

    # 具体检测功能
    enable_invalid_version_detection: bool = False
    enable_invalid_method_detection: bool = False
    enable_malformed_request_detection: bool = False
    enable_invalid_http_method_detection: bool = False
    enable_malformed_connect_detection: bool = False
    enable_invalid_port_detection: bool = False
    enable_suspicious_headers_detection: bool = False

    # 快速连接检测子配置
    rapid_connection_detection: RapidConnectionDetectionConfig = field(
        default_factory=RapidConnectionDetectionConfig
    )

    def to_dict(self) -> Dict[str, Any]:
        """将完整配置转换为字典格式"""
        return {
            'enable_scan_protection': self.enable_scan_protection,
            'max_scan_attempts': self.max_scan_attempts,
            'scan_ban_duration': self.scan_ban_duration,
            'scan_cleanup_interval': self.scan_cleanup_interval,
            'enable_invalid_version_detection': self.enable_invalid_version_detection,
            'enable_invalid_method_detection': self.enable_invalid_method_detection,
            'enable_malformed_request_detection': self.enable_malformed_request_detection,
            'enable_invalid_http_method_detection': self.enable_invalid_http_method_detection,
            'enable_malformed_connect_detection': self.enable_malformed_connect_detection,
            'enable_invalid_port_detection': self.enable_invalid_port_detection,
            'enable_suspicious_headers_detection': self.enable_suspicious_headers_detection,
            'rapid_connection_detection': self.rapid_connection_detection.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdvancedSecurityConfig':
        """从字典创建配置实例"""
        rapid_connection_data = data.get('rapid_connection_detection', {})

        return cls(
            enable_scan_protection=data.get('enable_scan_protection', False),
            max_scan_attempts=data.get('max_scan_attempts', 5),
            scan_ban_duration=data.get('scan_ban_duration', 3600),
            scan_cleanup_interval=data.get('scan_cleanup_interval', 3600),
            enable_invalid_version_detection=data.get('enable_invalid_version_detection', False),
            enable_invalid_method_detection=data.get('enable_invalid_method_detection', False),
            enable_malformed_request_detection=data.get('enable_malformed_request_detection', False),
            enable_invalid_http_method_detection=data.get('enable_invalid_http_method_detection', False),
            enable_malformed_connect_detection=data.get('enable_malformed_connect_detection', False),
            enable_invalid_port_detection=data.get('enable_invalid_port_detection', False),
            enable_suspicious_headers_detection=data.get('enable_suspicious_headers_detection', False),
            rapid_connection_detection=RapidConnectionDetectionConfig.from_dict(rapid_connection_data)
        )


@dataclass
class SecurityConfig:
    """
    安全管理器完整配置

    采用分层配置设计：
    1. core: 核心基础配置
    2. auth_failure_detection: 认证失败检测配置
    3. advanced: 高级安全功能配置（包含快速连接检测子配置）

    Attributes:
        core (CoreSecurityConfig): 核心安全配置
            包含文件路径、模式、清理间隔等基础设置
            默认: CoreSecurityConfig()

        auth_failure_detection (AuthFailureDetectionConfig): 认证失败检测配置
            控制HTTP和SOCKS协议的认证失败检测参数
            默认: AuthFailureDetectionConfig()

        advanced (AdvancedSecurityConfig): 高级安全配置
            包含扫描防护和各种异常检测功能
            默认: AdvancedSecurityConfig()
    """

    core: CoreSecurityConfig = field(default_factory=CoreSecurityConfig)
    auth_failure_detection: AuthFailureDetectionConfig = field(
        default_factory=AuthFailureDetectionConfig
    )
    advanced: AdvancedSecurityConfig = field(default_factory=AdvancedSecurityConfig)

    def to_dict(self) -> Dict[str, Any]:
        """将完整配置转换为嵌套字典格式"""
        return {
            'core': self.core.to_dict(),
            'auth_failure_detection': self.auth_failure_detection.to_dict(),
            'advanced': self.advanced.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecurityConfig':
        """从嵌套字典创建完整配置实例"""
        core_data = data.get('core', {})
        auth_failure_data = data.get('auth_failure_detection', {})
        advanced_data = data.get('advanced', {})

        return cls(
            core=CoreSecurityConfig.from_dict(core_data),
            auth_failure_detection=AuthFailureDetectionConfig.from_dict(auth_failure_data),
            advanced=AdvancedSecurityConfig.from_dict(advanced_data)
        )

    @classmethod
    def get_default_config(cls) -> 'SecurityConfig':
        """获取默认配置

        此方法用于与config_manager兼容，提供默认配置实例

        Returns:
            默认配置实例
        """
        return cls()
