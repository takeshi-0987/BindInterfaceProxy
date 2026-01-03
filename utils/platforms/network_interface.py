"""
跨平台网络接口基类
"""

import ipaddress
from typing import Optional, List
from abc import ABC, abstractmethod

class BaseNetworkInterface(ABC):
    """
    网络接口基类
    核心特征:
        iface_name - 网卡名称，如WLAN
        ip - 网卡地址，仅ipv4，如'127.0.0.1'
        port - 网络端口, 如80

    """

    def __init__(self, iface_name: str = "", ip: str = "", port: int = 0, **kwargs):

        self.iface_name = iface_name
        self.ip = ip
        self.port = port

        # 验证iface_name, ip至少提供一个参数
        if not any([iface_name, ip]):
            raise ValueError("必须提供 iface_name 或 ip 中的一个")


        # 根据提供的参数初始化, 优先利用ip初始化iface_name，没有提供ip则尝试利用iface_name初始化ip
        if ip:
            self._init_by_ip(ip)
        elif iface_name:
            self._init_by_iface_name(iface_name)

        # 最终验证
        if not self.ip:
            raise ValueError("无法获取有效的IP地址")

        # 验证端口
        if not (0 <= port <= 65535):
            raise ValueError("端口号必须在0到65535之间")
        self.port = port

        # 收集其他配置信息
        for key, value in kwargs.items():
            setattr(self, key, value)


    def _init_by_ip(self, ip: str):
        """通过IP初始化"""
        try:
            self.ip = ipaddress.ip_address(ip).exploded
        except ValueError:
            raise ValueError(f"无效的IP地址: {ip}")

        # 如果只有IP没有iface_name，尝试通过IP获取接口名称
        if self.iface_name is None:
            self.iface_name = self._get_iface_name_by_ip(self.ip) or f"接口-{self.ip}"


    def _init_by_iface_name(self, iface_name: str):
        """通过名称初始化"""
        self.iface_name = iface_name
        # 通过名称获取IP
        self.ip = self._get_ip_by_iface_name(iface_name)
        if self.ip is None:
            raise ValueError(f"无法通过接口名称获取IP地址: {iface_name}")

    @abstractmethod
    def _get_ip_by_iface_name(self, iface_name: str) -> Optional[str]:
        """通过接口名称获取IP地址 - 子类实现"""
        pass

    @abstractmethod
    def _get_iface_name_by_ip(self, ip: str) -> Optional[str]:
        """通过IP地址获取接口名称 - 子类实现"""
        pass

    @abstractmethod
    def get_available_interfaces(self) -> List[dict]:
        """获取所有可用的网络接口 - 子类实现"""
        pass

    def __repr__(self):
        # 1. 获取所有实例属性字典
        attrs = ', '.join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"NetworkInterface({attrs})"

    # def __str__(self):
    #     auth_status = "认证" if getattr(self, 'auth_enabled', True) else "无认证"
    #     return f"{self.iface_name} ({self.ip}:{self.port}) [{auth_status}]"
