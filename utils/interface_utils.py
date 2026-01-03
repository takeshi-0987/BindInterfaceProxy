"""
跨平台网络接口工具函数
支持 Windows、Linux、macOS
"""

import sys
from typing import List, Dict, Tuple, Any
import psutil

# 根据操作系统选择实现
if sys.platform == "win32":
    from .platforms.windows_interface import WindowsNetworkInterface as NetworkInterface
elif sys.platform == "linux":
    from .platforms.linux_interface import LinuxNetworkInterface as NetworkInterface
elif sys.platform == "darwin":  # macOS
    from .platforms.macos_interface import MacOSNetworkInterface as NetworkInterface
else:
    # 回退到基础实现
    from .platforms.network_interface import BaseNetworkInterface as NetworkInterface

def get_outbound_interfaces():
    """
    获取真实网卡列表（流量出口）
    排除虚拟接口、回环接口，只返回真实物理接口
    """
    real_interfaces = []

    try:
        net_stats = psutil.net_if_stats()

        # 真实网卡通常有以下特征，虚拟接口通常没有
        for iface, stats in net_stats.items():
            if not stats or not stats.isup:
                continue

            iface_lower = iface.lower()

            # 排除虚拟/回环接口
            exclude_keywords = [
                'loopback', 'lo',  # 回环
                'zerotier', 'tap', 'tun',  # 虚拟隧道
                'veth', 'docker', 'br-', 'virbr',  # 容器
                'vboxnet', 'vmnet', 'vethernet',  # 虚拟机
                'bluetooth', '蓝牙',  # 蓝牙
                'ppp', 'pppoe',  # 拨号
            ]

            # 检查是否排除
            should_exclude = any(keyword in iface_lower for keyword in exclude_keywords)

            if not should_exclude:
                # 真实网卡通常有MAC地址且不是回环
                try:
                    addrs = psutil.net_if_addrs().get(iface, [])
                    has_mac = any(addr.family == psutil.AF_LINK for addr in addrs)

                    if has_mac:  # 有MAC地址的是真实网卡
                        # 美化显示名称
                        display_name = iface
                        if 'wlan' in iface_lower or 'wireless' in iface_lower or 'wifi' in iface_lower:
                            display_name = f"📶 {iface} (无线)"
                        elif 'ethernet' in iface_lower or '以太网' in iface:
                            display_name = f"🔌 {iface} (有线)"
                        elif '本地连接' in iface:
                            display_name = f"🌐 {iface}"

                        NetworkInterface(iface_name=iface)

                        real_interfaces.append({
                            'iface_name': iface,
                            'display_name': display_name,
                            'is_up': stats.isup,
                            'speed': stats.speed
                        })
                except:
                    pass

    except Exception as e:
        print(f"获取网卡列表时出错: {e}")

    # 按速度排序（最快的在前面）
    # real_interfaces.sort(key=lambda x: x['speed'], reverse=True)

    return real_interfaces

def get_listening_interfaces():
    """
    获取监听网卡列表（包括本地回环）
    用于绑定监听地址
    """
    listening_interfaces = []

    try:
        net_stats = psutil.net_if_stats()

        # 首先添加本地回环
        for iface, stats in net_stats.items():
            iface_lower = iface.lower()
            try:
                NetworkInterface(iface_name=iface)
                if 'loopback' in iface_lower or 'lo' in iface_lower:
                    listening_interfaces.append({
                        'iface_name': iface,
                        'display_name': f"🔄 {iface} (本地回环)",
                        'is_up': stats.isup if stats else True,
                        'is_loopback': True,
                        'speed': stats.speed,
                    })
                    break
            except:
                pass

        # 添加其他所有接口（包括真实和虚拟）
        for iface, stats in net_stats.items():
            iface_lower = iface.lower()
            try:
                # 跳过已添加的回环接口
                if 'loopback' in iface_lower or 'lo' in iface_lower:
                    continue

                # 确定显示名称
                display_name = iface
                if 'wlan' in iface_lower or 'wireless' in iface_lower:
                    display_name = f"📶 {iface} (无线)"
                elif 'ethernet' in iface_lower or '以太网' in iface:
                    display_name = f"🔌 {iface} (有线)"
                elif 'zerotier' in iface_lower:
                    display_name = f"🛰️ {iface} (ZeroTier)"
                elif 'tap' in iface_lower or 'tun' in iface_lower:
                    display_name = f"🔗 {iface} (虚拟隧道)"
                elif 'bluetooth' in iface_lower or '蓝牙' in iface:
                    display_name = f"📱 {iface} (蓝牙)"
                elif '本地连接' in iface:
                    display_name = f"🌐 {iface} (虚拟机)"

                NetworkInterface(iface_name=iface)
                listening_interfaces.append({
                    'iface_name': iface,
                    'display_name': display_name,
                    'is_up': stats.isup if stats else False,
                    'is_loopback': False,
                    'speed': stats.speed,
                })
            except:
                pass

    except Exception as e:
        print(f"获取监听网卡列表时出错: {e}")

    # listening_interfaces.sort(key=lambda x: x['speed'], reverse=True)

    return listening_interfaces

def generate_all_interfaces(config_list: List[Dict]) -> Tuple[List[NetworkInterface], List[Dict]]:
    """根据配置列表生成 NetworkInterface 实例列表"""
    valid_interfaces = []
    invalid_configs = []

    for cfg in config_list:
        try:
            iface = NetworkInterface(**cfg)
            valid_interfaces.append(iface)

        except (ValueError, NotImplementedError) as e:
            invalid_configs.append(cfg)

    return valid_interfaces, invalid_configs

def unique_interfaces(iface_list: List[NetworkInterface]) -> List[NetworkInterface]:
    """根据 (ip, port) 去重接口列表"""
    unique = {}
    for iface in iface_list:
        key = (iface.ip, iface.port)
        if key not in unique:
            unique[key] = iface
    return list(unique.values())

def get_sock5_config(iface: NetworkInterface) -> Dict[str, Any]:
    return {
        "auth_enabled": getattr(iface, "auth_enabled", False),
        "security_enabled": getattr(iface, "security_enabled", False),
        "proxy_protocol": getattr(iface, "proxy_protocol", None),
    }

def get_http_config(iface: NetworkInterface) -> Dict[str, Any]:
    return {
        "auth_enabled": getattr(iface, "auth_enabled", False),
        "security_enabled": getattr(iface, "security_enabled", False),
        "proxy_protocol": getattr(iface, "proxy_protocol", None),
        "use_https": getattr(iface, "use_https", False),
        "cert_file": getattr(iface, "cert_file", None),
        "key_file": getattr(iface, "key_file", None),
    }
