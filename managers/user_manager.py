# -*- coding: utf-8 -*-
"""
Module: user_manager.py
Author: Takeshi
Date: 2025-11-08
Update: 2025-11-09 (添加缓存功能)

Description:
    用户管理模块，使用密码哈希存储
"""

import os
import logging
import secrets
import hashlib
import base64
import time
import threading
from typing import Tuple, Dict, List
import hmac

from defaults.user_default import USERS_CACHE_ENABLED, USERS_CACHE_CHECK_INTERVAL


logger = logging.getLogger(__name__)


class PasswordHasher:
    """安全的密码哈希工具类"""

    def __init__(self):
        # 使用安全的哈希参数
        self.hash_algorithm = 'sha256'  # 或 'sha512'
        self.iterations = 100000  # PBKDF2迭代次数
        self.salt_length = 16     # 盐值长度（字节）

    def generate_salt(self) -> bytes:
        """生成安全的随机盐值"""
        return secrets.token_bytes(self.salt_length)

    def hash_password(self, password: str) -> str:
        """
        哈希密码（使用PBKDF2）
        格式: algorithm:iterations:salt:hash
        """
        # 生成随机盐值
        salt = self.generate_salt()

        # 使用PBKDF2进行密码哈希
        hashed = hashlib.pbkdf2_hmac(
            self.hash_algorithm,
            password.encode('utf-8'),
            salt,
            self.iterations
        )

        # 转换为可存储的格式
        salt_b64 = base64.b64encode(salt).decode('ascii')
        hash_b64 = base64.b64encode(hashed).decode('ascii')

        return f"pbkdf2:{self.hash_algorithm}:{self.iterations}:{salt_b64}:{hash_b64}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """验证密码是否匹配存储的哈希"""
        try:
            # 解析存储的哈希字符串
            parts = stored_hash.split(':')
            if len(parts) != 5:
                return False

            algorithm = parts[0]
            hash_algo = parts[1]
            iterations = int(parts[2])
            salt = base64.b64decode(parts[3])
            stored_hash_bytes = base64.b64decode(parts[4])

            if algorithm != 'pbkdf2':
                logger.error(f"不支持的哈希算法: {algorithm}")
                return False

            # 计算输入密码的哈希
            computed_hash = hashlib.pbkdf2_hmac(
                hash_algo,
                password.encode('utf-8'),
                salt,
                iterations
            )

            # 使用恒定时间比较防止时序攻击
            return hmac.compare_digest(computed_hash, stored_hash_bytes)

        except Exception as e:
            logger.error(f"密码验证失败: {e}")
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        """检查是否需要重新哈希（参数已过时）"""
        try:
            parts = stored_hash.split(':')
            if len(parts) != 5:
                return True

            algorithm = parts[0]
            hash_algo = parts[1]
            iterations = int(parts[2])

            return (algorithm != 'pbkdf2' or
                    hash_algo != self.hash_algorithm or
                    iterations < self.iterations)

        except Exception:
            return True


class UserManager:
    def __init__(self, users_file: str):
        self.hasher = PasswordHasher()
        self.users_file = users_file

        # 缓存相关属性
        self._users_cache = None  # 缓存用户数据 {username: password_hash}
        self._cache_lock = threading.RLock()  # 缓存读写锁
        self._file_mtime = 0  # 缓存对应的文件最后修改时间
        self._last_cache_time = 0  # 最后缓存时间

        # 缓存配置

        self._cache_check_interval = USERS_CACHE_CHECK_INTERVAL  # 缓存检查间隔（秒）
        self._cache_enabled = USERS_CACHE_ENABLED  # 是否启用缓存

        # 确保用户文件目录存在
        self._ensure_users_file()

    def _ensure_users_file(self):
        """确保用户文件目录存在"""
        file_dir = os.path.dirname(self.users_file)
        if file_dir and not os.path.exists(file_dir):
            os.makedirs(file_dir, exist_ok=True)

    def _load_users_dict(self) -> Dict[str, str]:
        """从文件加载用户字典"""
        users = {}
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and ':' in line:
                            # 用户名和哈希之间用冒号分隔
                            username, password_hash = line.split(':', 1)
                            users[username] = password_hash
                logger.debug(f"✅ 已从 {self.users_file} 加载 {len(users)} 个用户")
            except Exception as e:
                logger.error(f"❌ 加载用户文件失败: {e}")
                # 如果文件损坏，可以备份并创建新的
                if os.path.exists(self.users_file):
                    backup = f"{self.users_file}.bak"
                    try:
                        os.rename(self.users_file, backup)
                        logger.warning(f"⚠️ 用户文件已备份到: {backup}")
                    except Exception as rename_error:
                        logger.error(f"❌ 备份文件失败: {rename_error}")
        return users

    def _save_users_dict(self, users: Dict[str, str]) -> bool:
        """保存用户字典到文件"""
        temp_file = ""
        try:
            # 确保目录存在
            self._ensure_users_file()

            # 先写入临时文件，然后重命名（原子操作）
            temp_file = f"{self.users_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                for username, password_hash in users.items():
                    f.write(f"{username}:{password_hash}\n")

            # 原子替换文件
            if os.path.exists(self.users_file):
                os.replace(temp_file, self.users_file)
            else:
                os.rename(temp_file, self.users_file)

            # 更新文件修改时间
            self._update_file_mtime()

            # 使缓存失效，强制下次重新加载
            self._invalidate_cache()

            logger.info(f"✅ 用户数据已安全保存到 {self.users_file}")
            return True
        except Exception as e:
            logger.error(f"❌ 保存用户文件失败: {e}")
            # 清理临时文件
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as remove_error:
                    logger.error(f"❌ 清理临时文件失败: {remove_error}")
            return False

    def _get_current_file_mtime(self) -> float:
        """获取当前文件的最后修改时间"""
        try:
            if os.path.exists(self.users_file):
                return os.path.getmtime(self.users_file)
        except Exception as e:
            logger.error(f"❌ 获取文件修改时间失败: {e}")
        return 0

    def _update_file_mtime(self):
        """更新记录的文件修改时间"""
        try:
            self._file_mtime = self._get_current_file_mtime()
        except Exception as e:
            logger.error(f"❌ 更新文件修改时间失败: {e}")

    def _invalidate_cache(self):
        """使缓存失效"""
        with self._cache_lock:
            self._users_cache = None
            logger.debug("🔄 用户缓存已失效")

    def _get_users_from_cache_or_file(self) -> Dict[str, str]:
        """
        从缓存或文件获取用户数据
        如果缓存有效则使用缓存，否则从文件加载
        """
        current_time = time.time()

        with self._cache_lock:
            # 如果缓存未启用，直接读取文件
            if not self._cache_enabled:
                users = self._load_users_dict()
                self._update_file_mtime()
                return users

            # 检查是否需要刷新缓存
            need_refresh = False
            if self._users_cache is None:
                need_refresh = True
                logger.debug("🔄 缓存为空，需要刷新")
            elif current_time - self._last_cache_time > self._cache_check_interval:
                # 检查文件是否被修改
                current_mtime = self._get_current_file_mtime()
                if current_mtime > self._file_mtime:
                    need_refresh = True
                    logger.debug(f"🔄 文件已修改，需要刷新缓存 (缓存时间: {self._file_mtime}, 当前时间: {current_mtime})")

            # 如果需要刷新，重新加载数据
            if need_refresh:
                try:
                    self._users_cache = self._load_users_dict()
                    self._update_file_mtime()
                    self._last_cache_time = current_time
                    logger.debug(f"🔄 缓存已刷新，加载了 {len(self._users_cache)} 个用户")
                except Exception as e:
                    logger.error(f"❌ 刷新缓存失败: {e}")
                    # 如果刷新失败，但缓存不为空，继续使用旧缓存
                    if self._users_cache is None:
                        self._users_cache = {}

            return self._users_cache.copy() if self._users_cache else {}

    def load_users(self) -> Dict[str, str]:
        """
        从文件加载用户数据
        这个方法返回的是 {username: 'hash:...'} 格式
        """
        users_dict = self._get_users_from_cache_or_file()

        result = {}
        for username, password_hash in users_dict.items():
            result[username] = password_hash
        return result

    def save_users(self, users: Dict[str, str]) -> bool:
        """
        保存用户数据到文件
        这里期望的是 {username: password} 或 {username: 'hash:...'}
        """
        users_to_save = {}

        for username, password_data in users.items():
            if password_data.startswith('pbkdf2:'):
                # 已经是哈希格式，直接保存
                users_to_save[username] = password_data
            else:
                # 明文密码，进行哈希
                try:
                    users_to_save[username] = self.hasher.hash_password(password_data)
                except Exception as e:
                    logger.error(f"❌ 密码哈希失败: {e}")
                    return False

        success = self._save_users_dict(users_to_save)
        if success:
            # 更新缓存
            with self._cache_lock:
                self._users_cache = users_to_save.copy()
                self._update_file_mtime()
                self._last_cache_time = time.time()
        return success

    def add_user(self, username: str, password: str) -> Tuple[bool, str]:
        """添加用户"""
        # 输入验证
        if not username or not password:
            return False, "用户名和密码不能为空"
        if len(username) > 50:
            return False, "用户名过长"

        users = self._get_users_from_cache_or_file()
        if username in users:
            return False, "用户名已存在"

        # 哈希密码
        try:
            password_hash = self.hasher.hash_password(password)
        except Exception as e:
            logger.error(f"❌ 密码哈希失败: {e}")
            return False, "密码处理失败"

        users[username] = password_hash
        if self._save_users_dict(users):
            # 更新缓存
            with self._cache_lock:
                if self._users_cache is not None:
                    self._users_cache[username] = password_hash
            return True, "用户添加成功"
        else:
            return False, "保存用户数据失败"

    def update_user(self, username: str, new_password: str) -> Tuple[bool, str]:
        """更新用户密码"""
        users = self._get_users_from_cache_or_file()
        if username not in users:
            return False, "用户不存在"

        # 哈希新密码
        try:
            password_hash = self.hasher.hash_password(new_password)
        except Exception as e:
            logger.error(f"❌ 密码哈希失败: {e}")
            return False, "密码处理失败"

        users[username] = password_hash
        if self._save_users_dict(users):
            # 更新缓存
            with self._cache_lock:
                if self._users_cache is not None:
                    self._users_cache[username] = password_hash
            return True, "密码更新成功"
        else:
            return False, "保存用户数据失败"

    def delete_user(self, username: str) -> Tuple[bool, str]:
        """删除用户"""
        users = self._get_users_from_cache_or_file()
        if username not in users:
            return False, "用户不存在"

        del users[username]
        if self._save_users_dict(users):
            # 更新缓存
            with self._cache_lock:
                if self._users_cache is not None and username in self._users_cache:
                    del self._users_cache[username]
            return True, "用户删除成功"
        else:
            return False, "保存用户数据失败"

    def list_users(self) -> List[str]:
        """获取用户列表"""
        users = self._get_users_from_cache_or_file()
        return list(users.keys())

    def get_user_count(self) -> int:
        """获取用户数量"""
        users = self._get_users_from_cache_or_file()
        return len(users)

    def verify_user_credentials(self, username: str, password: str) -> bool:
        """验证用户凭据"""
        users = self._get_users_from_cache_or_file()

        if username not in users:
            # 使用恒定时间操作防止用户枚举攻击
            self.hasher.verify_password(password, "pbkdf2:sha256:100000:dummy:dummy")
            return False

        stored_hash = users[username]

        # 验证密码
        is_valid = self.hasher.verify_password(password, stored_hash)

        # 如果需要重新哈希（参数已更新）
        if is_valid and self.hasher.needs_rehash(stored_hash):
            try:
                # 重新哈希密码
                new_hash = self.hasher.hash_password(password)

                # 异步更新文件和缓存
                def _async_update():
                    try:
                        # 重新加载最新的用户数据
                        current_users = self._get_users_from_cache_or_file()
                        current_users[username] = new_hash
                        if self._save_users_dict(current_users):
                            logger.info(f"🔄 用户 {username} 的密码已重新哈希并保存")
                    except Exception as e:
                        logger.warning(f"⚠️ 异步重新哈希保存失败: {e}")

                # 使用线程异步执行
                import threading
                thread = threading.Thread(target=_async_update, daemon=True)
                thread.start()

            except Exception as e:
                logger.warning(f"⚠️ 密码重新哈希失败: {e}")

        return is_valid

    # ===== 缓存管理方法 =====

    def clear_cache(self) -> bool:
        """清空缓存"""
        with self._cache_lock:
            self._users_cache = None
            self._file_mtime = 0
            self._last_cache_time = 0
            logger.info("🗑️ 用户缓存已清空")
            return True

    def refresh_cache(self, force: bool = False) -> bool:
        """刷新缓存"""
        try:
            with self._cache_lock:
                if force or self._users_cache is None:
                    self._users_cache = self._load_users_dict()
                    self._update_file_mtime()
                    self._last_cache_time = time.time()
                    logger.info(f"🔄 用户缓存已刷新，{len(self._users_cache)} 个用户")
                    return True
                else:
                    logger.debug("🔄 缓存未过期，无需刷新")
                    return False
        except Exception as e:
            logger.error(f"❌ 刷新缓存失败: {e}")
            return False

    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        with self._cache_lock:
            return {
                "cache_enabled": self._cache_enabled,
                "cache_size": len(self._users_cache) if self._users_cache else 0,
                "last_cache_time": self._last_cache_time,
                "file_mtime": self._file_mtime,
                "current_file_mtime": self._get_current_file_mtime(),
                "cache_check_interval": self._cache_check_interval
            }

    def enable_cache(self, enabled: bool = True):
        """启用或禁用缓存"""
        with self._cache_lock:
            self._cache_enabled = enabled
            if not enabled:
                self._users_cache = None
            logger.info(f"🔄 缓存已{'启用' if enabled else '禁用'}")

    def set_cache_check_interval(self, interval: int):
        """设置缓存检查间隔（秒）"""
        if interval > 0:
            with self._cache_lock:
                self._cache_check_interval = interval
                logger.info(f"🔄 缓存检查间隔已设置为 {interval} 秒")
