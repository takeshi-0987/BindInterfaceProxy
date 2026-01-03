# -*- coding: utf-8 -*-
"""
Module: ip_geo_manager.py
Author: Takeshi
Date: 2026-01-01

Description:
    通过ip查询地理信息
"""

import logging
import ipaddress
import time
import copy

import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from concurrent.futures import ThreadPoolExecutor, as_completed

from defaults.ip_geo_default import IPGeoConfig, DatabaseConfig, DatabaseType

logger = logging.getLogger(__name__)


class DatabaseResult:
    """数据库查询结果"""

    def __init__(self, source_name: str, source_path: str, source_type: DatabaseType):
        self.source_name = source_name      # 数据库名
        self.source_path = source_path      # 文件路径
        self.source_type = source_type      # 数据库类型
        self.country = "未知"
        self.region = "未知"
        self.city = "未知"
        self.isp = "未知"
        self.success = False
        self.error = ""
        self.response_time = 0  # 响应时间（毫秒）
        self.is_special = False  # 是否为特殊IP

        # 详细信息字段
        self.organization = ""      # 组织
        self.asn = ""               # ASN
        self.as_organization = ""   # AS组织
        self.country_code = ""      # 国家代码
        self.latitude = ""          # 纬度
        self.longitude = ""         # 经度
        self.timezone = ""          # 时区
        self.network_cidr = ""      # 网络CIDR
        self.ip_range = ""          # IP范围

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'source_name': self.source_name,
            'source_path': self.source_path,
            'source_type': self.source_type.value,
            'country': self.country,
            'region': self.region,
            'city': self.city,
            'isp': self.isp,
            'success': self.success,
            'error': self.error,
            'response_time': self.response_time,
            'is_special': self.is_special,
            'organization': self.organization,
            'asn': self.asn,
            'as_organization': self.as_organization,
            'country_code': self.country_code,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'timezone': self.timezone,
            'network_cidr': self.network_cidr,
            'ip_range': self.ip_range
        }


class IPGeoManager:
    """IP地理位置管理器 - 查看IP地理位置信息"""

    def __init__(self, config: IPGeoConfig):
        self.config = config

        # 数据库列表
        self.databases: List[DatabaseConfig] = []
        self.db_readers: Dict[str, Any] = {}
        self.db_types: Dict[str, DatabaseType] = {}

        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_queries)

        # 延迟加载的依赖库
        self.maxminddb = None
        self.ip2location_module = None

        # 导入依赖库
        self._import_dependencies()

        # 加载所有数据库
        self._load_databases()

        # 缓存初始化
        self.cache_enabled = self.config.cache_config.enabled
        self.cache_ttl = self.config.cache_config.ttl_seconds
        self.cache_max_size = self.config.cache_config.max_size

        # 简单缓存字典：ip -> (results, timestamp)
        self._cache = {}

        # 缓存统计
        self.cache_stats: Dict[str, Union[int, float]] = {
            'hits': 0,
            'misses': 0,
            'size': 0
        }

        # 统计信息
        self.stats = {
            'total_queries': 0,
            'special_ip_queries': 0,
            'database_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0
        }

        logger.info(f"IP地理位置管理器初始化，加载了 {len(self.databases)} 个数据库")
        if self.cache_enabled:
            logger.info(f"缓存启用: TTL={self.cache_ttl}秒, 最大数量={self.cache_max_size}")

    def _import_dependencies(self):
        """导入依赖库"""
        # 尝试导入 maxminddb
        try:
            import maxminddb
            self.maxminddb = maxminddb
            logger.info("✓ maxminddb 库导入成功")
        except ImportError as e:
            logger.warning(f"⚠ 无法导入 maxminddb 库: {e}")
            logger.warning("请安装: pip install maxminddb")

        # 尝试导入 ip2location
        try:
            import IP2Location
            self.ip2location_module = IP2Location
            logger.info("✓ IP2Location 库导入成功")
        except ImportError as e:
            logger.warning(f"⚠ 无法导入 IP2Location 库: {e}")
            logger.warning("请安装: pip install IP2Location")
        except Exception as e:
            logger.warning(f"⚠ 导入 IP2Location 库时出错: {e}")

    def _load_databases(self):
        """加载所有启用的数据库"""
        # 获取启用的数据库配置
        enabled_dbs = [db for db in self.config.databases if db.enabled]

        if not enabled_dbs:
            logger.warning("没有启用任何数据库")
            return

        logger.info(f"找到 {len(enabled_dbs)} 个启用的数据库")

        # 按优先级排序
        enabled_dbs.sort(key=lambda db: db.priority)

        for db_config in enabled_dbs:

            logger.debug(f"启用的数据库: {db_config.name}, 类型: {db_config.db_type}, "
            f"路径: {db_config.path}, 优先级: {db_config.priority}")

            db_name = db_config.name
            db_path_str = db_config.path
            db_path = Path(db_path_str)
            db_type_str = db_config.db_type

            if not db_path.exists():
                logger.warning(f"数据库文件不存在: {db_path}")
                continue

            if not db_path.is_file():
                logger.warning(f"数据库路径不是文件: {db_path}")
                continue

            # 确定数据库类型
            try:
                db_type = DatabaseType(db_type_str)
            except ValueError:
                logger.warning(f"不支持的数据库类型: {db_type_str}，尝试自动识别")
                db_type = self._guess_database_type(db_path)

            try:
                reader = None

                # 只保留MMDB和IP2Location BIN两种格式
                if db_type == DatabaseType.MMDB:
                    reader = self._load_mmdb_database(db_path, db_name)
                elif db_type == DatabaseType.IP2LOCATION_BIN:
                    reader = self._load_ip2location_database(db_path, db_name)
                else:
                    logger.warning(f"不支持的数据格式: {db_type.value}")
                    continue

                if reader is None:
                    continue

                # 保存数据库
                self.db_readers[db_name] = reader
                self.db_types[db_name] = db_type
                self.databases.append(db_config)

                # 记录数据库信息
                db_size = db_path.stat().st_size
                size_mb = db_size / (1024 * 1024)
                logger.info(f"✓ 已加载 {db_type.value} 数据库: {db_name} ({size_mb:.1f} MB, 优先级: {db_config.priority})")

            except Exception as e:
                logger.error(f"加载数据库 {db_name} 失败: {e}")
                continue

        logger.info(f"成功加载 {len(self.db_readers)}/{len(enabled_dbs)} 个数据库")

    def _guess_database_type(self, db_path: Path) -> DatabaseType:
        """根据文件扩展名猜测数据库类型"""
        suffix = db_path.suffix.lower()
        filename = db_path.name.lower()

        if suffix in ['.mmdb']:
            return DatabaseType.MMDB
        elif suffix in ['.bin', '.dat']:
            if 'ip2location' in filename:
                return DatabaseType.IP2LOCATION_BIN
            else:
                return DatabaseType.IP2LOCATION_BIN
        else:
            return DatabaseType.UNKNOWN

    def _load_mmdb_database(self, db_path: Path, db_name: str):
        """加载MMDB格式数据库"""
        if self.maxminddb is None:
            logger.warning(f"跳过 {db_name}: maxminddb 库未安装")
            return None

        try:
            reader = self.maxminddb.open_database(str(db_path))

            # 验证数据库是否能正常读取
            try:
                test_ip = "8.8.8.8"
                test_result = reader.get(test_ip)
                if test_result is None:
                    logger.warning(f"数据库 {db_name} 可能为空或格式错误")
                    reader.close()
                    return None
            except Exception as e:
                logger.warning(f"数据库 {db_name} 读取测试失败: {e}")
                reader.close()
                return None

            return reader

        except Exception as e:
            logger.error(f"加载MMDB数据库 {db_name} 失败: {e}")
            return None

    def _load_ip2location_database(self, db_path: Path, db_name: str):
        """加载IP2Location BIN格式数据库"""
        if self.ip2location_module is None:
            logger.warning(f"跳过 {db_name}: ip2location 库未安装")
            return None

        try:
            # 创建数据库对象
            database = self.ip2location_module.IP2Location()

            # 尝试打开数据库
            try:
                database.open(str(db_path))
            except Exception as e:
                logger.error(f"打开IP2Location数据库 {db_name} 失败: {e}")
                return None

            # 测试读取
            try:
                test_result = database.get_all("8.8.8.8")
                if not test_result:
                    logger.warning(f"IP2Location数据库 {db_name} 可能为空或格式错误")
                    database.close()
                    return None
            except Exception as e:
                logger.warning(f"IP2Location数据库 {db_name} 读取测试失败: {e}")
                database.close()
                return None

            # 存储额外信息
            # 尝试从文件名猜测数据库类型
            filename = db_path.name.upper()

            # IP2Location数据库类型映射
            db_type_mapping = {
                'DB1': 'Country',
                'DB3': 'Region',
                'DB5': 'ISP',
                'DB9': 'City',
                'DB11': 'City_ISP'
            }

            # 从文件名提取数据库类型
            db_code = None
            for code in db_type_mapping.keys():
                if code in filename:
                    db_code = code
                    break

            if db_code:
                setattr(database, '_db_type_code', db_code)
                setattr(database, '_db_type_name', db_type_mapping[db_code])
            else:
                setattr(database, '_db_type_code', 'UNKNOWN')
                setattr(database, '_db_type_name', 'Unknown')

            return database

        except Exception as e:
            logger.error(f"加载IP2Location数据库 {db_name} 失败: {e}")
            return None

    def get_ip_geo_info(self, ip: str) -> List[DatabaseResult]:
        """
        获取IP地理位置信息
        """

        self.stats['total_queries'] += 1

        # 1. 检查缓存
        if self.cache_enabled:
            current_time = time.time()

            if ip in self._cache:
                cached_results, timestamp = self._cache[ip]

                # 检查缓存是否过期
                if current_time - timestamp < self.cache_ttl:
                    self.cache_stats['hits'] += 1
                    self.cache_stats['size'] = len(self._cache)
                    logger.debug(f"缓存命中: {ip}")
                    # 返回缓存结果的深拷贝
                    return copy.deepcopy(cached_results)
                else:
                    # 缓存过期，删除
                    del self._cache[ip]
                    self.cache_stats['size'] = len(self._cache)

        # 2. 缓存未命中或未启用，执行查询
        if self.cache_enabled:
            self.cache_stats['misses'] += 1

        # 执行原有查询逻辑
        all_results = []
        try:
            # 检查是否为特殊IP
            special_result = self._check_special_ip(ip)
            if special_result:
                all_results.append(special_result)
                self.stats['special_ip_queries'] += 1

                if (special_result.is_special and
                    special_result.country not in ["未知", "-", ""] and
                    self.config.query_config.skip_special_ips):
                    logger.debug(f"跳过数据库查询（特殊IP: {special_result.country}）")
                    # 缓存结果
                    if self.cache_enabled:
                        self._cache[ip] = (copy.deepcopy(all_results), time.time())
                        self.cache_stats['size'] = len(self._cache)
                    return all_results

            # 检查是否为内网IP
            is_private = self._is_private_ip(ip)
            if is_private and self.config.query_config.skip_private_ips:
                logger.debug("识别为内网IP，跳过数据库查询")
                if not special_result:
                    result = DatabaseResult("系统", "", DatabaseType.UNKNOWN)
                    result.country = "内网"
                    result.region = "私有网络"
                    result.success = True
                    result.is_special = True
                    all_results.append(result)
                # 缓存结果
                if self.cache_enabled:
                    self._cache[ip] = (copy.deepcopy(all_results), time.time())
                    self.cache_stats['size'] = len(self._cache)
                return all_results

            # 查询数据库
            if self.config.query_config.strategy == "parallel" and self.config.max_concurrent_queries > 1:
                db_results = self._query_databases_parallel(ip)
            else:
                db_results = self._query_databases_sequential(ip)

            all_results.extend(db_results)
            self.stats['database_queries'] += len(db_results)

            # 统计成功查询
            successful = [r for r in db_results if r.success]
            if successful:
                self.stats['successful_queries'] += 1
            else:
                self.stats['failed_queries'] += 1

            # 如果设置了stop_on_first_success，只返回第一个成功的结果
            if self.config.query_config.stop_on_first_success and len(db_results) > 1:
                success_results = [r for r in db_results if r.success]
                if success_results:
                    filtered_results = []
                    if special_result:
                        filtered_results.append(special_result)
                    filtered_results.append(success_results[0])
                    # 缓存结果
                    if self.cache_enabled:
                        self._cache[ip] = (copy.deepcopy(filtered_results), time.time())
                        self.cache_stats['size'] = len(self._cache)
                        # 简单清理：如果超过最大数量，删除最早的
                        self._cleanup_cache_simple()
                    return filtered_results

            # 缓存结果
            if self.cache_enabled:
                self._cache[ip] = (copy.deepcopy(all_results), time.time())
                self.cache_stats['size'] = len(self._cache)
                # 简单清理：如果超过最大数量，删除最早的
                self._cleanup_cache_simple()

        except Exception as e:
            logger.error(f"查询IP {ip} 地理位置失败: {e}")
            result = DatabaseResult("系统", "", DatabaseType.UNKNOWN)
            result.error = f"查询失败: {str(e)}"
            all_results.append(result)

        return all_results

    def _check_special_ip(self, ip: str) -> Optional[DatabaseResult]:
        """检查是否为特殊IP"""
        try:
            ip_str = ip.split('/')[0] if '/' in ip else ip
            ip_obj = ipaddress.ip_address(ip_str)

            # 检查是否为真正的特殊IP
            is_special = (
                ip_obj.is_private or
                ip_obj.is_loopback or
                ip_obj.is_multicast or
                ip_obj.is_reserved or
                ip_obj.is_link_local
            )

            # 如果不是特殊IP，返回None
            if not is_special:
                logger.debug(f"IP {ip} 不是特殊IP（公网IP），将查询数据库")
                return None

            # 如果是特殊IP，创建结果对象
            result = DatabaseResult("系统识别", "", DatabaseType.UNKNOWN)
            result.success = True
            result.is_special = True

            if ip_obj.is_private:
                result.country = "内网"
                result.region = "私有网络"
                result.city = "局域网"
                result.isp = "内部网络"
                result.network_cidr = "私有地址空间"
                logger.debug(f"识别为内网IP: {ip}")

                # 根据私有地址范围设置更多信息
                if ip_obj.version == 4:
                    if ip_obj in ipaddress.ip_network('10.0.0.0/8'):
                        result.region = "A类私有网络 (10.0.0.0/8)"
                    elif ip_obj in ipaddress.ip_network('172.16.0.0/12'):
                        result.region = "B类私有网络 (172.16.0.0/12)"
                    elif ip_obj in ipaddress.ip_network('192.168.0.0/16'):
                        result.region = "C类私有网络 (192.168.0.0/16)"
                    elif ip_obj in ipaddress.ip_network('169.254.0.0/16'):
                        result.country = "链路本地"
                        result.region = "自动配置地址"
                        result.city = "本地链路"

            elif ip_obj.is_loopback:
                result.country = "本机"
                result.region = "回环地址"
                result.city = "localhost"
                result.isp = "系统"
                result.network_cidr = "127.0.0.0/8" if ip_obj.version == 4 else "::1/128"
                logger.debug(f"识别为回环IP: {ip}")

            elif ip_obj.is_multicast:
                result.country = "组播"
                result.region = "组播网络"
                result.isp = "多播网络"
                result.network_cidr = "224.0.0.0/4" if ip_obj.version == 4 else "ff00::/8"
                logger.debug(f"识别为组播IP: {ip}")

            elif ip_obj.is_reserved:
                result.country = "保留"
                result.region = "保留地址"
                result.isp = "IANA保留"
                logger.debug(f"识别为保留IP: {ip}")

            elif ip_obj.is_link_local:
                result.country = "链路本地"
                result.region = "自动配置地址"
                result.isp = "本地链路"
                logger.debug(f"识别为链路本地IP: {ip}")

            logger.debug(f"识别为特殊IP: {result.country}-{result.region}")
            return result

        except Exception as e:
            logger.debug(f"识别特殊IP失败: {e}")
            return None

    def _is_private_ip(self, ip: str) -> bool:
        """检查是否为内网IP"""
        try:
            ip_str = ip.split('/')[0] if '/' in ip else ip
            ip_obj = ipaddress.ip_address(ip_str)
            return ip_obj.is_private
        except:
            return False

    def _query_databases_sequential(self, ip: str) -> List[DatabaseResult]:
        """串行查询所有数据库"""
        results = []

        for db_config in self.databases:
            start_time = time.time()
            result = self._query_single_database(db_config, ip)
            result.response_time = int((time.time() - start_time) * 1000)
            results.append(result)

            # 如果找到成功结果且设置了停止条件，则停止查询
            if (result.success and
                self.config.query_config.stop_on_first_success and
                self.config.query_config.strategy == "sequential"):
                break

        return results

    def _query_databases_parallel(self, ip: str) -> List[DatabaseResult]:
        """并行查询所有数据库"""
        results = []
        futures = []

        # 提交所有查询任务
        for db_config in self.databases:
            future = self._executor.submit(self._query_single_database_with_time, db_config, ip)
            futures.append(future)

        # 收集结果
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"并行查询数据库失败: {e}")

        # 按优先级排序
        results.sort(key=lambda r: next(
            (db.priority for db in self.databases if db.name == r.source_name),
            999
        ))

        return results

    def _query_single_database_with_time(self, db_config: DatabaseConfig, ip: str) -> DatabaseResult:
        """带时间记录的查询"""
        start_time = time.time()
        result = self._query_single_database(db_config, ip)
        result.response_time = int((time.time() - start_time) * 1000)
        return result

    def _query_single_database(self, db_config: DatabaseConfig, ip: str) -> DatabaseResult:
        """查询单个数据库"""
        db_name = db_config.name
        db_path = db_config.path

        # 检查数据库是否已加载
        if db_name not in self.db_readers:
            db_type = self.db_types.get(db_name, DatabaseType.UNKNOWN)
            result = DatabaseResult(db_name, db_path, db_type)
            result.error = "数据库未加载"
            return result

        try:
            reader = self.db_readers[db_name]
            db_type = self.db_types[db_name]

            if db_type == DatabaseType.MMDB:
                result = self._query_mmdb_database(reader, ip, db_name, db_path)
            elif db_type == DatabaseType.IP2LOCATION_BIN:
                result = self._query_ip2location_database(reader, ip, db_name, db_path)
            else:
                result = DatabaseResult(db_name, db_path, db_type)
                result.error = f"不支持的数据库类型: {db_type.value}"

            return result

        except Exception as e:
            logger.error(f"查询数据库 {db_name} 失败: {e}")
            db_type = self.db_types.get(db_name, DatabaseType.UNKNOWN)
            result = DatabaseResult(db_name, db_path, db_type)
            result.error = f"查询失败: {str(e)}"
            return result

    def _query_mmdb_database(self, reader, ip: str, db_name: str, db_path: str) -> DatabaseResult:
        """查询MMDB格式数据库"""
        result = DatabaseResult(db_name, db_path, DatabaseType.MMDB)

        try:
            data = reader.get(ip)
            logger.debug(f"MMDB数据库 {db_name} 查询IP {ip}")

            if data is None:
                result.error = "IP不在数据库中"
                return result

            # 标记为成功
            result.success = True

            # 提取信息
            # 国家信息
            country = data.get('country')
            if country:
                names = country.get('names', {})
                result.country = names.get('zh-CN') or names.get('en') or '未知'
                result.country_code = country.get('iso_code', '')

            # 地区信息
            subdivisions = data.get('subdivisions')
            if subdivisions and len(subdivisions) > 0:
                region = subdivisions[0]
                names = region.get('names', {})
                result.region = names.get('zh-CN') or names.get('en') or '未知'

            # 城市信息
            city = data.get('city')
            if city:
                names = city.get('names', {})
                result.city = names.get('zh-CN') or names.get('en') or '未知'

            # ISP信息
            traits = data.get('traits', {})
            if traits.get('isp'):
                result.isp = traits['isp']
            if traits.get('organization'):
                result.organization = traits['organization']
            if traits.get('autonomous_system_number'):
                result.asn = f"AS{traits['autonomous_system_number']}"
            if traits.get('autonomous_system_organization'):
                result.as_organization = traits['autonomous_system_organization']

            # 位置坐标
            location = data.get('location')
            if location:
                result.latitude = location.get('latitude')
                result.longitude = location.get('longitude')
                result.timezone = location.get('time_zone')

            # 网络信息
            if traits.get('network'):
                result.network_cidr = str(traits['network'])

            logger.debug(f"MMDB数据库 {db_name} 解析结果: 国家={result.country}, "
            f"地区={result.region}, 城市={result.city}, ISP={result.isp}, ASN={result.asn}")

            return result

        except Exception as e:
            result.error = f"查询异常: {str(e)}"
            return result

    def _query_ip2location_database(self, database, ip: str, db_name: str, db_path: str) -> DatabaseResult:
        """查询IP2Location BIN格式数据库"""
        result = DatabaseResult(db_name, db_path, DatabaseType.IP2LOCATION_BIN)

        try:
            # 查询数据库
            record = database.get_all(ip)
            logger.debug(f"IP2Location数据库 {db_name} 查询IP {ip}")

            if not record or record.country_short == "-":
                result.error = "IP不在数据库中或记录为空"
                return result

            # 标记为成功
            result.success = True

            # 提取信息
            if hasattr(record, 'country_long') and record.country_long and record.country_long != "-":
                result.country = record.country_long
            elif hasattr(record, 'country') and record.country and record.country != "-":
                result.country = record.country

            result.country_code = getattr(record, 'country_short', '')

            # 地区信息
            if hasattr(record, 'region') and record.region and record.region != "-":
                result.region = record.region
            elif hasattr(record, 'state') and record.state and record.state != "-":
                result.region = record.state

            # 城市信息
            if hasattr(record, 'city') and record.city and record.city != "-":
                result.city = record.city

            # ISP信息
            if hasattr(record, 'isp') and record.isp and record.isp != "-":
                result.isp = record.isp
            elif hasattr(record, 'org') and record.org and record.org != "-":
                result.isp = record.org
                result.organization = record.org

            # ASN信息 - 使用getattr避免关键字冲突
            as_value = getattr(record, 'as', None)
            if as_value and str(as_value) != "-":
                result.asn = str(as_value)
            elif hasattr(record, 'asn') and record.asn and record.asn != "-":
                result.asn = f"AS{record.asn}"

            if hasattr(record, 'asname') and record.asname and record.asname != "-":
                result.as_organization = record.asname

            # 地理位置
            if hasattr(record, 'latitude') and record.latitude and str(record.latitude) != "-":
                try:
                    result.latitude = str(record.latitude)
                except:
                    pass
            if hasattr(record, 'longitude') and record.longitude and str(record.longitude) != "-":
                try:
                    result.longitude = str(record.longitude)
                except:
                    pass

            # 时区
            if hasattr(record, 'timezone') and record.timezone and record.timezone != "-":
                result.timezone = record.timezone

            logger.debug(f"IP2Location数据库 {db_name} 解析结果: 国家={result.country}, "
            f"地区={result.region}, 城市={result.city}, ISP={result.isp}, ASN={result.asn}")

            return result

        except Exception as e:
            result.error = f"查询异常: {str(e)}"
            return result

    def get_ip_location_string(self, ip: str) -> str:
        """
        获取IP的位置字符串

        Returns:
            格式化的位置字符串，如"中国-北京-北京"
        """
        try:
            if not self.config.enabled:
                return ""

            results = self.get_ip_geo_info(ip)

            if not results:
                return "❌查询失败"

            logger.debug(f"查询IP {ip} 得到 {len(results)} 个结果")

            # 首先处理特殊IP
            for result in results:
                if result.is_special:
                    # 如果是特殊IP，检查是否有有效的国家信息
                    if result.country and result.country != "未知":
                        location = f"🖥️{result.country}"  # 添加图标
                        if result.region and result.region != "未知":
                            location += f"-{result.region}"
                        logger.debug(f"识别为特殊IP: {location}")
                        return location
                    else:
                        # 特殊IP但没有有效信息，跳过继续查找数据库结果
                        continue

            # 查找数据库成功的结果
            for result in results:
                if result.success and not result.is_special:  # 排除特殊IP
                    # 检查是否有有效的位置信息
                    has_valid_info = False
                    if result.country and result.country not in ["未知", "-", ""]:
                        has_valid_info = True
                    elif result.region and result.region not in ["未知", "-", ""]:
                        has_valid_info = True
                    elif result.city and result.city not in ["未知", "-", ""]:
                        has_valid_info = True

                    if not has_valid_info:
                        logger.debug(f"数据库 {result.source_name} 返回成功但没有有效的位置信息")
                        continue

                    # 使用配置的格式化字符串
                    format_str = self.config.display_config.format_string

                    # 替换变量，过滤空值和"未知"
                    country = result.country if result.country and result.country not in ["未知", "-", ""] else ""
                    region = result.region if result.region and result.region not in ["未知", "-", ""] else ""
                    city = result.city if result.city and result.city not in ["未知", "-", ""] else ""
                    isp = result.isp if result.isp and result.isp not in ["未知", "-", ""] else ""
                    asn = result.asn if result.asn and result.asn not in ["未知", "-", ""] else ""

                    location = format_str.format(
                        country=country,
                        region=region,
                        city=city,
                        isp=isp,
                        asn=asn
                    )

                    # 清理多余的"-"
                    while '--' in location:
                        location = location.replace('--', '-')
                    location = location.strip('-')

                    # 如果所有字段都为空，继续查找其他数据库
                    if not location:
                        continue

                    location = f"📍{location}"  # 添加位置图标
                    logger.debug(f"使用数据库 {result.source_name} 返回位置: {location}")
                    return location

            # 如果没有找到任何有效结果
            # 检查是否有数据库查询失败的情况
            for result in results:
                if result.error and not result.success:
                    logger.debug(f"数据库 {result.source_name} 查询失败: {result.error}")
                    return "❌查询失败"

            # 默认返回未知
            return "❓未知位置"

        except Exception as e:
            logger.error(f"获取IP {ip} 位置字符串失败: {e}", exc_info=True)
            return "⚠️查询异常"

    def get_ip_details(self, ip: str) -> Dict[str, Any]:
        """获取IP的详细地理位置信息"""
        details = {
            'ip': ip,
            'location': '',
            'success': False,
            'is_special': False,
            'sources': []
        }

        try:
            results = self.get_ip_geo_info(ip)

            for result in results:
                source_info = {
                    'source': result.source_name,
                    'type': result.source_type.value,
                    'success': result.success,
                    'response_time': result.response_time
                }

                if result.success or result.is_special:
                    # 基础信息
                    location_info = {
                        'country': result.country,
                        'region': result.region,
                        'city': result.city,
                        'isp': result.isp,
                        'is_special': result.is_special
                    }

                    # 根据显示配置添加详细信息
                    if self.config.display_config.show_asn and result.asn:
                        location_info['asn'] = result.asn
                    if self.config.display_config.show_network and result.network_cidr:
                        location_info['network_cidr'] = result.network_cidr
                    if result.organization:
                        location_info['organization'] = result.organization

                    source_info['data'] = location_info

                    # 设置主要位置信息（使用第一个成功的结果）
                    if not details['success']:
                        details['location'] = self._format_location_string(result)
                        details['success'] = True
                        details['is_special'] = result.is_special
                else:
                    source_info['error'] = result.error

                details['sources'].append(source_info)

        except Exception as e:
            logger.error(f"获取IP {ip} 详细地理位置失败: {e}")
            details['error'] = str(e)

        return details

    def _format_location_string(self, result: DatabaseResult) -> str:
        """格式化位置字符串"""
        parts = []
        if result.country and result.country != "未知":
            parts.append(result.country)
        if result.region and result.region != "未知":
            parts.append(result.region)
        if result.city and result.city != "未知":
            parts.append(result.city)

        if parts:
            return "-".join(parts)
        elif result.is_special:
            return f"{result.country}-{result.region}"
        else:
            return "未知位置"

    def search_ip_online(self, ip: str, url_name: str):
        """
        在浏览器中搜索IP信息

        Args:
            ip: IP地址
            url_name: 要使用的网址名称，如果为None则使用第一个启用的网址
        """
        if not self.config.search_urls.enabled:
            logger.warning("在线搜索功能未启用")
            return False

        urls = self.config.search_urls.urls
        if not urls:
            logger.warning("没有配置搜索网址")
            return False

        try:
            # 查找要使用的网址
            url_to_open = None
            if url_name:
                # 按名称查找
                for url_info in urls:
                    if url_info.get('name') == url_name:
                        url_to_open = url_info['url']
                        break
            else:
                # 使用第一个网址
                if urls:
                    url_to_open = urls[0]['url']

            if not url_to_open:
                logger.warning(f"未找到搜索网址: {url_name}")
                return False

            # 替换IP地址
            formatted_url = url_to_open.replace("{ip}", ip)

            # 打开浏览器
            logger.info(f"在浏览器中打开: {formatted_url}")
            webbrowser.open(formatted_url)

            return True

        except Exception as e:
            logger.error(f"打开搜索网址失败: {e}")
            return False

    def get_search_urls(self) -> List[Dict[str, str]]:
        """获取所有搜索网址"""
        if not self.config.search_urls.enabled:
            return []
        return self.config.search_urls.urls.copy()

    def _cleanup_cache_simple(self):
        """清理缓存 - 只在超过最大数量时清理"""
        if len(self._cache) <= self.cache_max_size:
            return

        # 按时间排序，删除最早的20%
        sorted_items = sorted(self._cache.items(), key=lambda x: x[1][1])
        to_delete_count = max(1, len(sorted_items) // 5)  # 删除20%

        for i in range(to_delete_count):
            key, _ = sorted_items[i]
            del self._cache[key]

        self.cache_stats['size'] = len(self._cache)
        logger.debug(f"缓存清理: 移除了 {to_delete_count} 条记录，当前大小: {len(self._cache)}")

    def clear_cache(self):
        """清空缓存（手动调用）"""
        self._cache.clear()
        self.cache_stats['size'] = 0
        logger.info("已清空IP地理位置缓存")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = self.cache_stats.copy()
        stats['enabled'] = self.cache_enabled
        stats['ttl'] = self.cache_ttl
        stats['max_size'] = self.cache_max_size

        total = stats['hits'] + stats['misses']
        if total > 0:
            stats['hit_rate'] = stats['hits'] / total
        else:
            stats['hit_rate'] = 0.0

        return stats

    def get_stats(self) -> Dict[str, Any]:
        """获取完整的统计信息（包含缓存）"""
        all_stats = self.stats.copy()
        all_stats.update(self.get_cache_stats())
        return all_stats

    def list_databases(self) -> List[Dict[str, Any]]:
        """列出所有数据库信息"""
        db_list = []
        for db_config in self.databases:
            db_name = db_config.name
            db_path = Path(db_config.path)

            db_info = {
                'name': db_name,
                'path': str(db_path),
                'db_type': db_config.db_type,
                'enabled': db_config.enabled,
                'priority': db_config.priority,
                'loaded': db_name in self.db_readers
            }

            if db_name in self.db_types:
                db_info['type'] = self.db_types[db_name].value
            else:
                db_info['type'] = 'unknown'

            if db_path.exists():
                db_info['exists'] = True
                db_info['size'] = db_path.stat().st_size
                db_info['modified'] = time.strftime('%Y-%m-%d %H:%M',
                                                   time.localtime(db_path.stat().st_mtime))
            else:
                db_info['exists'] = False

            db_list.append(db_info)

        return db_list

    def get_database_count(self) -> Dict[str, int]:
        """获取数据库统计"""
        loaded_count = len(self.db_readers)
        enabled_count = len([db for db in self.databases if db.enabled])

        return {
            'total': len(self.databases),
            'loaded': loaded_count,
            'enabled': enabled_count
        }

    def close(self):
        """关闭所有数据库和线程池"""
        # 关闭线程池
        self._executor.shutdown(wait=True)

        # 关闭所有数据库
        for db_name, reader in self.db_readers.items():
            try:
                if hasattr(reader, 'close'):
                    reader.close()
                elif hasattr(reader, 'close_reader'):
                    reader.close_reader()
            except Exception as e:
                logger.debug(f"关闭数据库 {db_name} 失败: {e}")

        self.db_readers.clear()
        logger.info("已关闭所有地理数据库和线程池")
