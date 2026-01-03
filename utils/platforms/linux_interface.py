"""
Linux 网络接口实现
"""

import subprocess
import re
from typing import Optional, List
from .network_interface import BaseNetworkInterface

class LinuxNetworkInterface(BaseNetworkInterface):
    """Linux 网络接口实现"""

    def _get_ip_by_iface_name(self, iface_name: str) -> Optional[str]:
        """通过接口名称获取IP地址"""
        try:
            # 使用 ip 命令获取接口IP
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show', iface_name],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                # 解析IP地址
                match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass

        # 特殊名称处理
        if iface_name == '本地回环' or iface_name == 'lo':
            return '127.0.0.1'
        elif 'loopback' in iface_name.lower() or 'lo' in iface_name.lower():
            return '127.0.0.1'
        elif iface_name == '所有接口':
            return '0.0.0.0'

        return None

    def _get_iface_name_by_ip(self, ip: str) -> Optional[str]:
        """通过IP地址获取接口名称"""
        try:
            # 使用 ip 命令查找对应接口
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show'],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                current_interface = None

                for line in lines:
                    # 检测接口行
                    interface_match = re.match(r'^\d+:\s+(\w+):', line)
                    if interface_match:
                        current_interface = interface_match.group(1)

                    # 检测IP行
                    ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match and ip_match.group(1) == ip and current_interface:
                        return current_interface

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass

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

        try:
            # 使用 ip 命令获取所有接口
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show'],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                current_interface = None

                for line in lines:
                    # 检测接口行
                    interface_match = re.match(r'^\d+:\s+(\w+):', line)
                    if interface_match:
                        current_interface = interface_match.group(1)

                    # 检测IP行
                    ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match and current_interface:
                        ip = ip_match.group(1)
                        if ip != "127.0.0.1":  # 跳过回环地址，因为已经单独添加了
                            interfaces.append({'iface_name': current_interface, 'ip': ip})

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass

        return interfaces
