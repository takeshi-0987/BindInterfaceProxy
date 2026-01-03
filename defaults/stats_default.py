# -*- coding: utf-8 -*-
"""
Module: stats_default.py
Author: Takeshi
Date: 2025-12-25

Description:
    统计管理默认配置
"""

from dataclasses import dataclass

@dataclass
class StatsConfig:
    """
    统计管理器配置类

    用于配置代理服务的统计功能，包括流量监控、连接记录、数据持久化等设置。
    统计功能可以帮助监控代理服务的运行状态、性能指标和使用情况。

    Attributes:
        enable_stats (bool): 统计功能主开关
            True: 启用统计功能，记录所有连接和流量数据
            False: 禁用统计功能，不记录任何数据
            默认: True（建议保持启用以监控服务状态）

        save_file (str): 统计数据保存文件路径
            存储每日统计数据的JSON文件路径
            支持相对路径或绝对路径
            目录不存在时会自动创建
            默认: 'data/stats.json'

        save_interval (int): 统计数据自动保存间隔（秒）
            定期将内存中的统计数据保存到文件
            设置太频繁会增加磁盘IO，设置太长可能导致数据丢失
            默认: 600秒（10分钟）

        max_days (int): 统计数据保留天数
            自动清理超过此天数的历史统计数据
            0或None表示不自动清理
            建议根据存储空间和审计需求设置
            默认: 30天

        update_interval (int): 监控数据更新间隔（秒）
            实时统计数据的刷新频率，影响速度计算的准确性
            设置太小会增加CPU负担，设置太大会降低实时性
            默认: 1秒

        history_size (int): 历史连接记录保留数量
            内存中保存的最近连接记录数量
            用于提供最近连接的详细信息和查询
            达到限制时会自动清理最旧的记录
            默认: 300条

    Methods:
        to_dict() -> dict:
            将配置转换为字典格式，便于序列化存储

        from_dict(config_dict: dict) -> 'StatsConfig':
            从字典创建配置实例，用于从配置文件或数据库加载配置

        get_default_config() -> 'StatsConfig':
            获取默认配置实例，用于与config_manager兼容

    Example:
        >>> # 创建自定义统计配置
        >>> config = StatsConfig(
        ...     enable_stats=True,
        ...     save_file='logs/proxy_stats.json',
        ...     save_interval=300,  # 5分钟保存一次
        ...     max_days=90,         # 保留90天历史
        ...     update_interval=2,   # 2秒更新一次实时数据
        ...     history_size=1000    # 保存1000条历史连接
        ... )
        >>>
        >>> # 转换为字典
        >>> config_dict = config.to_dict()
        >>>
        >>> # 从字典加载
        >>> loaded_config = StatsConfig.from_dict(config_dict)
        >>>
        >>> # 获取默认配置
        >>> default_config = StatsConfig.get_default_config()

    Note:
        1. 统计功能启用后会占用额外内存存储统计数据和连接记录
        2. 保存间隔和更新间隔需要平衡性能和实时性的需求
        3. 历史数据清理有助于控制内存和存储空间使用
        4. 统计数据文件采用JSON格式，便于分析和备份
    """

    enable_stats: bool = True              # 主开关
    save_file: str = 'data/stats.json'    # 保存文件
    save_interval: int = 600               # 保存间隔
    max_days: int = 30                    # 保留天数
    update_interval: int = 1              # 监控更新间隔
    history_size: int = 300               # 历史数据点数

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'StatsConfig':
        """从字典创建配置实例

        使用字典中的数据创建StatsConfig实例，字典中没有的字段使用默认值。
        这个方法特别适合从配置文件、数据库或其他序列化存储加载配置。

        Args:
            config_dict: 包含配置信息的字典

        Returns:
            StatsConfig: 新的配置实例

        Example:
            >>> config_data = {'enable_stats': False, 'save_interval': 120}
            >>> config = StatsConfig.from_dict(config_data)
            >>> print(config.enable_stats)  # False
            >>> print(config.save_interval) # 120
            >>> print(config.max_days)      # 30 (默认值)
        """
        default_instance = cls()

        return cls(
            enable_stats=config_dict.get('enable_stats', default_instance.enable_stats),
            save_file=config_dict.get('save_file', default_instance.save_file),
            save_interval=config_dict.get('save_interval', default_instance.save_interval),
            max_days=config_dict.get('max_days', default_instance.max_days),
            update_interval=config_dict.get('update_interval', default_instance.update_interval),
            history_size=config_dict.get('history_size', default_instance.history_size),
        )

    def to_dict(self) -> dict:
        """将配置转换为字典格式

        将StatsConfig实例的所有属性转换为字典，便于序列化存储或传输。
        适合保存到配置文件、数据库或发送到其他组件。

        Returns:
            dict: 包含所有配置项的字典

        Example:
            >>> config = StatsConfig()
            >>> config_dict = config.to_dict()
            >>> print(config_dict)
            {'enable_stats': True, 'save_file': 'data/stats.json', ...}
        """
        return {
            'enable_stats': self.enable_stats,
            'save_file': self.save_file,
            'save_interval': self.save_interval,
            'max_days': self.max_days,
            'update_interval': self.update_interval,
            'history_size': self.history_size,
        }

    @classmethod
    def get_default_config(cls) -> 'StatsConfig':
        """获取默认配置实例

        此方法用于与config_manager兼容，提供默认配置实例。
        返回的实例包含所有属性的默认值，适合作为新配置的基础。

        Returns:
            StatsConfig: 包含所有默认值的配置实例
        """
        return cls()
