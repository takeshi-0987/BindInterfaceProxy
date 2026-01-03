# -*- coding: utf-8 -*-
"""
Module: log_default.py
Author: Takeshi
Date: 2025-12-25

Description:
    日志文件配置类
"""


from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ConsoleLogConfig:
    """
    控制台日志配置

    配置控制台（终端）输出的日志格式和行为。

    Attributes:
        enabled (bool): 是否启用控制台日志输出
            True: 在终端显示日志
            False: 不在终端显示日志
            默认: True

        level (str): 控制台日志级别
            只显示该级别及以上的日志
            可选值: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
            默认: 'DEBUG'

        format (str): 日志格式字符串
            使用Python logging模块的标准格式化语法
            常用占位符:
                %(asctime)s: 时间
                %(name)s: 日志器名称
                %(levelname)s: 日志级别
                %(message)s: 日志消息
                %(filename)s: 文件名
                %(funcName)s: 函数名
                %(lineno)d: 行号
            默认: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        date_format (str): 时间格式
            Python datetime格式化语法
            默认: '%m-%d %H:%M:%S' (月-日 时:分:秒)

        color_enabled (bool): 是否启用彩色输出
            True: 根据不同日志级别显示不同颜色
            False: 使用普通文本输出
            依赖colorlog库，未安装时自动降级为普通格式
            默认: True

        log_color (Dict[str, str]): 各级别的颜色配置
            键: 日志级别名称
            值: colorlog支持的颜色字符串
            支持的级别: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
            默认: {
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }

    Example:
        >>> # 创建简单的控制台配置
        >>> config = ConsoleLogConfig(
        ...     enabled=True,
        ...     level='INFO',
        ...     color_enabled=True
        ... )
    """

    enabled: bool = True
    level: str = 'DEBUG'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format: str = '%m-%d %H:%M:%S'
    color_enabled: bool = True
    log_color: Dict[str, str] = field(default_factory=lambda: {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    })

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有配置项的字典
        """
        return {
            'enabled': self.enabled,
            'level': self.level,
            'format': self.format,
            'date_format': self.date_format,
            'color_enabled': self.color_enabled,
            'log_color': self.log_color.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConsoleLogConfig':
        """从字典创建配置实例

        Args:
            data: 包含配置信息的字典

        Returns:
            ConsoleLogConfig: 新的配置实例
        """
        return cls(
            enabled=data.get('enabled', True),
            level=data.get('level', 'DEBUG'),
            format=data.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            date_format=data.get('date_format', '%m-%d %H:%M:%S'),
            color_enabled=data.get('color_enabled', True),
            log_color=data.get('log_color', {})
        )


@dataclass
class UILogConfig:
    """
    界面日志配置

    配置图形用户界面中的日志显示格式和行为。
    主要用于Qt等GUI框架的日志显示。

    Attributes:
        enabled (bool): 是否启用界面日志输出
            True: 在GUI界面中显示日志
            False: 不在GUI界面中显示日志
            默认: True

        level (str): 界面日志级别
            只显示该级别及以上的日志
            通常比控制台级别高，避免界面信息过载
            可选值: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
            默认: 'INFO'

        format (str): 日志格式字符串
            通常比控制台格式简洁
            默认: '%(asctime)s [%(levelname)s] %(message)s'

        date_format (str): 时间格式
            默认: '%m-%d %H:%M:%S' (月-日 时:分:秒)

        max_lines (int): 最大显示行数
            界面日志控件中保留的最大日志行数
            达到限制后自动删除最旧的行
            默认: 1000行

        auto_scroll (bool): 是否自动滚动
            True: 新日志到达时自动滚动到底部
            False: 保持当前滚动位置
            默认: True

        color_enabled (bool): 是否启用彩色显示
            True: 在HTML/富文本中使用颜色
            False: 使用纯文本
            默认: True

        log_color (Dict[str, str]): 各级别的颜色配置
            键: 日志级别名称
            值: HTML颜色名称或十六进制颜色值
            默认: {
                'DEBUG': 'gray',
                'INFO': 'green',
                'WARNING': 'orange',
                'ERROR': 'red',
                'CRITICAL': 'darkred',
            }
    """

    enabled: bool = True
    level: str = 'INFO'
    format: str = '%(asctime)s [%(levelname)s] %(message)s'
    date_format: str = '%m-%d %H:%M:%S'
    max_lines: int = 1000
    auto_scroll: bool = True
    color_enabled: bool = True
    log_color: Dict[str, str] = field(default_factory=lambda: {
        'DEBUG': 'gray',
        'INFO': 'green',
        'WARNING': 'orange',
        'ERROR': 'red',
        'CRITICAL': 'darkred',
    })

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有配置项的字典
        """
        return {
            'enabled': self.enabled,
            'level': self.level,
            'format': self.format,
            'date_format': self.date_format,
            'max_lines': self.max_lines,
            'auto_scroll': self.auto_scroll,
            'color_enabled': self.color_enabled,
            'log_color': self.log_color.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UILogConfig':
        """从字典创建配置实例

        Args:
            data: 包含配置信息的字典

        Returns:
            UILogConfig: 新的配置实例
        """
        return cls(
            enabled=data.get('enabled', True),
            level=data.get('level', 'INFO'),
            format=data.get('format', '%(asctime)s [%(levelname)s] %(message)s'),
            date_format=data.get('date_format', '%m-%d %H:%M:%S'),
            max_lines=data.get('max_lines', 1000),
            auto_scroll=data.get('auto_scroll', True),
            color_enabled=data.get('color_enabled', True),
            log_color=data.get('log_color', {})
        )


@dataclass
class FileLogConfig:
    """
    文件日志配置

    配置日志文件的格式、轮转策略和存储设置。
    支持多文件配置，不同级别可以记录到不同文件。

    Attributes:
        enabled (bool): 是否启用文件日志
            True: 启用此文件日志配置
            False: 忽略此配置
            默认: True

        level (str): 文件日志级别
            记录该级别及以上的日志到此文件
            可选值: 'DEBUG', 'INFO', 'WARNING', 'ERROR',


        format (str): 日志格式字符串
            通常包含详细信息，便于后续分析
            默认: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        date_format (str): 时间格式
            包含年份，便于归档和查找
            默认: '%Y-%m-%d %H:%M:%S'

        filename (str): 日志文件路径
            相对或绝对路径
            支持目录自动创建
            默认: 'logs/proxy_server_info.log'

        max_size_mb (int): 单个文件最大大小（MB）
            达到此大小时触发日志轮转
            默认: 10 MB

        backup_count (int): 备份文件数量
            保留的历史日志文件数量
            达到数量限制时删除最旧的文件
            默认: 3个
    """

    enabled: bool = True
    level: str = 'INFO'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format: str = '%Y-%m-%d %H:%M:%S'
    filename: str = 'logs/proxy_server_info.log'
    max_size_mb: int = 10
    backup_count: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有配置项的字典
        """
        return {
            'enabled': self.enabled,
            'level': self.level,
            'format': self.format,
            'date_format': self.date_format,
            'filename': self.filename,
            'max_size_mb': self.max_size_mb,
            'backup_count': self.backup_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileLogConfig':
        """从字典创建配置实例

        Args:
            data: 包含配置信息的字典

        Returns:
            FileLogConfig: 新的配置实例
        """
        return cls(
            enabled=data.get('enabled', True),
            level=data.get('level', 'INFO'),
            format=data.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            date_format=data.get('date_format', '%Y-%m-%d %H:%M:%S'),
            filename=data.get('filename', 'logs/proxy_server_info.log'),
            max_size_mb=data.get('max_size_mb', 10),
            backup_count=data.get('backup_count', 3)
        )


@dataclass
class LogConfig:
    """
    完整的日志配置管理器

    整合控制台、界面和文件日志配置，提供统一的日志管理接口。
    支持多目标、多级别的灵活日志配置。

    Attributes:
        console (ConsoleLogConfig): 控制台日志配置
            默认: ConsoleLogConfig()

        ui (UILogConfig): 界面日志配置
            默认: UILogConfig()

        file (List[FileLogConfig]): 文件日志配置列表
            支持配置多个日志文件，不同级别/用途分别记录
            默认: 空列表，通过get_default_config()获取推荐配置

    Methods:
        to_dict() -> Dict[str, Any]:
            将完整配置转换为嵌套字典格式

        from_dict(data: Dict[str, Any]) -> 'LogConfig':
            从字典创建完整配置实例

        get_default_config() -> 'LogConfig':
            获取推荐的默认配置

    Example:
        >>> # 使用默认配置
        >>> default_config = LogConfig.get_default_config()
        >>>
        >>> # 创建自定义配置
        >>> config = LogConfig(
        ...     console=ConsoleLogConfig(enabled=True, level='INFO'),
        ...     ui=UILogConfig(enabled=True, level='WARNING'),
        ...     file=[
        ...         FileLogConfig(
        ...             enabled=True,
        ...             filename='logs/app_info.log',
        ...             level='INFO',
        ...             max_size_mb=50
        ...         ),
        ...         FileLogConfig(
        ...             enabled=True,
        ...             filename='logs/app_error.log',
        ...             level='ERROR',
        ...             backup_count=10
        ...         )
        ...     ]
        ... )
        >>>
        >>> # 转换为字典保存
        >>> config_dict = config.to_dict()
    """

    console: ConsoleLogConfig = field(default_factory=ConsoleLogConfig)
    ui: UILogConfig = field(default_factory=UILogConfig)
    file: List[FileLogConfig] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """将完整配置转换为嵌套字典格式

        Returns:
            Dict[str, Any]: 包含所有子配置的嵌套字典
        """
        return {
            'console': self.console.to_dict(),
            'ui': self.ui.to_dict(),
            'file': [f.to_dict() for f in self.file]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogConfig':
        """从字典创建完整配置实例

        Args:
            data: 包含嵌套配置信息的字典

        Returns:
            LogConfig: 新的完整配置实例
        """
        console_data = data.get('console', {})
        ui_data = data.get('ui', {})
        file_data = data.get('file', [])

        file_configs = []
        for file_item in file_data:
            file_configs.append(FileLogConfig.from_dict(file_item))

        return cls(
            console=ConsoleLogConfig.from_dict(console_data),
            ui=UILogConfig.from_dict(ui_data),
            file=file_configs
        )

    @classmethod
    def get_default_config(cls) -> 'LogConfig':
        """获取推荐的默认配置
        """
        return cls(
            console=ConsoleLogConfig(),
            ui=UILogConfig(),
            file=[
                FileLogConfig(
                    enabled=False,
                    level='DEBUG',
                    filename='logs/proxy_server_debug.log',
                    max_size_mb=50,
                    backup_count=1,
                ),
                FileLogConfig(
                    enabled=True,
                    level='INFO',
                    filename='logs/proxy_server_info.log',
                    max_size_mb=20,
                    backup_count=3,
                ),
                FileLogConfig(
                    enabled=True,
                    level='WARNING',
                    filename='logs/proxy_server_warning.log',
                    max_size_mb=5,
                    backup_count=5,
                ),
                FileLogConfig(
                    enabled=False,  # 默认关闭，需要时开启
                    level='ERROR',
                    filename='logs/proxy_server_error.log',
                    max_size_mb=2,
                    backup_count=10,
                ),
            ]
        )
