# -*- coding: utf-8 -*-
"""
Module: health_checker.py
Author: Takeshi
Date: 2025-11-08

Description:
    健康检查模块
"""
import logging
import requests
import threading
import concurrent.futures
import urllib3
import time

from datetime import datetime
from typing import Dict, Tuple, Any

from utils.interface_utils import NetworkInterface
from .signals import StatusSignals
from defaults.healthcheck_default import HealthCheckConfig

logger = logging.getLogger(__name__)

# 禁用所有InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HealthChecker:
    def __init__(self, config: HealthCheckConfig,
                 sock5_bind_interface: NetworkInterface,
                 dns_resolver,
                 ip_geo_manager,
                 signals: StatusSignals):

        self.config = config

        # 临时SOCKS5服务器
        self._sock5_bind_interface = sock5_bind_interface
        self._dns_resolver = dns_resolver
        self._ip_geo_manager = ip_geo_manager
        self._temp_socks5_server = None

        self.signals = signals

        # 状态变量
        self.is_checking = False
        self.health_status = "unknown"
        self.last_check_time = None
        self.last_success_time = None
        self.last_failure_time = None
        self.last_failure_reason = ""
        self.last_error = ""

        # 存储详细的检查结果
        self.all_connections_status = {}      # 存储每个连接的状态（布尔值）
        self.all_connections_details = {}     # 存储每个连接的详细信息
        self.last_success_url = None          # 存储最后成功的URL
        self.last_success_status_code = None  # 存储最后成功的状态码

        # 检查控制
        self.check_timer = None
        self.session = None
        self._stop_event = threading.Event()

        # 线程池执行器（用于并行检查）
        self._executor = None

    def first_start_and_check(self):
        """首次运行并执行健康检查"""
        if self.config.enabled:
            self.start()
            self._perform_check()
        else:
            logger.info("未启动健康检查")

    def start(self):
        """启动健康检查"""
        self._stop_event.clear()
        self._schedule_next_check()
        logger.info("启动健康检查")

    def stop(self):
        """停止健康检查"""
        self._stop_event.set()
        if self.check_timer:
            self.check_timer.cancel()
        if self.session:
            self.session.close()
        # 关闭执行器
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

        self.health_status = "unknown"
        self.signals.health_changed.emit(self.health_status)
        logger.info("停止健康检查")

    def _schedule_next_check(self):
        """安排下一次检查"""
        if self._stop_event.is_set():
            return

        if self.check_timer:
            self.check_timer.cancel()

        self.check_timer = threading.Timer(
            self.config.check_interval,
            self._perform_check
        )
        self.check_timer.daemon = True
        self.check_timer.start()

    def _perform_check(self):
        """执行自动健康检查"""
        if self._stop_event.is_set():
            return

        if self.is_checking:
            return

        self.is_checking = True
        self.health_status = "checking"
        self.last_check_time = datetime.now()
        self.signals.health_changed.emit(self.health_status)

        logger.info(f"🔍 开始自动健康检查...")

        try:
            # 创建临时SOCKS5服务器用于健康检查
            self._setup_temp_socks5_server()

            # 根据配置选择检查模式
            if self.config.check_strategy == 'serial':
                success, details = self._perform_serial_check_with_details()
            else:
                success, details = self._perform_parallel_check_with_details()

            # 更新状态
            if success:
                self.health_status = "healthy"
                self.last_error = ""
                self.last_success_time = datetime.now()

                # 保存成功的URL和状态码
                for url, detail in details.items():
                    if isinstance(detail, dict) and detail.get('success'):
                        self.last_success_url = url
                        self.last_success_status_code = detail.get('status_code')
                        break

                self.signals.health_changed.emit(self.health_status)
                logger.info(f"✅ 自动健康检查成功 - {self.last_success_url} ({self.last_success_status_code})")
            else:
                self.health_status = "unhealthy"
                self.last_error = f"所有测试url都不可访问"
                self.last_failure_time = datetime.now()
                self.last_failure_reason = self.last_error
                self.signals.health_changed.emit(self.health_status)
                logger.warning(f"❌ 自动健康检查失败 - 所有测试url都不可访问")

        except Exception as e:
            self.health_status = "unhealthy"
            self.last_error = str(e)
            self.last_failure_time = datetime.now()
            self.last_failure_reason = self.last_error
            self.signals.health_changed.emit(self.health_status)
            logger.error(f"💥 自动健康检查异常 - {e}")

        finally:
            # 清理临时服务器
            self._cleanup_temp_socks5_server()
            self.last_check_time = datetime.now()
            self.is_checking = False
            self.signals.health_changed.emit(self.health_status)
            self._schedule_next_check()

    def _setup_temp_socks5_server(self):
        """设置临时SOCKS5服务器"""
        from servers.socks5_proxy_server import SOCKS5ProxyServer
        # 创建临时SOCKS5服务器
        self._temp_socks5_server = SOCKS5ProxyServer(
            name="健康检查临时服务器",
            listen_host='127.0.0.1',
            listen_port=0,    # 让系统随机安排一个可用端口
            egress_ip=self._sock5_bind_interface.ip,
            egress_port=self._sock5_bind_interface.port,
            dns_resolver=self._dns_resolver,
            ip_geo_manager=self._ip_geo_manager,
            health_check_mode=True,
        )

        # 在后台线程启动服务器
        server_thread = threading.Thread(
            target=self._temp_socks5_server.start,
            daemon=True
        )
        server_thread.start()

        # 等待并获取端口
        time.sleep(0.5)
        self._temp_socks5_port = self._temp_socks5_server.get_listen_port()
        logger.debug(f"启动临时SOCKS5服务器: 127.0.0.1:{self._temp_socks5_port}")

    def _cleanup_temp_socks5_server(self):
        """清理临时SOCKS5服务器"""
        if self._temp_socks5_server:
            try:
                self._temp_socks5_server.stop()
                self._temp_socks5_server = None
                logger.debug("临时SOCKS5服务器已清理")
            except Exception as e:
                logger.debug(f"清理临时服务器时出错: {e}")

    def _check_url_with_status_code(self, test_url: str, timeout: int) -> Tuple[bool, Dict[str, Any]]:
        """检查URL并返回状态码和详细信息

        Returns:
            Tuple[bool, Dict]: (是否成功, 详细信息)
        """
        # socks5h 会将DNS解析交给代理服务器，从而发送域名信息
        proxy_url = f"socks5h://127.0.0.1:{self._temp_socks5_port}"
        proxies = {'http': proxy_url, 'https': proxy_url}

        # 如果URL没有协议头，自动添加https://
        if not test_url.startswith(('http://', 'https://')):
            request_url = f'https://{test_url}'
            logger.debug(f"URL标准化: '{test_url}' -> '{request_url}'")
        else:
            request_url = test_url

        try:
            # 创建临时Session
            temp_session = requests.Session()
            temp_session.verify = False
            temp_session.trust_env = False

            # 设置User-Agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            start_time = time.time()

            # 发送请求 - 使用标准化后的URL
            response = temp_session.get(
                request_url,
                timeout=timeout,
                proxies=proxies,
                headers=headers,
                allow_redirects=True  # 允许重定向
            )

            elapsed_time = time.time() - start_time

            # 获取状态码
            status_code = response.status_code

            # 判断是否成功（2xx和3xx都算成功）
            success = 200 <= status_code < 400

            # 构建详细信息 - 保持原有key不变
            detail = {
                'success': success,
                'status_code': status_code,
                'response_time': round(elapsed_time * 1000, 2),  # 毫秒
                'url': request_url,
                'final_url': response.url,  # 最终URL（考虑重定向）
                'reason': response.reason if hasattr(response, 'reason') else ''
            }

            logger.debug(f"{request_url} 状态码: {status_code}, 响应时间: {detail['response_time']}ms")
            temp_session.close()

            return success, detail

        except requests.exceptions.Timeout:
            logger.debug(f"{request_url} 请求超时")
            return False, {
                'success': False,
                'status_code': None,
                'response_time': timeout * 1000,
                'url': request_url,
                'error': 'timeout'
            }
        except requests.exceptions.SSLError as e:
            logger.debug(f"{request_url} SSL错误: {e}")
            return False, {
                'success': False,
                'status_code': None,
                'response_time': None,
                'url': request_url,
                'error': 'ssl_error'
            }
        except requests.exceptions.ConnectionError as e:
            logger.debug(f"{request_url} 连接错误: {e}")
            return False, {
                'success': False,
                'status_code': None,
                'response_time': None,
                'url': request_url,
                'error': 'connection_error'
            }
        except Exception as e:
            logger.debug(f"{request_url} 检查异常: {e}")
            return False, {
                'success': False,
                'status_code': None,
                'response_time': None,
                'url': request_url,
                'error': str(e)[:100]
            }

    def _perform_serial_check_with_details(self) -> Tuple[bool, Dict[str, Dict]]:
        """执行串行检查并返回详细结果"""
        if not self._temp_socks5_server:
            return False, {}

        all_details = {}
        has_success = False

        for test_url in self.config.check_services:
            success, detail = self._check_url_with_status_code(test_url, self.config.check_timeout)
            all_details[test_url] = detail

            if success:
                if not has_success:
                    has_success = True  # 首次成功时设置标志
                logger.debug(f"✅ 串行检查: {test_url} 成功 ({detail['status_code']})")
            else:
                status_info = f"状态码: {detail['status_code']}" if detail['status_code'] else f"错误: {detail.get('error', 'unknown')}"
                logger.debug(f"❌ 串行检查: {test_url} 失败 ({status_info})")

        return has_success, all_details

    def _perform_parallel_check_with_details(self) -> Tuple[bool, Dict[str, Dict]]:
        """执行并行检查并返回详细结果"""
        if not self._temp_socks5_server:
            return False, {}

        try:
            # 创建线程池
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=min(self.config.parallel_pool_size, len(self.config.check_services))
            )

            # 提交所有检查任务
            future_to_url = {}
            for test_url in self.config.check_services:
                future = self._executor.submit(
                    self._check_url_with_status_code,
                    test_url,
                    self.config.check_timeout
                )
                future_to_url[future] = test_url

            # 收集所有结果
            all_details = {}
            has_success = False

            # 设置超时
            timeout = self.config.check_timeout + 2

            for future in concurrent.futures.as_completed(future_to_url, timeout=timeout):
                test_url = future_to_url[future]
                try:
                    success, detail = future.result()
                    all_details[test_url] = detail

                    if success:
                        if not has_success:
                            has_success = True  # 首次成功时设置标志
                        logger.debug(f"✅ 并行检查: {test_url} 成功 ({detail['status_code']})")
                    else:
                        status_info = f"状态码: {detail['status_code']}" if detail['status_code'] else f"错误: {detail.get('error', 'unknown')}"
                        logger.debug(f"❌ 并行检查: {test_url} 失败 ({status_info})")

                except Exception as e:
                    logger.debug(f"⚠️  并行检查: {test_url} 异常: {e}")
                    all_details[test_url] = {
                        'success': False,
                        'status_code': None,
                        'error': str(e)
                    }

        except Exception as e:
            logger.error(f"并行检查异常: {e}")
            return False, {}
        finally:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None

        return has_success, all_details

    def check_all_connections_status(self) -> Dict[str, Dict]:
        """检查所有连接的状态 - 手动调用，使用并行逻辑

        Returns:
            Dict[str, Dict]: 每个URL的详细结果字典
        """
        if self.is_checking:
            return {}

        self.is_checking = True
        self.health_status = "checking"
        self.signals.health_changed.emit(self.health_status)
        logger.info("手动检查所有连接状态（并行）...")


        try:
            self._setup_temp_socks5_server()

            # 使用线程池并行测试所有连接
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(self.config.parallel_pool_size, len(self.config.check_services))
            ) as executor:
                # 提交所有检查任务
                future_to_url = {
                    executor.submit(self._check_url_with_status_code, url, self.config.check_timeout): url
                    for url in self.config.check_services
                }

                # 没有成功是'unhealthy'
                self.health_status = 'unhealthy'
                # 收集所有结果
                all_details = {}
                for future in concurrent.futures.as_completed(future_to_url, timeout=self.config.check_timeout + 5):
                    url = future_to_url[future]
                    try:
                        success, detail = future.result()
                        all_details[url] = detail
                        if success:
                            # 有成功则 'healthy'
                            self.health_status = 'healthy'
                        logger.debug(f"连接状态检查: {url} = {success}, 状态码: {detail.get('status_code')}")
                    except Exception as e:
                        all_details[url] = {
                            'success': False,
                            'status_code': None,
                            'error': str(e)
                        }
                        logger.debug(f"连接状态检查: {url} 异常: {e}")

            self.signals.health_changed.emit(self.health_status)

            # 保存到内存
            self.all_connections_status = {url: detail['success'] for url, detail in all_details.items()}
            self.all_connections_details = all_details
            self.last_check_time = datetime.now()
            self.all_connections_details['last_check'] = self.last_check_time

            return all_details

        except Exception as e:
            logger.error(f"检查所有连接状态失败: {e}")
            self.health_status = 'unhealthy'
            self.signals.health_changed.emit(self.health_status)
            return {}
        finally:
            self._cleanup_temp_socks5_server()

    def get_formatted_check_time(self, only_time=False):
        """获取格式化的检查时间"""
        if not self.last_check_time:
            return "从未检查"

        if self.health_status == "checking":
            return "正在检查..."

        now = datetime.now()
        time_diff = now - self.last_check_time
        total_seconds = int(time_diff.total_seconds())

        if total_seconds < 60:
            time_str = f"{total_seconds}秒前"
        elif total_seconds < 3600:
            time_str = f"{total_seconds // 60}分钟前"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            time_str = f"{hours}小时{minutes}分钟前"
        else:
            days = total_seconds // 86400
            time_str = f"{days}天前"

        if only_time:
            return time_str

        if self.health_status == "healthy":
            prefix = "✅"
            detail_text = f"检查成功"
            if self.last_success_url and self.last_success_status_code:
                detail_text += f" - {self.last_success_url} ({self.last_success_status_code})"
        elif self.health_status == "unhealthy":
            prefix = "❌"
            failure_reason = self.last_failure_reason
            if len(failure_reason) > 30:
                failure_reason = failure_reason[:30] + "..."
            detail_text = f"检查失败: {failure_reason}"
        else:
            prefix = "❓"
            detail_text = "状态未知"

        return f"{prefix} {time_str} - {detail_text}"

    def set_enabled(self, enabled):
        """启用或禁用健康检查"""
        if enabled:
            self.start()
        else:
            self.stop()

    def get_health_info(self):
        """获取健康状态信息"""
        return {
            'status': self.health_status,
            'last_check': self.last_check_time,
            'last_success_url': self.last_success_url,
            'last_success_status_code': self.last_success_status_code,
            'last_error': self.last_error,
            'check_strategy': self.config.check_strategy,
            'all_connections_status': self.all_connections_status,
            'all_connections_details': self.all_connections_details
        }
