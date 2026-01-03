# -*- coding: utf-8 -*-
"""
Module: dns_resolver.py
Author: Takeshi
Date: 2025-11-08

Description:
    DNS解析器
"""
import concurrent.futures
import fnmatch
import logging
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Tuple

import dns.message
import dns.query
import dns.rdatatype
from dns.exception import DNSException, Timeout

from defaults.dns_default import DNSConfig

logger = logging.getLogger(__name__)


class DNSResolver:
    """DNS解析器，支持缓存和并行解析"""

    def __init__(self, config: DNSConfig):
        """初始化DNS解析器"""
        # self.config = config
        self.name = config.name
        self.enable_remote_dns_resolve = config.enable_remote_dns_resolve
        self.dns_servers = config.dns_servers
        self.enable_cache = config.enable_cache
        self.default_cache_ttl = config.default_cache_ttl
        self.cleanup_interval = config.cleanup_interval
        self.max_cache_size = config.max_cache_size
        self.enable_system_dns = config.enable_system_dns
        self.resolve_strategy = config.resolve_strategy
        self.serial_timeout = config.serial_timeout
        self.parallel_timeout = config.parallel_timeout
        self.parallel_workers = config.parallel_workers

        # 解析黑名单
        self.blacklist_domains = set(config.blacklist_domains)
        self.blacklist_patterns = config.blacklist_patterns

        # 编译正则表达式
        self._compiled_patterns = None
        if self.blacklist_patterns:
            self._compile_patterns()

        # 缓存相关
        self._cache: Dict[str, Tuple[str, float, float]] = {}  # hostname -> (ip, timestamp, ttl)
        self._cache_lock = threading.RLock()

        # 线程池用于并行解析
        self._executor = ThreadPoolExecutor(
            max_workers=self.parallel_workers,
            thread_name_prefix=f"DNSResolver-Parallel-{self.name}"
        )

        # 定期清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._start_cleanup_thread()

        logger.info(f"{self.name}: DNS解析器初始化完成，策略: {self.resolve_strategy}")

    # ==================== 主要解析方法 ====================

    def resolve(self,
                hostname: str,
                egress_ip: Optional[str] = None,
                timeout: Optional[int] = None) -> str:
        """
        解析域名到IP地址

        Args:
            hostname: 要解析的域名
            egress_ip: 出口IP地址（绑定网卡）
            timeout: 超时时间（秒），None使用默认配置

        Returns:
            IP地址字符串

        Raises:
            RuntimeError: 解析失败时抛出
        """
        # 检查黑名单
        if self._is_blacklisted(hostname):
            logger.warning(f"{self.name}: 🚫 拒绝解析黑名单域名: {hostname}")
            return "0.0.0.0"

        # 检查缓存
        if self.enable_cache:
            cached_result = self._get_from_cache(hostname)
            if cached_result:
                logger.info(f"{self.name}: 使用缓存: {hostname} -> {cached_result}")
                return cached_result

        if not self.enable_remote_dns_resolve:
            logger.debug(f"禁用远端dns解析")
            return self._resolve_with_system_mode(hostname)

        # 根据策略选择解析方法
        if self.resolve_strategy == "parallel":
            result = self._resolve_parallel(hostname, egress_ip, timeout)
        else:
            result = self._resolve_serial(hostname, egress_ip, timeout)

        # 缓存结果
        if self.enable_cache and result:
            self._add_to_cache(hostname, result, self.default_cache_ttl)

        return result

    def _resolve_serial(self,
                       hostname: str,
                       egress_ip: Optional[str] = None,
                       timeout: Optional[int] = None) -> str:
        """串行解析"""
        timeout_val = timeout or self.serial_timeout

        for server in self.dns_servers:
            try:
                logger.debug(f"{self.name}: 使用DNS服务器 {server} 解析: {hostname}")

                result = self._query_dns_server(server, hostname, egress_ip, timeout_val)

                logger.info(f"{self.name}: 串行解析成功 [{server}]: {hostname} -> {result}")
                return result

            except (socket.timeout, Timeout):
                logger.debug(f"{self.name}: {server} 查询超时")
            except DNSException as e:
                logger.debug(f"{self.name}: {server} DNS协议错误: {e}")
            except OSError as e:
                logger.debug(f"{self.name}: {server} 网络错误: {e}")
            except Exception as e:
                logger.warning(f"{self.name}: {server} 未知错误: {e}")

        # 尝试过期缓存
        if self.enable_cache:
            expired_result = self._get_expired_from_cache(hostname)
            if expired_result:
                logger.debug(f"{self.name}: DNS查询失败，使用过期的缓存: {hostname} -> {expired_result}")
                return expired_result

        # 尝试系统DNS
        if self.enable_system_dns:
            try:
                logger.debug(f"{self.name}: 尝试系统DNS解析: {hostname}")
                result = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
                if result:
                    ip = result[0][4][0]
                    logger.debug(f"{self.name}: 系统DNS解析成功: {hostname} -> {ip}")
                    return str(ip)
                raise RuntimeError("系统DNS返回空结果")
            except Exception as e:
                logger.error(f"{self.name}: 系统DNS解析失败: {e}")

        # 所有方法都失败
        error_msg = f"{self.name}: 所有DNS服务器均无法解析 {hostname}"
        raise RuntimeError(error_msg)


    def _resolve_parallel(self,
                         hostname: str,
                         egress_ip: Optional[str] = None,
                         timeout: Optional[int] = None) -> str:
        """并行解析"""
        timeout_val = timeout or self.parallel_timeout

        # 准备并行查询任务
        futures = {}
        for server in self.dns_servers:
            future = self._executor.submit(
                self._query_dns_server,
                server, hostname, egress_ip, timeout_val
            )
            futures[future] = server

        # 等待第一个成功的结果
        try:
            done, not_done = concurrent.futures.wait(
                futures.keys(),
                timeout=timeout_val,
                return_when=concurrent.futures.FIRST_COMPLETED
            )

            # 检查已完成的任务
            for future in done:
                if future.exception() is None:
                    result = future.result()
                    if result:
                        server = futures[future]
                        logger.info(f"{self.name}: 并行解析成功 [{server}]: {hostname} -> {result}")

                        for unfinished_future in not_done:
                            unfinished_future.cancel()

                        return result

        except Exception as e:
            logger.error(f"{self.name}: 并行解析异常: {e}")

        # 并行解析失败，降级到串行
        logger.debug(f"{self.name}: 并行解析失败，尝试串行解析")
        return self._resolve_serial(hostname, egress_ip, timeout)

    def _query_dns_server(self,
                         server: str,
                         hostname: str,
                         egress_ip: Optional[str] = None,
                         timeout: int = 5) -> str:
        """查询单个DNS服务器"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)

            if egress_ip:
                sock.bind((egress_ip, 0))

            query = dns.message.make_query(hostname, dns.rdatatype.A)
            response = dns.query.udp(query, server, timeout=timeout, sock=sock)

            if response.rcode() != 0:
                raise DNSException(f"DNS错误码: {response.rcode()}")

            # 查找A记录
            for answer in response.answer:
                if answer.rdtype == dns.rdatatype.A:
                    for item in answer:
                        if hasattr(item, 'address'):
                            ip_address = str(item.address)
                            return ip_address

            raise DNSException("未找到A记录")

    def _resolve_with_system_mode(self, hostname:str) -> str:
        try:
            logger.debug(f"{self.name}: 使用系统DNS解析: {hostname}")
            result = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
            if result:
                hostname_ip = result[0][4][0]
                logger.info(f"{self.name}: 系统DNS解析成功: {hostname} -> {hostname_ip}")
                return str(hostname_ip)
            else:
                raise RuntimeError(f"{self.name}: 系统DNS解析返回空结果")
        except Exception as e:
            logger.error(f"{self.name}: 系统DNS解析失败: {e}")
            raise RuntimeError(f"{self.name}: 系统DNS解析失败: {e}")

    # ==================== 黑名单检查 ====================

    def _compile_patterns(self):
        """预编译通配符模式为正则表达式"""
        import re
        compiled = []
        for pattern in self.blacklist_patterns:
            regex_pattern = fnmatch.translate(pattern)
            compiled.append(re.compile(regex_pattern))
        self._compiled_patterns = compiled

    def _is_blacklisted(self, hostname: str) -> bool:
        """检查域名是否在黑名单中"""
        if hostname in self.blacklist_domains:
            logger.debug(f"{self.name}: 精确匹配黑名单: {hostname}")
            return True

        if self._compiled_patterns:
            for pattern_regex in self._compiled_patterns:
                if pattern_regex.match(hostname):
                    logger.debug(f"{self.name}: 通配符匹配: {hostname}")
                    return True

        return False

    # ==================== 缓存管理 ====================

    def _add_to_cache(self, hostname: str, ip: str, ttl: Optional[int] = None):
        """添加记录到缓存"""
        with self._cache_lock:
            cache_ttl = ttl if ttl is not None else self.default_cache_ttl
            self._cache[hostname] = (ip, time.time(), cache_ttl)

    def _get_from_cache(self, hostname: str) -> Optional[str]:
        """从缓存获取未过期的记录"""
        with self._cache_lock:
            if hostname not in self._cache:
                return None

            ip, timestamp, ttl = self._cache[hostname]
            if time.time() - timestamp <= ttl:
                return ip
            else:
                return None

    def _get_expired_from_cache(self, hostname: str) -> Optional[str]:
        """获取过期的缓存记录"""
        with self._cache_lock:
            if hostname in self._cache:
                ip, timestamp, ttl = self._cache[hostname]
                return ip
            return None

    def clear_cache(self, hostname: Optional[str] = None):
        """清理缓存"""
        with self._cache_lock:
            if hostname:
                if hostname in self._cache:
                    del self._cache[hostname]
                    logger.debug(f"{self.name}: 已清除缓存: {hostname}")
            else:
                count = len(self._cache)
                self._cache.clear()
                logger.debug(f"{self.name}: 已清除所有缓存，共{count}条记录")

    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        with self._cache_lock:
            now = time.time()
            valid = 0
            expired = 0

            for ip, timestamp, ttl in self._cache.values():
                if now - timestamp <= ttl:
                    valid += 1
                else:
                    expired += 1

            return {
                'total': len(self._cache),
                'valid': valid,
                'expired': expired
            }

    # ==================== 后台清理线程 ====================

    def _start_cleanup_thread(self):
        """启动缓存清理线程"""
        if self.enable_cache and self.cleanup_interval:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                name=f"DNSResolver-Cleanup-{self.name}",
                daemon=True
            )
            self._cleanup_thread.start()
            logger.debug(f"{self.name}: 启动缓存清理线程")

    def _cleanup_worker(self):
        """缓存清理工作线程"""
        while not self._stop_event.wait(self.cleanup_interval):
            try:
                self._perform_cache_cleanup()
            except Exception as e:
                logger.error(f"{self.name}: 缓存清理异常: {e}")

    def _perform_cache_cleanup(self):
        """执行缓存清理"""
        with self._cache_lock:
            now = time.time()
            expired_count = 0
            oversized_count = 0

            # 清理过期缓存
            expired_hostnames = []
            for hostname, (ip, timestamp, ttl) in self._cache.items():
                if now - timestamp > ttl:
                    expired_hostnames.append(hostname)

            for hostname in expired_hostnames:
                del self._cache[hostname]
                expired_count += 1

            # 清理超出大小的缓存
            if self.max_cache_size > 0 and len(self._cache) > self.max_cache_size:
                sorted_items = sorted(
                    self._cache.items(),
                    key=lambda x: x[1][1]
                )
                remove_count = len(self._cache) - self.max_cache_size
                for i in range(remove_count):
                    hostname, _ = sorted_items[i]
                    del self._cache[hostname]
                    oversized_count += 1

            if expired_count > 0 or oversized_count > 0:
                logger.debug(
                    f"{self.name}: 缓存清理 - "
                    f"过期: {expired_count}, 超限: {oversized_count}, "
                    f"剩余: {len(self._cache)}"
                )

    def shutdown(self):
        """关闭解析器，清理资源"""
        self._stop_event.set()

        # 等待清理线程结束
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)

        # 关闭线程池
        self._executor.shutdown(wait=True)

        # 清理缓存
        self.clear_cache()

        logger.debug(f"{self.name}: DNS解析器已关闭")
