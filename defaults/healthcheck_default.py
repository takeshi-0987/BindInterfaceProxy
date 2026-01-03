# -*- coding: utf-8 -*-
"""
Module: healthcheck_default.py
Author: Takeshi
Date: 2025-12-25

Description:
    健康检查默认配置
"""


from dataclasses import dataclass, field
from typing import List, Dict, Any, Literal


@dataclass
class HealthCheckConfig:
    """
    健康检查配置类

    用于配置代理服务的健康检查功能，通过定期访问测试网站来验证代理服务的可用性。

    Attributes:
        enabled (bool): 是否启用健康检查功能
            True: 启用定期健康检查
            False: 禁用健康检查
            默认: False（建议根据需求手动开启）

        check_interval (int): 健康检查间隔时间（秒）
            每隔多少秒执行一次健康检查
            设置太频繁会增加网络负担，设置太长会影响故障发现速度
            默认: 1800秒（30分钟）

        check_services (List[str]): 健康检查服务列表
            用于测试代理可用性的URL列表，按顺序尝试直到有一个成功
            支持HTTP和HTTPS协议
            默认: []

        check_timeout (int): 健康检查超时时间（秒）
            每个测试请求的最大等待时间
            超时会导致检查失败，计入失败记录
            默认: 5秒

        check_strategy (str): 健康检查策略
            串行或并行测试每个请求，有一个连接成功即通过
            默认: 串行

        parallel_pool_size (int): 并行最在连接池
            并行测试同时最大连接数
            默认: 3

    Methods:
        to_dict() -> Dict[str, Any]:
            将配置转换为字典格式，便于序列化和存储

        from_dict(data: Dict[str, Any]) -> 'HealthCheckConfig':
            从字典创建配置实例，用于从配置文件或数据库加载配置

        get_default_config() -> 'HealthCheckConfig':
            获取默认配置实例，用于与config_manager兼容

    Example:
        >>> # 创建自定义配置
        >>> config = HealthCheckConfig(
        ...     enabled=True,
        ...     check_interval=900,  # 15分钟检查一次
        ...     check_services=['https://www.baidu.com', 'https://www.qq.com'],
        ...     check_timeout=10
        ... )
        >>>
        >>> # 转换为字典
        >>> config_dict = config.to_dict()
        >>>
        >>> # 从字典加载
        >>> loaded_config = HealthCheckConfig.from_dict(config_dict)
        >>>
        >>> # 获取默认配置
        >>> default_config = HealthCheckConfig.get_default_config()

    Note:
        1. 健康检查会创建临时SOCKS5服务器进行测试，避免影响主服务
        2. 启用健康检查会增加系统资源消耗（线程、网络连接）
        3. 建议选择稳定的、可访问的测试网站
        4. 测试失败并不一定表示代理完全不可用，可能是网站暂时不可达
    """

    enabled: bool = False
    check_interval: int = 1800
    check_services: List = field(default_factory=lambda:
                        [

                        ]
    )
    check_timeout: int = 5
    check_strategy: Literal['serial', 'parallel'] = 'serial'  #是否启用并行检查
    parallel_pool_size: int = 3      # 新增：并行检查池大小（固定为3个池）


    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        返回的字典适合用于JSON序列化、存储到配置文件或数据库

        Returns:
            Dict[str, Any]: 包含所有配置项的字典

        Note:
            check_services列表会进行深拷贝，避免原始数据被意外修改
        """
        return {
            'enabled': self.enabled,
            'check_interval': self.check_interval,
            'check_services': self.check_services.copy(),
            'check_timeout': self.check_timeout,
            'check_strategy': self.check_strategy,      # 新增
            'parallel_pool_size': self.parallel_pool_size,   # 新增
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthCheckConfig':
        """从字典创建配置实例

        Args:
            data: 包含配置信息的字典，可以是从配置文件或数据库加载的数据

        Returns:
            HealthCheckConfig: 新的配置实例

        Note:
            如果字典中缺少某些字段，会使用默认值填充
        """
        return cls(
            enabled=data.get('enabled', False),
            check_interval=data.get('check_interval', 1800),
            check_services=data.get('check_services', []),
            check_timeout=data.get('check_timeout', 5),
            check_strategy=data.get('check_strategy', 'serial'),  # 新增
            parallel_pool_size=data.get('parallel_pool_size', 3),   # 新增
        )

    @classmethod
    def get_default_config(cls) -> 'HealthCheckConfig':
        """获取默认配置实例

        此方法用于与config_manager兼容，提供默认配置实例

        Returns:
            HealthCheckConfig: 包含所有默认值的配置实例
        """
        return cls()
