# -*- coding: utf-8 -*-
"""
Module: stats_manager.py
Author: Takeshi
Date: 2025-12-21

Description:
    连接和流量统计模块，用于记录代理服务器和客户端之间的流量
    bytes_received为从客户端接收的流量
    bytes_sent为向客户端发送的流量
"""



from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import time
import threading
import json
from pathlib import Path
import logging
from collections import defaultdict
from defaults.stats_default import StatsConfig

logger = logging.getLogger(__name__)


@dataclass
class DailyStats:
    """每日统计数据"""
    date: str
    total_connections: int = 0
    failed_connections: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    unique_ips: int = 0
    unique_proxies: int = 0
    unique_users: int = 0
    unique_countries: int = 0
    peak_time: str = ""
    peak_connections: int = 0

    # 组合统计
    combined_stats: Dict[str, Dict] = field(default_factory=dict)

    # 协议统计
    socks5_connections: int = 0
    http_connections: int = 0
    https_connections: int = 0

    # 按维度统计
    country_stats: Dict[str, int] = field(default_factory=dict)
    country_bytes_sent: Dict[str, int] = field(default_factory=dict)
    country_bytes_received: Dict[str, int] = field(default_factory=dict)

    proxy_stats: Dict[str, int] = field(default_factory=dict)
    proxy_bytes_sent: Dict[str, int] = field(default_factory=dict)
    proxy_bytes_received: Dict[str, int] = field(default_factory=dict)

    ip_stats: Dict[str, int] = field(default_factory=dict)
    ip_bytes_sent: Dict[str, int] = field(default_factory=dict)
    ip_bytes_received: Dict[str, int] = field(default_factory=dict)

    user_stats: Dict[str, int] = field(default_factory=dict)
    user_bytes_sent: Dict[str, int] = field(default_factory=dict)
    user_bytes_received: Dict[str, int] = field(default_factory=dict)

    # 时间分布
    hourly_connections: Dict[str, int] = field(default_factory=dict)
    hourly_traffic: Dict[str, Dict[str, int]] = field(default_factory=dict)


class ConnectionRecord:
    """连接记录"""

    def __init__(self, timestamp: float, ip: str, country: str = "",
                 proxy_name: str = "", protocol: str = "", user: str = ""):
        self.timestamp = timestamp
        self.ip = ip
        self.country = country
        self.proxy_name = proxy_name
        self.protocol = protocol
        self.user = user
        self.duration: float = 0
        self.bytes_sent: int = 0
        self.bytes_received: int = 0
        self.success: bool = True

        # 添加速度追踪
        self._last_speed_update = timestamp
        self._last_sent = 0
        self._last_received = 0
        self._current_send_speed = 0.0
        self._current_receive_speed = 0.0

    @property
    def total_bytes(self) -> int:
        return self.bytes_sent + self.bytes_received

    @property
    def date_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d")

    @property
    def time_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")

    @property
    def hour_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H")

    def update_speed(self, current_sent: int, current_received: int):
        """更新实时速度"""
        now = time.time()
        elapsed = now - self._last_speed_update

        if elapsed >= 0.5:  # 每0.5秒更新一次速度
            if elapsed > 0:
                sent_delta = current_sent - self._last_sent
                received_delta = current_received - self._last_received

                self._current_send_speed = sent_delta / elapsed
                self._current_receive_speed = received_delta / elapsed

                self._last_sent = current_sent
                self._last_received = current_received
                self._last_speed_update = now



class StatsManager:
    """统计管理器"""

    def __init__(self, config: StatsConfig):
        self.config = config
        self.current_day = datetime.now().strftime("%Y-%m-%d")

        # TODO 先验证功能，后续可以考虑加到配置文件中
        # enable_real_time_speed为True时，计算实时速度，否则为平均速度
        self.enable_real_time_speed = True

        # 存储结构
        self.daily_stats: Dict[str, DailyStats] = {}
        self.active_connections: Dict[str, ConnectionRecord] = {}
        self.active_traffic: Dict[str, Dict[str, int]] = {}
        self.recent_connections: List[ConnectionRecord] = []

        # 实时统计
        self.total_traffic = {
            'bytes_sent': 0,
            'bytes_received': 0,
            'connections_started': 0,
            'connections_ended': 0
        }

        # 分类统计
        self.protocol_stats: Dict[str, Dict[str, Any]] = defaultdict(self._create_protocol_stat)
        self.country_stats: Dict[str, Dict[str, Any]] = defaultdict(self._create_traffic_stat)
        self.proxy_stats: Dict[str, Dict[str, Any]] = defaultdict(self._create_traffic_stat)
        self.ip_stats: Dict[str, Dict[str, Any]] = defaultdict(self._create_traffic_stat)
        self.user_stats: Dict[str, Dict[str, Any]] = defaultdict(self._create_traffic_stat)

        # 速度计算 - 修复版
        self._last_update_time = time.time()
        self._last_bytes_sent = 0
        self._last_bytes_received = 0
        self._current_send_speed = 0.0
        self._current_receive_speed = 0.0
        self._last_speed_update = time.time()

        self._lock = threading.RLock()
        self._running = True

        self._load_stats()
        self._start_workers()

    def _create_protocol_stat(self) -> Dict[str, Any]:
        """创建协议统计默认值"""
        return {'sent': 0, 'received': 0, 'connections': 0}

    def _create_traffic_stat(self) -> Dict[str, Any]:
        """创建流量统计默认值"""
        return {'sent': 0, 'received': 0, 'connections': 0}

    def _create_combined_key(self, proxy_name: str, ip: str, user: str, protocol: str, country: str) -> str:
        """创建安全的组合键"""
        # 使用不太可能在字段中出现的分隔符
        separator = "::"
        fields = [
            proxy_name or "未命名代理",
            ip or "未知",
            user or "无认证",
            protocol or "未知协议",
            country or "未知"
        ]
        # 转义字段中的分隔符
        safe_fields = [str(f).replace(separator, "_") for f in fields]
        return separator.join(safe_fields)

    # ==================== 核心方法 ====================

    def record_connection_start(self, ip: str, protocol: str = "",
                              country: str = "", proxy_name: str = "",
                              user: str = "") -> str:
        """记录连接开始"""
        if not self.config.enable_stats:
            return ""

        connection_id = f"{ip}_{int(time.time()*1000)}"

        with self._lock:
            self._ensure_today_stats()

            # 创建连接记录
            record = ConnectionRecord(
                timestamp=time.time(),
                ip=ip,
                country=country,
                proxy_name=proxy_name,
                protocol=protocol,
                user=user
            )

            # 添加到活跃连接
            self.active_connections[connection_id] = record
            self.active_traffic[connection_id] = {'sent': 0, 'received': 0}

            # 更新总连接数
            self.total_traffic['connections_started'] += 1

            # 更新每日统计
            today = self.current_day
            if today not in self.daily_stats:
                self.daily_stats[today] = DailyStats(date=today)

            stats = self.daily_stats[today]
            stats.total_connections += 1

            # 更新组合统计 - 使用安全的组合键
            proxy_name_display = proxy_name or "未命名代理"
            user_display = user or "无认证"
            protocol_display = protocol or "未知协议"
            country_display = country or "未知"

            combined_key = self._create_combined_key(
                proxy_name_display, ip, user_display, protocol_display, country_display
            )

            if combined_key not in stats.combined_stats:
                stats.combined_stats[combined_key] = {
                    'proxy_name': proxy_name_display,
                    'ip': ip,
                    'user': user_display,
                    'protocol': protocol_display,
                    'country': country_display,
                    'connections': 0,
                    'bytes_sent': 0,
                    'bytes_received': 0,
                    'last_active': time.time()
                }

            stats.combined_stats[combined_key]['connections'] += 1
            stats.combined_stats[combined_key]['last_active'] = time.time()

            # 更新协议统计
            protocol_lower = protocol_display.lower()
            if protocol_lower == 'socks5':
                stats.socks5_connections += 1
            elif protocol_lower == 'http':
                stats.http_connections += 1
            elif protocol_lower == 'https':
                stats.https_connections += 1

            # 更新其他维度统计
            if country_display:
                stats.country_stats[country_display] = stats.country_stats.get(country_display, 0) + 1

            if proxy_name_display:
                stats.proxy_stats[proxy_name_display] = stats.proxy_stats.get(proxy_name_display, 0) + 1

            stats.ip_stats[ip] = stats.ip_stats.get(ip, 0) + 1

            if user_display:
                stats.user_stats[user_display] = stats.user_stats.get(user_display, 0) + 1

            # 更新时间分布
            hour_key = datetime.now().strftime("%H")
            stats.hourly_connections[hour_key] = stats.hourly_connections.get(hour_key, 0) + 1

            if hour_key not in stats.hourly_traffic:
                stats.hourly_traffic[hour_key] = {"sent": 0, "received": 0}

            # 更新唯一计数
            stats.unique_ips = len(stats.ip_stats)
            stats.unique_proxies = len(stats.proxy_stats)
            stats.unique_users = len(stats.user_stats)
            stats.unique_countries = len(stats.country_stats)

            # 更新分类连接数
            if protocol:
                self.protocol_stats[protocol]['connections'] += 1
            if country:
                self.country_stats[country]['connections'] += 1
            if proxy_name:
                self.proxy_stats[proxy_name]['connections'] += 1
            self.ip_stats[ip]['connections'] += 1
            if user:
                self.user_stats[user]['connections'] += 1

            return connection_id

    def record_traffic(self, bytes_sent: int, bytes_received: int,
                      protocol: str = "", country: str = "", proxy_name: str = "",
                      ip: str = "", user: str = "", connection_id: str = ""):
        """记录流量（实时调用）"""
        if not self.config.enable_stats or not connection_id:
            return

        with self._lock:
            # 更新总流量
            self.total_traffic['bytes_sent'] += bytes_sent
            self.total_traffic['bytes_received'] += bytes_received

            # 更新活跃连接流量
            traffic_data = self.active_traffic.get(connection_id)
            if traffic_data is None:
                # 如果连接不在活跃列表中，创建记录（可能先收到流量后开始连接）
                traffic_data = {'sent': 0, 'received': 0}
                self.active_traffic[connection_id] = traffic_data

            traffic_data['sent'] += bytes_sent
            traffic_data['received'] += bytes_received

            # 更新连接的速度信息
            record = self.active_connections.get(connection_id)
            if record:
                record.bytes_sent = traffic_data['sent']
                record.bytes_received = traffic_data['received']
                if self.enable_real_time_speed:
                    record.update_speed(traffic_data['sent'], traffic_data['received'])

            # 更新每日统计
            today = self.current_day
            if today in self.daily_stats:
                stats = self.daily_stats[today]

                # 更新总流量
                stats.total_bytes_sent += bytes_sent
                stats.total_bytes_received += bytes_received

                # 更新组合统计
                proxy_name_display = proxy_name or "未命名代理"
                user_display = user or "无认证"
                protocol_display = protocol or "未知协议"
                country_display = country or "未知"

                combined_key = self._create_combined_key(
                    proxy_name_display, ip, user_display, protocol_display, country_display
                )

                if combined_key in stats.combined_stats:
                    stats.combined_stats[combined_key]['bytes_sent'] += bytes_sent
                    stats.combined_stats[combined_key]['bytes_received'] += bytes_received
                    stats.combined_stats[combined_key]['last_active'] = time.time()

                # 更新时间分布流量
                hour_key = datetime.now().strftime("%H")
                if hour_key in stats.hourly_traffic:
                    stats.hourly_traffic[hour_key]["sent"] += bytes_sent
                    stats.hourly_traffic[hour_key]["received"] += bytes_received

                # 按维度更新流量
                if country_display:
                    stats.country_bytes_sent[country_display] = stats.country_bytes_sent.get(country_display, 0) + bytes_sent
                    stats.country_bytes_received[country_display] = stats.country_bytes_received.get(country_display, 0) + bytes_received

                if proxy_name_display:
                    stats.proxy_bytes_sent[proxy_name_display] = stats.proxy_bytes_sent.get(proxy_name_display, 0) + bytes_sent
                    stats.proxy_bytes_received[proxy_name_display] = stats.proxy_bytes_received.get(proxy_name_display, 0) + bytes_received

                stats.ip_bytes_sent[ip] = stats.ip_bytes_sent.get(ip, 0) + bytes_sent
                stats.ip_bytes_received[ip] = stats.ip_bytes_received.get(ip, 0) + bytes_received

                if user_display:
                    stats.user_bytes_sent[user_display] = stats.user_bytes_sent.get(user_display, 0) + bytes_sent
                    stats.user_bytes_received[user_display] = stats.user_bytes_received.get(user_display, 0) + bytes_received

            # 更新分类统计流量
            if protocol:
                self.protocol_stats[protocol]['sent'] += bytes_sent
                self.protocol_stats[protocol]['received'] += bytes_received
            if country:
                self.country_stats[country]['sent'] += bytes_sent
                self.country_stats[country]['received'] += bytes_received
            if proxy_name:
                self.proxy_stats[proxy_name]['sent'] += bytes_sent
                self.proxy_stats[proxy_name]['received'] += bytes_received
            self.ip_stats[ip]['sent'] += bytes_sent
            self.ip_stats[ip]['received'] += bytes_received
            if user:
                self.user_stats[user]['sent'] += bytes_sent
                self.user_stats[user]['received'] += bytes_received

    def record_connection_end(self, connection_id: str,
                            bytes_sent: int = 0,
                            bytes_received: int = 0,
                            success: bool = True):
        """记录连接结束"""
        if not connection_id or not self.config.enable_stats:
            return

        with self._lock:
            record = self.active_connections.pop(connection_id, None)
            if not record:
                return

            # 使用实时流量或传入的流量
            traffic = self.active_traffic.pop(connection_id, {'sent': 0, 'received': 0})
            final_sent = max(bytes_sent, traffic['sent'])
            final_received = max(bytes_received, traffic['received'])

            # 更新记录
            record.duration = time.time() - record.timestamp
            record.bytes_sent = final_sent
            record.bytes_received = final_received
            record.success = success

            # 添加到历史记录
            self.recent_connections.append(record)
            if len(self.recent_connections) > 1000:
                self.recent_connections = self.recent_connections[-1000:]

            # 更新结束连接数
            self.total_traffic['connections_ended'] += 1

            # 更新每日统计的失败连接数
            if not success:
                today = self.current_day
                if today in self.daily_stats:
                    self.daily_stats[today].failed_connections += 1

    # ==================== UI接口方法 ====================

    def get_realtime_stats(self) -> Dict[str, Any]:
        """获取实时统计"""
        with self._lock:
            now = time.time()

            # 计算实时速度
            if self.enable_real_time_speed:
                elapsed_since_speed_update = now - self._last_speed_update
                if elapsed_since_speed_update > 0:
                    # 如果距离上次更新超过1秒，更新速度
                    sent_since_last = self.total_traffic['bytes_sent'] - self._last_bytes_sent
                    received_since_last = self.total_traffic['bytes_received'] - self._last_bytes_received

                    self._current_send_speed = sent_since_last / elapsed_since_speed_update
                    self._current_receive_speed = received_since_last / elapsed_since_speed_update

                    self._last_bytes_sent = self.total_traffic['bytes_sent']
                    self._last_bytes_received = self.total_traffic['bytes_received']
                    self._last_speed_update = now
            else:
                # 使用旧的简单计算
                elapsed = now - self._last_update_time
                if elapsed > 0:
                    self._current_send_speed = (self.total_traffic['bytes_sent'] - self._last_bytes_sent) / elapsed
                    self._current_receive_speed = (self.total_traffic['bytes_received'] - self._last_bytes_received) / elapsed
                else:
                    self._current_send_speed = 0
                    self._current_receive_speed = 0

            # 获取今日统计
            today = self.current_day
            today_connections = 0
            today_sent = 0
            today_received = 0

            if today in self.daily_stats:
                stats = self.daily_stats[today]
                today_connections = stats.total_connections
                today_sent = stats.total_bytes_sent
                today_received = stats.total_bytes_received

            result: Dict[str, Any] = {
                'active_count': len(self.active_connections),
                'today_connections': today_connections,
                'today_bytes_sent': today_sent,
                'today_bytes_received': today_received,
                'total_sent': self.total_traffic['bytes_sent'],
                'total_received': self.total_traffic['bytes_received'],
                'send_speed': self._current_send_speed,
                'receive_speed': self._current_receive_speed,
                'bytes_per_second': self._current_send_speed + self._current_receive_speed,
                'peak_active_count': 0,  # 可以添加峰值追踪
                'peak_time': datetime.now().strftime("%H:%M:%S")
            }

            return result

    def get_active_connection_details(self) -> List[Dict[str, Any]]:
        """获取活跃连接详情 - 提供实时速度"""
        details: List[Dict[str, Any]] = []

        with self._lock:
            current_time = time.time()

            for conn_id, record in self.active_connections.items():
                traffic = self.active_traffic.get(conn_id, {'sent': 0, 'received': 0})
                duration = current_time - record.timestamp

                # 使用连接记录的实时速度（如果可用）
                if self.enable_real_time_speed:
                    send_speed = record._current_send_speed
                    receive_speed = record._current_receive_speed
                else:
                    # 计算平均速度
                    send_speed = traffic['sent'] / duration if duration > 0 else 0
                    receive_speed = traffic['received'] / duration if duration > 0 else 0

                detail: Dict[str, Any] = {
                    'id': conn_id,
                    'time': record.time_str,
                    'proxy': record.proxy_name or '-',
                    'ip': record.ip,
                    'country': record.country or '-',
                    'user': record.user or '匿名',
                    'protocol': record.protocol or '-',
                    'duration': duration,
                    'bytes_sent': traffic['sent'],
                    'bytes_received': traffic['received'],
                    'send_speed': send_speed,
                    'receive_speed': receive_speed,
                    'active': True
                }
                details.append(detail)

        return details

    def get_active_connections_list(self) -> List[Dict[str, Any]]:
        """获取活跃连接列表"""
        return self.get_active_connection_details()

    def get_detailed_stats(self, date: str = None) -> Dict[str, Any]:
        """获取详细统计数据"""
        with self._lock:
            if date is None:
                date = self.current_day

            stats = self.daily_stats.get(date)
            if not stats:
                return {}

            return asdict(stats)

    def get_all_dates(self) -> List[str]:
        """获取所有有统计数据的日期"""
        with self._lock:
            dates = list(self.daily_stats.keys())
            dates.sort(reverse=True)  # 最新的在前面
            return dates

    def get_date_range_stats(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """获取日期范围内的统计数据"""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")

            if start > end:
                start, end = end, start

            result = {
                'total_connections': 0,
                'total_bytes_sent': 0,
                'total_bytes_received': 0,
                'failed_connections': 0,
                'days': []
            }

            with self._lock:
                current = start
                while current <= end:
                    date_str = current.strftime("%Y-%m-%d")
                    if date_str in self.daily_stats:
                        stats = self.daily_stats[date_str]
                        result['total_connections'] += stats.total_connections
                        result['total_bytes_sent'] += stats.total_bytes_sent
                        result['total_bytes_received'] += stats.total_bytes_received
                        result['failed_connections'] += stats.failed_connections
                        result['days'].append(date_str)

                    current += timedelta(days=1)

            return result

        except ValueError as e:
            logger.error(f"日期格式错误: {e}")
            return {}

    # ==================== 辅助方法 ====================

    def _ensure_today_stats(self):
        """确保今日统计存在"""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        if today != self.current_day:
            logger.info(f"检测到日期变化: {self.current_day} -> {today}")
            self.current_day = today

            # 创建新的每日统计（如果不存在）
            if today not in self.daily_stats:
                self.daily_stats[today] = DailyStats(date=today)
                logger.info(f"创建新的每日统计: {today}")

            # 只有在配置了max_days并且大于0时才清理
            if hasattr(self.config, 'max_days') and self.config.max_days and self.config.max_days > 0:
                self._cleanup_old_stats()
            else:
                logger.debug("跳过旧数据清理（max_days未设置或为0）")

    def _cleanup_old_stats(self):
        """清理过期数据"""
        if not hasattr(self.config, 'max_days') or not self.config.max_days:
            return

        try:
            cutoff_date = (datetime.now() - timedelta(days=self.config.max_days)).strftime("%Y-%m-%d")
            dates_to_remove = []

            for date in list(self.daily_stats.keys()):
                try:
                    if date < cutoff_date:
                        dates_to_remove.append(date)
                except (ValueError, TypeError):
                    logger.warning(f"无效的日期格式: {date}")
                    continue

            if dates_to_remove:
                logger.info(f"清理 {len(dates_to_remove)} 天的旧数据（早于 {cutoff_date}）")
                for date in dates_to_remove:
                    del self.daily_stats[date]

        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")

    def _start_workers(self):
        """启动工作线程"""
        if not self.config.enable_stats:
            return

        def save_worker():
            while self._running:
                time.sleep(self.config.save_interval)
                self._save_stats()

        def monitor_worker():
            while self._running:
                time.sleep(self.config.update_interval)
                self._update_monitor()

        threading.Thread(target=save_worker, daemon=True).start()
        threading.Thread(target=monitor_worker, daemon=True).start()

    def _update_monitor(self):
        """更新监控数据"""
        with self._lock:
            now = time.time()
            self._last_update_time = now

            # 更新连接的速度信息
            if self.enable_real_time_speed:
                for conn_id, record in self.active_connections.items():
                    traffic = self.active_traffic.get(conn_id, {'sent': 0, 'received': 0})
                    record.update_speed(traffic['sent'], traffic['received'])

    def _load_stats(self):
        """加载统计数据"""
        try:
            stats_file = Path(self.config.save_file)
            if not stats_file.exists():
                logger.info(f"统计文件不存在: {stats_file}")
                return

            with open(stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                for date_str, stats_data in data.get('daily_stats', {}).items():
                    try:
                        # 验证日期格式
                        datetime.strptime(date_str, "%Y-%m-%d")

                        stats = DailyStats(**stats_data)
                        self.daily_stats[date_str] = stats
                        logger.debug(f"加载日期 {date_str} 的统计数据")
                    except ValueError as e:
                        logger.error(f"日期格式无效 {date_str}: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"加载日期 {date_str} 的统计数据失败: {e}")
                        continue

            logger.info(f"成功加载 {len(self.daily_stats)} 天的统计数据")

        except json.JSONDecodeError as e:
            logger.error(f"统计文件JSON格式错误: {e}")
        except Exception as e:
            logger.error(f"加载连接统计失败: {e}")

    def _save_stats(self):
        """保存统计数据"""
        try:
            stats_file = Path(self.config.save_file)
            stats_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'daily_stats': {},
                'metadata': {
                    'saved_at': datetime.now().isoformat(),
                    'total_days': len(self.daily_stats),
                    'total_connections': self.total_traffic['connections_started']
                }
            }

            with self._lock:
                for date, stats in self.daily_stats.items():
                    try:
                        data['daily_stats'][date] = asdict(stats)
                    except Exception as e:
                        logger.error(f"序列化日期 {date} 的统计数据失败: {e}")
                        continue

            temp_file = stats_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            temp_file.replace(stats_file)
            logger.debug(f"统计数据已保存到: {stats_file}")

        except Exception as e:
            logger.error(f"保存连接统计失败: {e}")

    def clear_stats(self):
        """清空所有统计信息"""
        with self._lock:
            self.daily_stats.clear()
            self.active_connections.clear()
            self.active_traffic.clear()
            self.recent_connections.clear()

            self.total_traffic = {
                'bytes_sent': 0,
                'bytes_received': 0,
                'connections_started': 0,
                'connections_ended': 0
            }

            self.protocol_stats.clear()
            self.country_stats.clear()
            self.proxy_stats.clear()
            self.ip_stats.clear()
            self.user_stats.clear()

            self._current_send_speed = 0
            self._current_receive_speed = 0
            self._last_bytes_sent = 0
            self._last_bytes_received = 0
            self._last_speed_update = time.time()

            self.current_day = datetime.now().strftime("%Y-%m-%d")

            logger.info("统计信息已清空")

    def stop(self):
        """停止统计管理器"""
        self._running = False
        self._save_stats()
        logger.info("StatsManager已停止")
