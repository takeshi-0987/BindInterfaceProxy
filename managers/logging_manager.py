# -*- coding: utf-8 -*-
"""
Module: logging_manager.py
Author: Takeshi
Date: 2025-11-08

Description:
    日志管理器
"""

import logging
import logging.handlers
import sys

from typing import List

from managers.signals import LogSignals
from defaults.log_default import LogConfig, FileLogConfig


logger = logging.getLogger(__name__)



class LoggingManager:
    """日志管理器"""

    def __init__(self, log_signals: LogSignals):
        self.log_signals = log_signals
        self.is_initialized = False

    def setup_logging(self, log_config: LogConfig):
        """设置完整的日志系统"""
        # 清理重复的处理器
        self._cleanup_duplicate_handlers()

        # 设置根日志级别为DEBUG，让各处理器自己过滤
        logging.getLogger().setLevel(logging.DEBUG)

        # 设置各输出目标
        if log_config.console.enabled:
            self._setup_console_logging(log_config.console)

        if log_config.ui.enabled and self.log_signals:
            self._setup_ui_logging(log_config.ui)

        # 设置文件日志
        if log_config.file:
            self._setup_file_logging(log_config.file)

        self.is_initialized = True
        logger.info("日志系统初始化完成")

    def _setup_file_logging(self, file_configs: List[FileLogConfig]):
        """设置多文件日志"""
        import os

        for config in file_configs:
            if not config.enabled:
                continue

            self._setup_single_file(config)

    def _setup_single_file(self, config: FileLogConfig):
        """设置单个文件日志处理器"""
        import os

        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(config.filename)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                logger.debug(f"✅ 已创建日志目录: {log_dir}")

            # 创建 RotatingFileHandler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=config.filename,
                maxBytes=config.max_size_mb * 1024 * 1024,
                backupCount=config.backup_count,
                encoding='utf-8'
            )

            # 创建格式器
            formatter = logging.Formatter(
                config.format,
                datefmt=config.date_format
            )

            # 设置日志级别
            file_handler.setLevel(getattr(logging, config.level))
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)

            logger.info(f"✅ 文件日志已配置: {config.filename} (级别: {config.level})")

        except PermissionError as e:
            logger.error(f"❌ 权限错误，无法创建日志文件 {config.filename}: {e}")
        except Exception as e:
            logger.error(f"❌ 配置文件日志失败: {config.filename}, 错误: {e}")

    def _cleanup_duplicate_handlers(self):
        """清理重复的处理器"""
        root_logger = logging.getLogger()

        # 统计各类处理器的数量
        handler_types = {}
        for handler in root_logger.handlers[:]:
            handler_type = type(handler).__name__
            handler_types[handler_type] = handler_types.get(handler_type, 0) + 1

            # 移除重复的控制台处理器
            if (isinstance(handler, logging.StreamHandler) and
                handler_types[handler_type] > 1):
                root_logger.removeHandler(handler)
                logger.debug(f"移除重复的处理器: {handler_type}")

    def _setup_console_logging(self, console_config):
        """设置控制台日志"""

        # 创建基础格式
        formatter = logging.Formatter(
            console_config.format,
            datefmt=console_config.date_format
        )

        # 查找现有的控制台 StreamHandler
        existing_handler = self._find_existing_console_handler()

        if existing_handler:
            console_handler = existing_handler
            logger.debug("重用现有的控制台处理器")
        else:
            console_handler = logging.StreamHandler()
            logging.getLogger().addHandler(console_handler)
            logger.debug("创建新的控制台处理器")

        # 设置格式（根据颜色配置）
        if console_config.color_enabled:
            try:
                import colorlog
                color_formatter = colorlog.ColoredFormatter(
                    '%(log_color)s' + console_config.format,
                    datefmt=console_config.date_format,
                    log_colors=console_config.log_color,
                )
                console_handler.setFormatter(color_formatter)
            except ImportError:
                console_handler.setFormatter(formatter)
                logger.info("提示: 安装 colorlog 库可获得彩色控制台输出: pip install colorlog")
        else:
            console_handler.setFormatter(formatter)

        console_handler.setLevel(getattr(logging, console_config.level))
        logger.info(f"✅ 控制台日志已配置: 使用级别 {console_config.level}")

    def _find_existing_console_handler(self):
        """查找现有的控制台处理器"""
        root_logger = logging.getLogger()

        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                stream = getattr(handler, 'stream', None)
                if stream in (sys.stdout, sys.stderr) or stream is None:
                    return handler
        return None

    def _setup_ui_logging(self, ui_config):
        """设置界面日志"""

        # 创建基础格式
        formatter = logging.Formatter(
            ui_config.format,
            datefmt=ui_config.date_format
        )


        class QtLogHandler(logging.Handler):
            def __init__(self, signals, use_color=False):
                super().__init__()
                self.signals = signals
                self.use_color = use_color
                self.setLevel(getattr(logging, ui_config.level))

                self.color_map = ui_config.log_color

            def emit(self, record):
                try:
                    if self.use_color:
                        level_name = record.levelname
                        color = self.color_map.get(level_name, 'black')
                        msg = f'<span style="color: {color};">{self.format(record)}</span>'
                    else:
                        msg = self.format(record)

                    self.signals.new_log.emit(msg)
                except Exception as e:
                    logger.error(f"QtLogHandler.emit 错误: {e}")

        qt_handler = QtLogHandler(
            self.log_signals,
            use_color=ui_config.color_enabled
        )
        qt_handler.setFormatter(formatter)
        logging.getLogger().addHandler(qt_handler)
        logger.info(f"✅ 界面日志已配置: 使用级别 {ui_config.level}")

    def get_logger(self, name):
        """获取指定名称的日志器"""
        return logging.getLogger(name)

    def shutdown(self):
        """关闭日志系统"""
        logging.shutdown()
