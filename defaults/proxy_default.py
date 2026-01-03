# -*- coding: utf-8 -*-
"""
Module: proxy_default.py
Author: Takeshi
Date: 2025-12-25

Description:
    出口网卡配置类
"""


from dataclasses import dataclass, field, asdict
from typing import Optional, Literal, List, Dict, Any


@dataclass
class OutboundInterface:
    """
    出口网络接口配置类

    定义代理服务器使用的出口网络接口（网卡）配置。
    用于绑定特定的网络接口，实现多出口、负载均衡或特定网络路由。

    Attributes:
        iface_name (str): 网络接口名称
            操作系统识别的网络接口名称，如 'eth0', 'wlan0', '以太网' 等
            为空字符串时使用系统默认接口
            默认: ''（使用默认接口）

        ip (str): 绑定的IP地址
            指定出口接口的IP地址，支持IPv4地址
            用于在多IP主机上指定具体的出口IP
            为空字符串时使用接口的主IP地址
            默认: ''（使用接口主IP）

        port (int): 绑定的源端口
            指定代理服务器使用的本地源端口号
            0表示由操作系统自动分配
            特定端口可用于防火墙规则或网络策略
            默认: 0（自动分配）

    Methods:
        to_dict() -> Dict[str, Any]:
            将配置转换为字典格式，便于序列化存储

        from_dict(data: Dict[str, Any]) -> 'OutboundInterface':
            从字典创建配置实例，便于从配置文件加载

    Example:
        >>> # 绑定到特定网卡
        >>> interface = OutboundInterface(
        ...     iface_name='eth0',
        ...     ip='192.168.1.100',
        ...     port=0
        ... )
        >>>
        >>> # 使用默认接口
        >>> default_interface = OutboundInterface()
    """

    iface_name: str = ""
    ip: str = ""
    port: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有接口配置的字典
        """
        return {
            'iface_name': self.iface_name,
            'ip': self.ip,
            'port': self.port
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutboundInterface':
        """从字典创建配置实例

        Args:
            data: 包含接口配置信息的字典

        Returns:
            OutboundInterface: 新的配置实例
        """
        return cls(
            iface_name=data.get('iface_name', ''),
            ip=data.get('ip', ''),
            port=data.get('port', 0)
        )


@dataclass
class Socks5Proxy:
    """
    SOCKS5代理服务器配置类

    配置单个SOCKS5代理服务器的各项参数。
    SOCKS5协议支持TCP和UDP代理，常用于需要完整网络层代理的场景。

    Attributes:
        proxy_name (str): 代理服务器名称
            用于标识和显示此代理服务器的名称
            建议使用有意义的名称，如 '公司代理'、'家庭网络代理'
            默认: ''（未命名）

        iface_name (str): 监听的网络接口名称
            代理服务器监听的网络接口名称
            继承自OutboundInterface配置
            默认: ''（使用默认接口）

        ip (str): 监听IP地址
            代理服务器监听的本地IP地址
            '0.0.0.0' 表示监听所有网络接口
            '127.0.0.1' 表示仅本地访问
            默认: ''（使用默认监听地址）

        port (int): 监听端口
            代理服务器监听的本地端口号
            常用端口：1080（标准SOCKS5端口）
            需要确保端口未被占用且有访问权限
            默认: 1080

        auth_enabled (bool): 是否启用身份验证
            True: 客户端需要提供用户名和密码
            False: 允许匿名连接
            建议生产环境启用身份验证
            默认: False

        security_enabled (bool): 是否启用安全功能
            True: 启用额外的安全检查（如IP黑名单、连接限制）
            False: 只提供基本代理功能
            默认: False

        proxy_protocol (Optional[Literal['v1', 'v2']]): 代理协议版本
            'v1': HAProxy Proxy Protocol版本1
            'v2': HAProxy Proxy Protocol版本2
            None: 不使用代理协议
            用于在代理链中传递客户端真实IP
            默认: None

    Note:
        1. SOCKS5协议支持完整的TCP和UDP代理
        2. 启用身份验证可提高安全性，但会增加客户端配置复杂度
        3. 代理协议通常用于多层代理架构
        4. 建议为不同的代理用途使用不同的端口号
    """

    proxy_name: str = ""
    iface_name: str = ""
    ip: str = ""
    port: int = 1080
    auth_enabled: bool = False
    security_enabled: bool = False
    proxy_protocol: Optional[Literal['v1', 'v2']] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有SOCKS5代理配置的字典
        """
        return {
            'proxy_name': self.proxy_name,
            'iface_name': self.iface_name,
            'ip': self.ip,
            'port': self.port,
            'auth_enabled': self.auth_enabled,
            'security_enabled': self.security_enabled,
            'proxy_protocol': self.proxy_protocol
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Socks5Proxy':
        """从字典创建配置实例

        Args:
            data: 包含SOCKS5代理配置信息的字典

        Returns:
            Socks5Proxy: 新的配置实例
        """
        return cls(
            proxy_name=data.get('proxy_name', ''),
            iface_name=data.get('iface_name', ''),
            ip=data.get('ip', ''),
            port=data.get('port', 1080),
            auth_enabled=data.get('auth_enabled', False),
            security_enabled=data.get('security_enabled', False),
            proxy_protocol=data.get('proxy_protocol')
        )


@dataclass
class HttpProxy:
    """
    HTTP代理服务器配置类

    配置单个HTTP/HTTPS代理服务器的各项参数。
    HTTP代理主要用于Web浏览器和应用层的HTTP/HTTPS流量代理。

    Attributes:
        proxy_name (str): 代理服务器名称
            用于标识和显示此代理服务器的名称
            建议使用有意义的名称，如 'Web代理'、'安全代理'
            默认: ''（未命名）

        iface_name (str): 监听的网络接口名称
            代理服务器监听的网络接口名称
            默认: ''（使用默认接口）

        ip (str): 监听IP地址
            代理服务器监听的本地IP地址
            '0.0.0.0' 表示监听所有网络接口
            '127.0.0.1' 表示仅本地访问
            默认: ''（使用默认监听地址）

        port (int): 监听端口
            代理服务器监听的本地端口号
            常用端口：8080（HTTP代理标准端口）
            需要确保端口未被占用且有访问权限
            默认: 1080

        auth_enabled (bool): 是否启用身份验证
            True: 客户端需要提供用户名和密码
            False: 允许匿名连接
            建议生产环境启用身份验证
            默认: False

        security_enabled (bool): 是否启用安全功能
            True: 启用额外的安全检查
            False: 只提供基本代理功能
            默认: False

        proxy_protocol (Optional[Literal['v1', 'v2']]): 代理协议版本
            'v1': HAProxy Proxy Protocol版本1
            'v2': HAProxy Proxy Protocol版本2
            None: 不使用代理协议
            默认: None

        use_https (bool): 是否启用HTTPS
            True: 使用HTTPS加密连接
            False: 使用普通HTTP连接
            HTTPS可提供端到端加密，提高安全性
            默认: False

        cert_file (str): SSL证书文件路径
            用于HTTPS的SSL/TLS证书文件路径
            支持.pem、.crt等格式
            当use_https=True时必须配置
            默认: ''（未配置）

        key_file (str): SSL私钥文件路径
            对应证书的私钥文件路径
            需要保持与证书匹配
            当use_https=True时必须配置
            默认: ''（未配置）

    Note:
        1. HTTP代理主要用于HTTP/HTTPS流量，不支持其他协议
        2. 启用HTTPS可防止流量被中间人窃听
        3. 身份验证建议使用Basic Auth或Digest Auth
        4. 证书和私钥需要正确配对，否则HTTPS无法正常工作
        5. 可考虑使用自签名证书或Let's Encrypt免费证书
    """

    proxy_name: str = ""
    iface_name: str = ""
    ip: str = ""
    port: int = 1080
    auth_enabled: bool = False
    security_enabled: bool = False
    proxy_protocol: Optional[Literal['v1', 'v2']] = None
    use_https: bool = False
    cert_file: str = ""
    key_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有HTTP代理配置的字典
        """
        return {
            'proxy_name': self.proxy_name,
            'iface_name': self.iface_name,
            'ip': self.ip,
            'port': self.port,
            'auth_enabled': self.auth_enabled,
            'security_enabled': self.security_enabled,
            'proxy_protocol': self.proxy_protocol,
            'use_https': self.use_https,
            'cert_file': self.cert_file,
            'key_file': self.key_file
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HttpProxy':
        """从字典创建配置实例

        Args:
            data: 包含HTTP代理配置信息的字典

        Returns:
            HttpProxy: 新的配置实例
        """
        return cls(
            proxy_name=data.get('proxy_name', ''),
            iface_name=data.get('iface_name', ''),
            ip=data.get('ip', ''),
            port=data.get('port', 1080),
            auth_enabled=data.get('auth_enabled', False),
            security_enabled=data.get('security_enabled', False),
            proxy_protocol=data.get('proxy_protocol'),
            use_https=data.get('use_https', False),
            cert_file=data.get('cert_file', ''),
            key_file=data.get('key_file', '')
        )
