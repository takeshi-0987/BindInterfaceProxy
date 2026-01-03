# -*- coding: utf-8 -*-
"""
Module: config_manager.py
Author: Takeshi
Date: 2025-12-21

Description:
    配置管理器，中心化管理配置信息
"""


import json
from pathlib import Path
from typing import Dict, Any
import copy
import logging
from dataclasses import asdict, is_dataclass

logger = logging.getLogger(__name__)

# 导入所有配置类
from .dns_default import DNSConfig
from .healthcheck_default import HealthCheckConfig
from .ip_geo_default import IPGeoConfig
from .log_default import LogConfig
from .security_default import SecurityConfig
from .stats_default import StatsConfig
from .proxy_default import OutboundInterface, Socks5Proxy, HttpProxy
from .user_default import USER_CONFIG_FILE


class ConfigError(Exception):
    """配置相关错误"""
    pass


# 配置类型映射
_CONFIG_CLASSES = {
    'BIND_INTERFACE_CONFIG': OutboundInterface,
    'DNS_CONFIG': DNSConfig,
    'HEALTH_CHECK_CONFIG': HealthCheckConfig,
    'IP_GEO_CONFIG': IPGeoConfig,
    'LOG_CONFIG': LogConfig,
    'SECURITY_CONFIG': SecurityConfig,
    'STATS_CONFIG': StatsConfig,
}

# 列表配置类型
_LIST_CONFIG_CLASSES = {
    'SOCKS5_PROXY_CONFIG': Socks5Proxy,
    'HTTP_PROXY_CONFIG': HttpProxy,
}

# 配置保存顺序
CONFIG_SAVE_ORDER = [
    'BIND_INTERFACE_CONFIG',
    'SOCKS5_PROXY_CONFIG',
    'HTTP_PROXY_CONFIG',
    'DNS_CONFIG',
    'IP_GEO_CONFIG',
    'SECURITY_CONFIG',
    'STATS_CONFIG',
    'HEALTH_CHECK_CONFIG',
    'LOG_CONFIG'
]


class ConfigManager:
    """配置管理器 - 使用dataclass自带的转换方法

        统一的配置管理工具，支持所有系统配置的加载、保存、更新和验证。
        采用dataclass作为配置容器，提供类型安全的配置操作。

        Features:
            1. 统一的配置存储和加载
            2. 类型安全的配置访问
            3. 嵌套配置支持（dataclass嵌套）
            4. 列表配置支持
            5. 配置验证和完整性检查
            6. 默认配置回退
            7. 配置热更新

        Config Types:
            - 单个对象配置: 如 DNSConfig, SecurityConfig 等
            - 列表配置: 如 SOCKS5_PROXY_CONFIG, HTTP_PROXY_CONFIG
            - 嵌套配置: 支持多级dataclass嵌套

        Example:
            >>> from config.config_manager import get_config_manager
            >>> manager = get_config_manager()
            >>>
            >>> # 获取配置
            >>> dns_config = manager.get_config('DNS_CONFIG')
            >>>
            >>> # 更新配置
            >>> manager.update_config('LOG_CONFIG', 'console.level', 'INFO')
            >>>
            >>> # 保存配置
            >>> manager.save()
            >>>
            >>> # 批量操作
            >>> all_configs = manager.get_all_configs()
        """

    def __init__(self, config_path: str = USER_CONFIG_FILE):
        """初始化配置管理器

        Args:
            config_path: 配置文件路径，默认为用户配置路径
        """
        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._configs = {}
        self._load_configs()

    def _load_configs(self):
        """加载所有配置

        1. 首先设置所有配置的默认值
        2. 如果配置文件存在，从中加载用户配置
        3. 验证配置格式和完整性
        4. 记录加载结果

        Note:
            - 配置加载顺序按照 CONFIG_SAVE_ORDER
            - 缺少的配置项会使用默认值
            - 配置文件格式错误会记录错误但不中断
        """
        # 设置默认值
        for name, cls in _CONFIG_CLASSES.items():
            self._configs[name] = cls()

        for name in _LIST_CONFIG_CLASSES:
            self._configs[name] = []

        # 从文件加载
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)

                # 按保存顺序处理配置
                for config_name in CONFIG_SAVE_ORDER:
                    if config_name in file_data:
                        config_data = file_data[config_name]
                        self._apply_config_data(config_name, config_data)
                    else:
                        logger.warning(f"配置文件中缺少配置项: {config_name}")

                # 处理可能存在但不属于标准顺序的配置项
                for config_name, config_data in file_data.items():
                    if config_name not in CONFIG_SAVE_ORDER:
                        if config_name in self._configs:
                            self._apply_config_data(config_name, config_data)
                        else:
                            logger.warning(f"未知配置项: {config_name}")

                logger.info(f"配置加载成功: {self.config_path}")
            except Exception as e:
                logger.error(f"加载配置失败: {e}")

    def _apply_config_data(self, config_name: str, config_data: Any):
        """应用配置数据

        Args:
            config_name: 配置项名称
            config_data: 配置数据（字典或列表）

        Note:
            - 列表配置：每个元素通过from_dict转换
            - 对象配置：直接通过from_dict转换
            - 类型不匹配会记录警告
        """
        try:
            if config_name in _LIST_CONFIG_CLASSES:
                # 列表配置
                item_cls = _LIST_CONFIG_CLASSES[config_name]
                if isinstance(config_data, list):
                    self._configs[config_name] = [item_cls.from_dict(item)
                                                for item in config_data]
                else:
                    logger.warning(f"{config_name}: 期望列表，得到 {type(config_data)}")

            elif config_name in _CONFIG_CLASSES:
                # 普通配置
                config_cls = _CONFIG_CLASSES[config_name]
                if isinstance(config_data, dict):
                    self._configs[config_name] = config_cls.from_dict(config_data)
                else:
                    logger.warning(f"{config_name}: 期望字典，得到 {type(config_data)}")

        except Exception as e:
            logger.error(f"解析配置 {config_name} 失败: {e}")

    # ============== 核心公共接口 ==============

    def get_config(self, config_name: str) -> Any:
        """获取配置对象的深拷贝

        安全的配置获取方法，返回配置对象的深拷贝副本。
        防止外部代码修改内部配置状态。

        Args:
            config_name: 配置项名称，必须是预定义的配置键

        Returns:
            配置对象的深拷贝

        Raises:
            ConfigError: 当配置名不存在时

        Example:
            >>> manager = get_config_manager()
            >>> dns_config = manager.get_config('DNS_CONFIG')
            >>> print(dns_config.enable_cache)
            True
        """
        if config_name not in self._configs:
            raise ConfigError(f"未知配置: {config_name}")

        return copy.deepcopy(self._configs[config_name])

    def get_config_dict(self, config_name: str) -> Dict[str, Any]:
        """获取配置的字典表示

        将配置对象转换为字典格式，便于序列化或UI显示。
        支持嵌套dataclass、列表和字典的递归转换。

        Args:
            config_name: 配置项名称

        Returns:
            配置的字典表示

        Example:
            >>> manager = get_config_manager()
            >>> dns_dict = manager.get_config_dict('DNS_CONFIG')
            >>> print(json.dumps(dns_dict, indent=2))
        """
        config = self.get_config(config_name)
        return self._to_dict(config)

    def set_config(self, config_name: str, config: Any):
        """设置配置对象

        将配置对象设置为指定的值，使用深拷贝确保安全性。

        Args:
            config_name: 配置项名称
            config: 配置对象（必须是正确的类型）

        Raises:
            ConfigError: 当配置名不存在或类型不匹配时

        Note:
            此方法不自动保存，需要调用save()方法持久化
        """
        if config_name not in self._configs:
            raise ConfigError(f"未知配置: {config_name}")

        self._configs[config_name] = copy.deepcopy(config)

    def set_config_from_dict(self, config_name: str, config_dict: Any):
        """从字典设置配置

        从字典数据创建配置对象并设置。
        支持列表配置和对象配置。

        Args:
            config_name: 配置项名称
            config_dict: 配置字典数据

        Raises:
            ConfigError: 当数据类型不正确时（如列表配置需要列表）

        Example:
            >>> manager = get_config_manager()
            >>> new_dns = {'enable_cache': True, 'dns_servers': ['8.8.8.8']}
            >>> manager.set_config_from_dict('DNS_CONFIG', new_dns)
        """
        if config_name in _LIST_CONFIG_CLASSES:
            # 列表配置
            item_cls = _LIST_CONFIG_CLASSES[config_name]
            if isinstance(config_dict, list):
                config = [item_cls.from_dict(item) for item in config_dict]
                self.set_config(config_name, config)
            else:
                raise ConfigError(f"{config_name} 必须是列表")

        elif config_name in _CONFIG_CLASSES:
            # 普通配置
            config_cls = _CONFIG_CLASSES[config_name]
            if isinstance(config_dict, dict):
                config = config_cls.from_dict(config_dict)
                self.set_config(config_name, config)
            else:
                raise ConfigError(f"{config_name} 必须是字典")

    def _to_dict(self, obj: Any) -> Any:
        """安全地将任何对象转换为字典

        递归转换对象为字典格式，支持：
        1. 具有to_dict()方法的对象
        2. 列表和元组
        3. dataclass对象
        4. 普通字典
        5. 基本数据类型

        Args:
            obj: 要转换的对象

        Returns:
            转换后的字典或原始值

        Note:
            这是一个内部工具方法，确保配置序列化的稳定性
        """
        if obj is None:
            return None

        # 如果有to_dict方法，使用它
        if hasattr(obj, 'to_dict') and callable(obj.to_dict):
            return obj.to_dict()

        # 如果是列表，递归处理
        if isinstance(obj, list):
            return [self._to_dict(item) for item in obj]

        # 如果是dataclass，使用asdict
        if is_dataclass(obj):
            return asdict(obj)

        # 如果是字典，递归处理值
        if isinstance(obj, dict):
            return {key: self._to_dict(value) for key, value in obj.items()}

        # 其他类型直接返回
        return obj


    def update_config(self, config_name: str, field_path: str, value: Any) -> Any:
        """
        通用配置更新方法，支持复杂的嵌套路径访问和更新。

        此方法允许通过字符串路径精确访问和更新配置对象的任何字段，
        包括嵌套的 dataclass、列表和字典。

        Parameters
        ----------
        config_name : str
            配置项名称，必须是已定义的配置键之一：
            - 'BIND_INTERFACE_CONFIG'      # 出口网络接口配置
            - 'SOCKS5_PROXY_CONFIG'        # SOCKS5代理列表配置
            - 'HTTP_PROXY_CONFIG'          # HTTP代理列表配置
            - 'DNS_CONFIG'                  # DNS解析配置
            - 'LOG_CONFIG'                  # 日志配置
            - 'SECURITY_CONFIG'             # 安全配置
            - 'STATS_CONFIG'                # 统计配置
            - 'IP_GEO_CONFIG'              # IP地理位置配置
            - 'HEALTH_CHECK_CONFIG'        # 健康检查配置

        field_path : str
            字段路径字符串，支持多种访问格式：
            1. 直接字段访问: 'field_name'
            2. 嵌套对象访问: 'parent.child.grandchild'
            3. 列表索引访问: 'list_field[0].field' 或 'list_field.0.field'
            4. 字典键访问: 'dict_field.key_name'
            5. 混合访问: 'servers[0].settings.timeout'

            路径分隔符可以是点号(.)或方括号([])，支持混合使用。

        value : Any
            要设置的新值，类型必须与目标字段兼容。

        Returns
        -------
        Any
            设置成功后的值（返回传入的 value 参数）。

        Raises
        ------
        ConfigError
            1. 当 config_name 不存在时
            2. 当 field_path 无法解析时
            3. 当列表索引超出范围时
            4. 当尝试设置不存在的属性时

        Notes
        -----
        1. 此方法只更新内存中的配置，需要调用 save() 方法才能持久化到文件。
        2. 路径解析对大小写敏感。
        3. 列表索引从0开始。
        4. 使用 deepcopy 确保配置对象的安全性。

        Examples
        --------
        >>> from config.config_manager import get_config_manager
        >>> manager = get_config_manager()

        ============== 实际使用案例 ==============

        案例1: 更新出口网络配置
        >>> manager.update_config('BIND_INTERFACE_CONFIG', 'iface_name', 'eth0')
        'eth0'
        >>> manager.update_config('BIND_INTERFACE_CONFIG', 'ip', '192.168.1.100')
        '192.168.1.100'
        >>> manager.update_config('BIND_INTERFACE_CONFIG', 'port', 8080)
        8080

        案例2: 更新SOCKS5代理配置（列表操作）
        假设已经有一个SOCKS5代理在列表中：
        >>> manager.update_config('SOCKS5_PROXY_CONFIG', '[0].proxy_name', 'my_socks5_proxy')
        'my_socks5_proxy'
        >>> manager.update_config('SOCKS5_PROXY_CONFIG', '0.port', 1080)  # 两种索引写法都支持
        1080
        >>> manager.update_config('SOCKS5_PROXY_CONFIG', '[0].auth_enabled', True)
        True

        案例3: 更新DNS配置
        >>> manager.update_config('DNS_CONFIG', 'enable_cache', True)
        True
        >>> manager.update_config('DNS_CONFIG', 'dns_servers[0]', '8.8.8.8')
        '8.8.8.8'
        >>> manager.update_config('DNS_CONFIG', 'default_cache_ttl', 600)
        600
        >>> # 更新DNS服务器列表的第二个元素
        >>> manager.update_config('DNS_CONFIG', 'dns_servers.1', '1.1.1.1')
        '1.1.1.1'

        案例4: 更新日志配置（多层嵌套）
        >>> manager.update_config('LOG_CONFIG', 'console.enabled', True)
        True
        >>> manager.update_config('LOG_CONFIG', 'console.level', 'INFO')
        'INFO'
        >>> # 更新控制台日志颜色
        >>> manager.update_config('LOG_CONFIG', 'console.log_color.DEBUG', 'cyan')
        'cyan'
        >>> manager.update_config('LOG_CONFIG', 'console.log_color.INFO', 'green')
        'green'
        >>> # 更新UI日志配置
        >>> manager.update_config('LOG_CONFIG', 'ui.max_lines', 2000)
        2000
        >>> # 更新文件日志配置（列表操作）
        >>> manager.update_config('LOG_CONFIG', 'file[0].filename', 'logs/proxy.log')
        'logs/proxy.log'
        >>> manager.update_config('LOG_CONFIG', 'file[0].max_size_mb', 50)
        50

        案例5: 更新安全配置
        >>> manager.update_config('SECURITY_CONFIG', 'core.mode', 'mixed')
        'mixed'
        >>> manager.update_config('SECURITY_CONFIG', 'core.cleanup_interval', 600)
        600
        >>> manager.update_config('SECURITY_CONFIG', 'protocol.http_max_auth_failures', 5)
        5
        >>> manager.update_config('SECURITY_CONFIG', 'protocol.socks_ban_duration', 7200)
        7200

        案例6: 更新IP地理位置配置（复杂嵌套）
        >>> manager.update_config('IP_GEO_CONFIG', 'enabled', True)
        True
        >>> manager.update_config('IP_GEO_CONFIG', 'cache_config.enabled', True)
        True
        >>> manager.update_config('IP_GEO_CONFIG', 'cache_config.cache_size', 2000)
        2000
        >>> # 更新数据库配置（列表操作）
        >>> manager.update_config('IP_GEO_CONFIG', 'databases[0].enabled', False)
        False
        >>> manager.update_config('IP_GEO_CONFIG', 'databases[0].priority', 2)
        2

        案例7: 更新统计配置
        >>> manager.update_config('STATS_CONFIG', 'enable_stats', True)
        True
        >>> manager.update_config('STATS_CONFIG', 'save_interval', 30)
        30
        >>> manager.update_config('STATS_CONFIG', 'max_days', 90)
        90

        案例8: 更新健康检查配置
        >>> manager.update_config('HEALTH_CHECK_CONFIG', 'enabled', True)
        True
        >>> manager.update_config('HEALTH_CHECK_CONFIG', 'check_interval', 300)
        300
        >>> # 更新检查服务列表
        >>> manager.update_config('HEALTH_CHECK_CONFIG', 'check_services[0]', 'https://www.google.com')
        'https://www.google.com'

        案例9: 更新HTTP代理配置
        >>> manager.update_config('HTTP_PROXY_CONFIG', '[0].proxy_name', 'my_http_proxy')
        'my_http_proxy'
        >>> manager.update_config('HTTP_PROXY_CONFIG', '[0].use_https', True)
        True
        >>> manager.update_config('HTTP_PROXY_CONFIG', '[0].port', 8080)
        8080

        案例10: 混合复杂路径更新
        >>> # 假设有复杂的配置结构
        >>> manager.update_config('IP_GEO_CONFIG', 'online_apis[0].timeout', 5)
        5
        >>> manager.update_config('IP_GEO_CONFIG', 'online_apis[0].headers.User-Agent', 'MyApp/1.0')
        'MyApp/1.0'
        >>> manager.update_config('IP_GEO_CONFIG', 'query_config.strategy', 'online_first')
        'online_first'

        ============== 批量更新示例 ==============

        批量更新多个配置项：
        >>> updates = [
        ...     ('BIND_INTERFACE_CONFIG', 'ip', '192.168.1.200'),
        ...     ('DNS_CONFIG', 'enable_cache', True),
        ...     ('LOG_CONFIG', 'console.level', 'WARNING'),
        ...     ('SECURITY_CONFIG', 'core.cleanup_interval', 300),
        ...     ('SOCKS5_PROXY_CONFIG', '[0].auth_enabled', True),
        ... ]
        >>> for config_name, path, value in updates:
        ...     manager.update_config(config_name, path, value)
        ...     print(f"✓ 更新 {config_name}.{path} = {value}")

        ============== 错误处理示例 ==============

        >>> # 错误的配置名
        >>> try:
        ...     manager.update_config('UNKNOWN_CONFIG', 'field', 'value')
        ... except ConfigError as e:
        ...     print(f"错误: {e}")
        错误: 未知配置: UNKNOWN_CONFIG

        >>> # 错误的路径（字段不存在）
        >>> try:
        ...     manager.update_config('BIND_INTERFACE_CONFIG', 'non_existent_field', 'value')
        ... except ConfigError as e:
        ...     print(f"错误: {e}")
        错误: 路径错误: non_existent_field 不存在

        >>> # 索引超出范围
        >>> try:
        ...     manager.update_config('SOCKS5_PROXY_CONFIG', '[999].port', 1080)
        ... except ConfigError as e:
        ...     print(f"错误: {e}")
        错误: 列表索引 999 超出范围 (0-{len(list)-1})

        ============== 完整工作流程 ==============

        1. 获取配置管理器
        >>> manager = get_config_manager()

        2. 更新配置项
        >>> manager.update_config('BIND_INTERFACE_CONFIG', 'iface_name', 'eth0')
        >>> manager.update_config('SOCKS5_PROXY_CONFIG', '[0].port', 1080)
        >>> manager.update_config('LOG_CONFIG', 'console.level', 'INFO')

        3. 保存到文件
        >>> if manager.save():
        ...     print("配置保存成功")
        ... else:
        ...     print("配置保存失败")

        4. 重新加载验证
        >>> manager.reload()
        >>> saved_config = manager.get_config('BIND_INTERFACE_CONFIG')
        >>> print(f"重新加载后的配置: {saved_config.iface_name}")
        eth0
        """
        if config_name not in self._configs:
            raise ConfigError(f"未知配置: {config_name}")

        obj = self._configs[config_name]

        # 解析路径（支持 . 和 []）
        parts = []
        import re
        for part in re.split(r'\.|\[|\]', field_path):
            if part:  # 跳过空字符串
                parts.append(part)

        # 遍历到倒数第二个部分
        current = obj
        for i, part in enumerate(parts[:-1]):
            current = self._resolve_attribute(current, part)
            if current is None:
                raise ConfigError(f"路径错误: {'.'.join(parts[:i+1])} 不存在")

        # 设置最终值
        last_part = parts[-1]
        self._set_attribute(current, last_part, value)

        logger.debug(f"更新 {config_name}.{field_path} = {value}")
        return value


    def _resolve_attribute(self, obj: Any, attr_name: str) -> Any:
        """解析对象属性，支持列表、字典、dataclass

        内部工具方法，用于解析update_config中的路径访问。
        支持多种访问方式：
        1. 列表索引（数字字符串）
        2. dataclass/对象属性
        3. 字典键
        4. 混合访问

        Args:
            obj: 要解析的对象
            attr_name: 属性名称或索引

        Returns:
            解析出的属性值

        Raises:
            ConfigError: 当属性不存在或索引越界时
        """
        # 1. 列表索引
        if attr_name.isdigit() and isinstance(obj, (list, tuple)):
            index = int(attr_name)
            if 0 <= index < len(obj):
                return obj[index]
            else:
                raise ConfigError(f"列表索引 {index} 超出范围 (0-{len(obj)-1})")

        # 2. dataclass或对象属性
        if hasattr(obj, attr_name):
            return getattr(obj, attr_name)

        # 3. 字典键
        if isinstance(obj, dict) and attr_name in obj:
            return obj[attr_name]

        # 4. 尝试其他可能性
        if isinstance(obj, dict):
            # 尝试将attr_name转换为int再查找（对于类似'0'的键）
            try:
                index = int(attr_name)
                if index in obj:
                    return obj[index]
            except ValueError:
                pass

        raise ConfigError(f"属性不存在: {attr_name} (类型: {type(obj).__name__})")

    def _set_attribute(self, obj: Any, attr_name: str, value: Any):
        """设置对象属性，支持列表、字典、dataclass

        内部工具方法，用于update_config中的属性设置。
        支持多种设置方式。

        Args:
            obj: 要设置属性的对象
            attr_name: 属性名称或索引
            value: 要设置的值

        Raises:
            ConfigError: 当无法设置属性时
        """
        # 1. 列表索引
        if attr_name.isdigit() and isinstance(obj, (list, tuple)):
            index = int(attr_name)
            if 0 <= index < len(obj):
                obj[index] = value
                return
            else:
                raise ConfigError(f"列表索引 {index} 超出范围")

        # 2. dataclass或对象属性
        if hasattr(obj, attr_name):
            setattr(obj, attr_name, value)
            return

        # 3. 字典键
        if isinstance(obj, dict):
            obj[attr_name] = value
            return

        # 4. 尝试其他可能性
        if isinstance(obj, dict):
            try:
                index = int(attr_name)
                obj[index] = value
                return
            except ValueError:
                pass

        raise ConfigError(f"无法设置属性: {attr_name} (类型: {type(obj).__name__})")

    def save(self):
        """保存所有配置到文件，按照指定顺序

        将当前内存中的配置持久化到配置文件。
        保存顺序按照CONFIG_SAVE_ORDER，确保配置文件结构一致。

        Returns:
            bool: 保存是否成功

        Note:
            1. 会创建配置目录（如果不存在）
            2. 使用UTF-8编码和JSON格式
            3. 保存失败会记录错误但不抛出异常
            4. 非标准配置项也会被保存（但有警告）
        """
        try:
            save_data = {}

            # 按照指定顺序添加配置
            for name in CONFIG_SAVE_ORDER:
                if name in self._configs:
                    config = self._configs[name]
                    save_data[name] = self._to_dict(config)
                else:
                    logger.warning(f"保存时缺少配置项: {name}，使用默认值")
                    save_data[name] = self._to_dict(self.get_default_config(name))

            # 添加可能存在的其他配置项（虽然不应该有）
            for name in self._configs:
                if name not in CONFIG_SAVE_ORDER:
                    logger.warning(f"保存非标准配置项: {name}")
                    config = self._configs[name]
                    save_data[name] = self._to_dict(config)

            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=4)

            logger.info(f"配置已保存: {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def reload(self):
        """重新加载配置

        清空当前配置并从配置文件重新加载。
        用于配置变更后重新应用文件中的配置。

        Returns:
            bool: 总是返回True

        Example:
            >>> # 外部修改了配置文件
            >>> manager.reload()
            >>> # 现在使用的是文件中的最新配置
        """
        self._configs.clear()
        self._load_configs()
        return True

    # ============== 批量操作 ==============

    def get_all_configs(self) -> Dict[str, Any]:
        """获取所有配置对象，按照指定顺序

        返回所有配置的深拷贝副本，按照标准顺序排列。
        适用于备份或批量处理配置。

        Returns:
            Dict[str, Any]: 配置名到配置对象的映射

        Example:
            >>> manager = get_config_manager()
            >>> all_configs = manager.get_all_configs()
            >>> for name, config in all_configs.items():
            >>>     print(f"{name}: {type(config).__name__}")
        """
        result = {}
        for name in CONFIG_SAVE_ORDER:
            if name in self._configs:
                result[name] = self.get_config(name)
        return result

    def get_all_dicts(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置的字典形式，按照指定顺序

        返回所有配置的字典表示，适合用于JSON序列化或UI展示。
        自动处理转换错误，返回空字典而不是抛出异常。

        Returns:
            Dict[str, Dict[str, Any]]: 配置名到配置字典的映射
        """
        result = {}
        for name in CONFIG_SAVE_ORDER:
            if name in self._configs:
                try:
                    result[name] = self.get_config_dict(name)
                except Exception as e:
                    logger.error(f"获取配置 {name} 的字典失败: {e}")
                    result[name] = {}
        return result

    def set_all_configs(self, configs: Dict[str, Any]):
        """批量设置配置对象

        批量更新多个配置项，提高效率。
        只更新已存在的配置项，忽略不存在的配置名。

        Args:
            configs: 配置名到配置对象的映射

        Example:
            >>> manager = get_config_manager()
            >>> updates = {
            >>>     'DNS_CONFIG': new_dns_config,
            >>>     'LOG_CONFIG': new_log_config
            >>> }
            >>> manager.set_all_configs(updates)
        """
        for name, config in configs.items():
            if name in self._configs:
                self.set_config(name, config)

    def set_all_from_dicts(self, config_dicts: Dict[str, Dict[str, Any]]):
        """从字典批量设置配置

        从字典数据批量更新配置，适用于从文件或其他系统加载配置。

        Args:
            config_dicts: 配置名到配置字典的映射
        """
        for name, config_dict in config_dicts.items():
            if name in self._configs:
                self.set_config_from_dict(name, config_dict)

    # ============== 辅助方法 ==============

    def get_default_config(self, config_name: str) -> Any:
        """获取默认配置

        返回指定配置项的默认值，用于重置或初始化配置。

        Args:
            config_name: 配置项名称

        Returns:
            默认配置对象或空列表

        Raises:
            ConfigError: 当配置名不存在时，
            'BIND_INTERFACE_CONFIG'， 'SOCKS5_PROXY_CONFIG'，'HTTP_PROXY_CONFIG'不能使用默认值
        """
        if config_name in _CONFIG_CLASSES and config_name != 'BIND_INTERFACE_CONFIG':
            return _CONFIG_CLASSES[config_name].get_default_config()

        elif config_name in _LIST_CONFIG_CLASSES:
            raise ConfigError(f"{config_name}不能使用默认配置")
        elif config_name == 'BIND_INTERFACE_CONFIG':
            raise ConfigError(f"{config_name}不能使用默认配置")
        raise ConfigError(f"未知配置: {config_name}")

    def get_default_dict(self, config_name: str) -> Dict[str, Any]:
        """获取默认配置字典

        返回默认配置的字典表示，便于比较或显示默认值。

        Args:
            config_name: 配置项名称

        Returns:
            默认配置的字典表示
        """
        default_config = self.get_default_config(config_name)
        return self._to_dict(default_config)

    def validate_completeness(self) -> tuple[bool, str]:
        """验证配置完整性

        检查核心配置是否完整，确保系统可以正常运行。
        主要验证：
        1. 出口网络配置是否有效
        2. 至少有一个代理配置（SOCKS5或HTTP）

        Returns:
            tuple[bool, str]: (是否完整, 错误信息或空字符串)

        Example:
            >>> is_complete, error = manager.validate_completeness()
            >>> if not is_complete:
            >>>     print(f"配置不完整: {error}")
        """
        try:
            bind_config = self.get_config('BIND_INTERFACE_CONFIG')
            socks5 = self.get_config('SOCKS5_PROXY_CONFIG')
            http = self.get_config('HTTP_PROXY_CONFIG')

            if not bind_config or (not bind_config.iface_name and not bind_config.ip):
                if not socks5 and not http:
                    return False, "出口网络以及代理（SOCKS5或HTTP）"
                else:
                    return False, "出口网络"

            if not socks5 and not http:
                return False, "代理（SOCKS5或HTTP）"

            return True, ""
        except Exception:
            return False, "配置获取失败"

    def has_auth_config(self) -> bool:
        """检查是否有认证配置

        检查是否有任何代理启用了身份验证。
        用于决定是否需要显示认证相关的UI元素。

        Returns:
            bool: 是否有启用了认证的代理
        """
        try:
            for proxy in self.get_config('SOCKS5_PROXY_CONFIG') or []:
                if hasattr(proxy, 'auth_enabled') and proxy.auth_enabled:
                    return True

            for proxy in self.get_config('HTTP_PROXY_CONFIG') or []:
                if hasattr(proxy, 'auth_enabled') and proxy.auth_enabled:
                    return True
        except Exception:
            pass

        return False

    # def reset_to_defaults(self):
    #     """重置为默认配置

    #     清空所有用户配置，恢复为系统默认值。
    #     不自动保存，需要调用save()来持久化默认配置。

    #     Example:
    #         >>> manager.reset_to_defaults()
    #         >>> manager.save()  # 将默认配置保存到文件
    #     """
    #     self._configs.clear()
    #     self._load_configs()


# ============== 全局单例 ==============

_config_manager_instance = None

def get_config_manager(config_path: str = USER_CONFIG_FILE) -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager(config_path)
    return _config_manager_instance
