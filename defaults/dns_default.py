# -*- coding: utf-8 -*-
"""
Module: dns_default.py
Author: Takeshi
Date: 2025-12-25

Description:
    DNS解析器默认配置
"""


from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class DNSConfig:
    """
    DNS解析器配置类

    用于配置DNS解析器的各种参数，支持远程DNS解析、缓存、黑名单等功能。

    Attributes:
        enable_remote_dns_resolve (bool): 是否启用远程DNS解析
            True: 使用配置的DNS服务器进行远程解析
            False: 仅使用系统DNS解析
            默认: True

        name (str): DNS解析器名称，用于日志标识
            默认: "DNS解析器"

        dns_servers (List[str]): DNS服务器列表
            按优先级排列的DNS服务器地址，支持IPv4地址
            当解析策略为"serial"时，按列表顺序尝试
            当解析策略为"parallel"时，并发查询所有服务器

        enable_cache (bool): 是否启用DNS缓存
            True: 缓存DNS查询结果，提高解析速度
            False: 每次查询都直接请求DNS服务器
            默认: True

        default_cache_ttl (int): 默认缓存生存时间（秒）
            指定DNS记录的默认缓存时间
            实际TTL以DNS服务器返回的值为准，此为兜底值
            默认: 300秒（5分钟）

        cleanup_interval (Optional[int]): 缓存清理间隔（秒）
            后台线程清理过期缓存的间隔时间
            None: 不启用定期清理
            默认: 600秒（10分钟）

        max_cache_size (int): 最大缓存记录数
            限制缓存中的最大记录数量，防止内存占用过大
            达到限制时会清理最旧的记录
            默认: 1000条

        enable_system_dns (bool): 是否启用系统DNS作为后备
            True: 当所有配置的DNS服务器都失败时，尝试使用系统DNS
            False: 仅使用配置的DNS服务器
            默认: False

        resolve_strategy (str): DNS解析策略
            "serial": 串行解析 - 按顺序尝试DNS服务器，直到成功
            "parallel": 并行解析 - 并发查询所有DNS服务器，返回第一个成功的结果
            默认: "serial"

        serial_timeout (int): 串行解析超时时间（秒）
            每个DNS服务器的查询超时时间
            默认: 3秒

        parallel_timeout (int): 并行解析超时时间（秒）
            整个并行查询过程的超时时间
            默认: 3秒

        parallel_workers (int): 并行解析工作线程数
            用于并发查询DNS服务器的线程数量
            默认: 5个线程

        blacklist_domains (List[str]): 域名黑名单列表
            完全匹配的域名列表，拒绝解析这些域名
            默认: []（空列表）

        blacklist_patterns (List[str]): 域名黑名单模式列表
            支持通配符的模式列表（如 "*.malware.com", "adserver.*"）
            使用fnmatch语法进行匹配
            默认: []（空列表）

    Methods:
        to_dict() -> Dict[str, Any]:
            将配置转换为字典格式，便于序列化和存储

        from_dict(data: Dict[str, Any]) -> 'DNSConfig':
            从字典创建配置实例，用于从配置文件或数据库加载配置

        get_default_config() -> 'DNSConfig':
            获取默认配置实例，用于与config_manager兼容

    Example:
        >>> config = DNSConfig()
        >>> config.enable_cache = True
        >>> config.dns_servers = ['8.8.8.8', '1.1.1.1']
        >>> config_dict = config.to_dict()
        >>>
        >>> # 从字典加载配置
        >>> loaded_config = DNSConfig.from_dict(config_dict)
        >>>
        >>> # 获取默认配置
        >>> default_config = DNSConfig.get_default_config()
    """

    enable_remote_dns_resolve: bool = False
    name: str = "DNS解析器"
    dns_servers: List[str] = field(default_factory=lambda: [
        '8.8.8.8',
        '1.1.1.1',
        '208.67.222.222',
        '8.8.4.4',
        '1.0.0.1',
        '208.67.220.220',
    ])
    enable_cache: bool = True
    default_cache_ttl: int = 300
    cleanup_interval: Optional[int] = 600
    max_cache_size: int = 1000
    enable_system_dns: bool = False
    resolve_strategy: str = "serial"
    serial_timeout: int = 3
    parallel_timeout: int = 3
    parallel_workers: int = 5
    blacklist_domains: List[str] = field(default_factory=list)
    blacklist_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含所有配置项的字典，列表会进行复制以防止意外修改

        Note:
            返回的字典适合用于JSON序列化或持久化存储
        """
        return {
            'enable_remote_dns_resolve': self.enable_remote_dns_resolve,
            'name': self.name,
            'dns_servers': self.dns_servers.copy(),  # 复制列表
            'enable_cache': self.enable_cache,
            'default_cache_ttl': self.default_cache_ttl,
            'cleanup_interval': self.cleanup_interval,
            'max_cache_size': self.max_cache_size,
            'enable_system_dns': self.enable_system_dns,
            'resolve_strategy': self.resolve_strategy,
            'serial_timeout': self.serial_timeout,
            'parallel_timeout': self.parallel_timeout,
            'parallel_workers': self.parallel_workers,
            'blacklist_domains': self.blacklist_domains.copy(),
            'blacklist_patterns': self.blacklist_patterns.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DNSConfig':
        """从字典创建配置实例

        Args:
            data: 包含配置信息的字典

        Returns:
            新的DNSConfig实例

        Note:
            如果字典中缺少某些字段，会使用默认值填充
        """
        return cls(
            enable_remote_dns_resolve=data.get('enable_remote_dns_resolve', True),
            name=data.get('name', 'DNS解析器'),
            dns_servers=data.get('dns_servers', []),
            enable_cache=data.get('enable_cache', True),
            default_cache_ttl=data.get('default_cache_ttl', 300),
            cleanup_interval=data.get('cleanup_interval'),
            max_cache_size=data.get('max_cache_size', 1000),
            enable_system_dns=data.get('enable_system_dns', False),
            resolve_strategy=data.get('resolve_strategy', 'serial'),
            serial_timeout=data.get('serial_timeout', 3),
            parallel_timeout=data.get('parallel_timeout', 3),
            parallel_workers=data.get('parallel_workers', 5),
            blacklist_domains=data.get('blacklist_domains', []),
            blacklist_patterns=data.get('blacklist_patterns', [])
        )

    @classmethod
    def get_default_config(cls) -> 'DNSConfig':
        """获取默认配置实例

        此方法用于与config_manager兼容，提供默认配置实例

        Returns:
            包含所有默认值的DNSConfig实例
        """
        return cls()
