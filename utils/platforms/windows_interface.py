"""
Windows 网络接口实现
"""

import winreg
from typing import Optional, List
from .network_interface import BaseNetworkInterface

class WindowsNetworkInterface(BaseNetworkInterface):
    """Windows 网络接口实现"""

    def _get_ip_by_iface_name(self, iface_name: str) -> Optional[str]:
        """通过接口名称获取IP地址"""
        # 先尝试通过注册表查找
        guid = self._get_guid_by_adapter_iface_name(iface_name)
        if guid:
            return self._get_ip_by_guid(guid)

        # 如果注册表找不到，尝试特殊名称
        if iface_name == '本地回环':
            return '127.0.0.1'
        elif 'loopback' in iface_name.lower() or 'lo' in iface_name.lower():
            return '127.0.0.1'
        elif iface_name == '所有接口':
            return '0.0.0.0'

        return None

    def _get_iface_name_by_ip(self, ip: str) -> Optional[str]:
        """通过IP地址获取接口名称"""
        guid = self._get_guid_by_ip(ip)
        if guid:
            return self._get_iface_name_by_guid(guid)

        # 特殊IP处理
        if ip == '127.0.0.1':
            return '本地回环'
        elif ip == '0.0.0.0':
            return '所有接口'

        return f"接口-{ip}"

    def get_available_interfaces(self) -> List[dict]:
        """获取所有可用的网络接口"""
        interfaces = []

        # 添加特殊接口
        interfaces.append({'iface_name': '本地回环', 'ip': '127.0.0.1'})
        interfaces.append({'iface_name': '所有接口', 'ip': '0.0.0.0'})

        # 从注册表获取物理接口
        try:
            base_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}")
            index = 0
            while True:
                try:
                    guid = winreg.EnumKey(base_key, index)
                    iface_name = self._get_iface_name_by_guid(guid)
                    ip = self._get_ip_by_guid(guid)

                    if iface_name and ip and ip != "0.0.0.0":
                        interfaces.append({'iface_name': iface_name, 'ip': ip})

                    index += 1
                except OSError:
                    break
            winreg.CloseKey(base_key)
        except Exception:
            pass

        return interfaces

    # Windows 特定的辅助方法
    def _get_guid_by_adapter_iface_name(self, iface_name: str) -> Optional[str]:
        """通过适配器名称获取GUID"""
        try:
            base_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}")
            index = 0
            while True:
                try:
                    guid = winreg.EnumKey(base_key, index)
                    conn_path = f"{r'SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}'}\\{guid}\\Connection"
                    try:
                        conn_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, conn_path)
                        iface_name_value, _ = winreg.QueryValueEx(conn_key, "Name")
                        winreg.CloseKey(conn_key)
                        if iface_name_value == iface_name:
                            winreg.CloseKey(base_key)
                            return guid
                    except (FileNotFoundError, OSError):
                        pass
                    index += 1
                except OSError:
                    break
            winreg.CloseKey(base_key)
        except Exception:
            pass
        return None

    def _get_iface_name_by_guid(self, guid: str) -> Optional[str]:
        """通过GUID获取接口名称"""
        try:
            conn_path = f"{r'SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}'}\\{guid}\\Connection"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, conn_path)
            iface_name, _ = winreg.QueryValueEx(key, "Name")
            winreg.CloseKey(key)
            return iface_name
        except Exception:
            return None

    def _get_ip_by_guid(self, guid: str) -> Optional[str]:
        """通过GUID获取IP地址"""
        try:
            interfaces_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{interfaces_path}\\{guid}")

            # 尝试获取IP地址
            try:
                ip_value, _ = winreg.QueryValueEx(key, "DhcpIPAddress")
            except FileNotFoundError:
                try:
                    ip_value, _ = winreg.QueryValueEx(key, "IPAddress")
                except FileNotFoundError:
                    winreg.CloseKey(key)
                    return None

            winreg.CloseKey(key)

            # 处理IP值
            if isinstance(ip_value, (list, tuple)) and len(ip_value) > 0:
                for ip in ip_value:
                    if ip and ip.strip() and ip != "0.0.0.0":
                        return ip.strip()
            elif isinstance(ip_value, str) and ip_value and ip_value != "0.0.0.0":
                return ip_value.strip()

        except Exception:
            pass
        return None

    def _get_guid_by_ip(self, ip: str) -> Optional[str]:
        """通过IP地址获取GUID"""
        try:
            interfaces_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            base_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, interfaces_path)
            index = 0
            while True:
                try:
                    guid = winreg.EnumKey(base_key, index)
                    current_ip = self._get_ip_by_guid(guid)
                    if current_ip == ip:
                        winreg.CloseKey(base_key)
                        return guid
                    index += 1
                except OSError:
                    break
            winreg.CloseKey(base_key)
        except Exception:
            pass
        return None
