# -*- coding: utf-8 -*-
"""
Module: ip_geo_default.py
Author: Takeshi
Date: 2025-12-25

Description:
    IP地理信息配置类
"""


from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """数据库类型枚举"""
    MMDB = "mmdb"                     # MaxMind DB格式 (GeoLite2/GeoIP2)
    IP2LOCATION_BIN = "ip2location_bin"  # IP2Location BIN格式
    UNKNOWN = "unknown"


@dataclass
class DatabaseConfig:
    """
    数据库配置项

    Attributes:
        name (str): 数据库名称，用于显示和标识
        path (str): 数据库文件路径，相对或绝对路径
        db_type (str): 数据库类型，对应 DatabaseType 枚举值，默认 "mmdb"
        enabled (bool): 是否启用此数据库，默认 True
        priority (int): 查询优先级，数字越小优先级越高，默认 1
        format_spec (Dict[str, Any]): 格式规范配置（目前未使用，可保留用于未来扩展）
    """
    name: str
    path: str
    db_type: str = "mmdb"  # 数据库类型，对应 DatabaseType 枚举值
    enabled: bool = True
    priority: int = 1
    format_spec: Dict[str, Any] = field(default_factory=dict)  # 格式规范配置

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            包含所有配置项的字典
        """
        return {
            'name': self.name,
            'path': self.path,
            'db_type': self.db_type,
            'enabled': self.enabled,
            'priority': self.priority,
            'format_spec': self.format_spec.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatabaseConfig':
        """从字典创建配置对象

        Args:
            data: 包含配置信息的字典

        Returns:
            数据库配置对象
        """
        return cls(
            name=data.get('name', ''),
            path=data.get('path', ''),
            db_type=data.get('db_type', 'mmdb'),
            enabled=data.get('enabled', True),
            priority=data.get('priority', 1),
            format_spec=data.get('format_spec', {})
        )

@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True           # 是否启用缓存
    ttl_seconds: int = 600         # 缓存时间（秒），默认10分钟
    max_size: int = 100        # 最大缓存条数

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            包含所有配置项的字典
        """
        return {
            'enabled': self.enabled,
            'ttl_seconds': self.ttl_seconds,
            'max_size': self.max_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheConfig':
        """从字典创建配置对象

        Args:
            data: 包含配置信息的字典

        Returns:
            缓存配置对象
        """
        return cls(
            enabled=data.get('enabled', True),
            ttl_seconds=data.get('ttl_seconds', 600),
            max_size=data.get('ttl_max_size', 200),
        )

@dataclass
class SearchURLConfig:
    """
    在线搜索网址配置

    Attributes:
        enabled (bool): 是否启用在线搜索功能，默认 True
        urls (List[Dict[str, str]]): 在线查询网址列表，每个网址包含name和url
    """
    enabled: bool = True
    urls: List[Dict[str, str]] = field(default_factory=lambda: [
        {"name": "ip138查询", "url": "https://www.ip138.com/iplookup.asp?ip={ip}&action=2"},
        {"name": "AbuseIPDB", "url": "https://www.abuseipdb.com/check/{ip}"},
        {"name": "Shodan", "url": "https://www.shodan.io/host/{ip}"},
        {"name": "Google搜索", "url": "https://www.google.com/search?q=ip+{ip}"},
        {"name": "Baidu搜索", "url": "https://www.baidu.com/s?wd=ip+{ip}"},
    ])

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            包含所有配置项的字典
        """
        return {
            'enabled': self.enabled,
            'urls': self.urls.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchURLConfig':
        """从字典创建配置对象

        Args:
            data: 包含配置信息的字典

        Returns:
            搜索网址配置对象
        """
        return cls(
            enabled=data.get('enabled', True),
            urls=data.get('urls', [])
        )


@dataclass
class QueryStrategyConfig:
    """
    查询策略配置

    Attributes:
        strategy (str): 查询策略，可选 "sequential"（串行）或 "parallel"（并行），默认 "sequential"
        stop_on_first_success (bool): 找到第一个成功结果就停止查询，默认 True
        skip_private_ips (bool): 跳过内网IP（如192.168.x.x）查询，默认 True
        skip_special_ips (bool): 跳过特殊IP（回环地址、组播地址等）查询，默认 True
    """
    strategy: str = "sequential"  # sequential, parallel
    stop_on_first_success: bool = True  # 找到第一个成功结果就停止
    skip_private_ips: bool = True  # 跳过内网IP查询
    skip_special_ips: bool = True  # 跳过特殊IP（回环、组播等）

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            包含所有配置项的字典
        """
        return {
            'strategy': self.strategy,
            'stop_on_first_success': self.stop_on_first_success,
            'skip_private_ips': self.skip_private_ips,
            'skip_special_ips': self.skip_special_ips
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueryStrategyConfig':
        """从字典创建配置对象

        Args:
            data: 包含配置信息的字典

        Returns:
            查询策略配置对象
        """
        return cls(
            strategy=data.get('strategy', 'sequential'),
            stop_on_first_success=data.get('stop_on_first_success', True),
            skip_private_ips=data.get('skip_private_ips', True),
            skip_special_ips=data.get('skip_special_ips', True)
        )


@dataclass
class DisplayConfig:
    """
    显示配置

    Attributes:
        format_string (str): 位置格式化字符串，使用{country}、{region}等占位符，默认 "{country}-{region}-{city}"
                             支持的占位符有{country}、{region}、{city}、{isp}、{asn}
        show_isp (bool): 是否显示ISP（互联网服务提供商）信息，默认 True
        show_asn (bool): 是否显示ASN（自治系统号）信息，默认 False
        show_network (bool): 是否显示网络信息（CIDR、组织等），默认 True
    """
    format_string: str = "{country}-{region}-{city}"  # 位置格式化字符串
    show_isp: bool = True          # 是否显示ISP信息
    show_asn: bool = False         # 是否显示ASN信息
    show_network: bool = True      # 是否显示网络信息

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            包含所有配置项的字典
        """
        return {
            'format_string': self.format_string,
            'show_isp': self.show_isp,
            'show_asn': self.show_asn,
            'show_network': self.show_network
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayConfig':
        """从字典创建配置对象

        Args:
            data: 包含配置信息的字典

        Returns:
            显示配置对象
        """
        return cls(
            format_string=data.get('format_string', "{country}-{region}-{city}"),
            show_isp=data.get('show_isp', True),
            show_asn=data.get('show_asn', False),
            show_network=data.get('show_network', True)
        )


@dataclass
class IPGeoConfig:
    """
    IP地理位置查询主配置

    Attributes:
        enabled (bool): 是否启用本地IP地理位置查询功能，默认 False
        databases (List[DatabaseConfig]): 数据库配置列表
        search_urls (SearchURLConfig): 在线搜索网址配置
        max_concurrent_queries (int): 最大并发查询数（用于并行策略），默认 2
        query_config (QueryStrategyConfig): 查询策略配置
        display_config (DisplayConfig): 显示配置
    """
    enabled: bool = False

    # 数据库配置
    databases: List[DatabaseConfig] = field(default_factory=lambda: [
        # DatabaseConfig(
        #     name="GeoLite2-City",
        #     path="geoip/GeoLite2-City.mmdb",
        #     db_type="mmdb",
        #     enabled=True,
        #     priority=1
        # ),
        # DatabaseConfig(
        # name="IP2Location DB11",
        # path="geoip/IP2LOCATION-LITE-DB11.BIN",
        # db_type="ip2location_bin",
        # enabled=True,
        # priority=2
        # ),
    ])


    # 查询配置
    max_concurrent_queries: int = 2
    query_config: QueryStrategyConfig = field(default_factory=QueryStrategyConfig)

    # 添加缓存配置
    cache_config: CacheConfig = field(default_factory=CacheConfig)

    # 显示配置
    display_config: DisplayConfig = field(default_factory=DisplayConfig)

    # 在线搜索网址配置
    search_urls: SearchURLConfig = field(default_factory=SearchURLConfig)


    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            包含所有配置项的字典
        """
        return {
            'enabled': self.enabled,
            'databases': [db.to_dict() for db in self.databases],
            'max_concurrent_queries': self.max_concurrent_queries,
            'query_config': self.query_config.to_dict(),
            'cache_config': self.cache_config.to_dict(),
            'display_config': self.display_config.to_dict(),
            'search_urls': self.search_urls.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPGeoConfig':
        """从字典创建配置对象

        Args:
            data: 包含配置信息的字典

        Returns:
            IP地理位置配置对象
        """
        # 处理嵌套配置
        databases = []
        for db_data in data.get('databases', []):
            databases.append(DatabaseConfig.from_dict(db_data))

        query_data = data.get('query_config', {})
        cache_data = data.get('cache_data', {})
        display_data = data.get('display_config', {})
        search_urls_data = data.get('search_urls', {})

        return cls(
            enabled=data.get('enabled', True),
            databases=databases,
            max_concurrent_queries=data.get('max_concurrent_queries', 2),
            query_config=QueryStrategyConfig.from_dict(query_data),
            cache_config = CacheConfig.from_dict(cache_data),
            display_config=DisplayConfig.from_dict(display_data),
            search_urls=SearchURLConfig.from_dict(search_urls_data),
        )

    @classmethod
    def get_default_config(cls) -> 'IPGeoConfig':
        """获取默认配置

        此方法用于与config_manager兼容，提供默认配置实例

        Returns:
            默认配置实例
        """
        return cls()
