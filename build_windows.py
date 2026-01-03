#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows平台专用构建脚本
功能：专为Windows平台优化的Nuitka打包工具
要求：仅限Windows系统运行
"""

import os
import sys
import platform
import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict

class WindowsBuilder:
    def __init__(self):
        # 检查操作系统
        self.system = platform.system().lower()
        if self.system != 'windows':
            print("❌ 错误：此脚本仅适用于Windows系统")
            print(f"   当前系统：{platform.system()}")
            print("\n💡 请使用对应平台的构建脚本：")
            print("   Linux: python build_linux.py")
            print("   macOS: python build_macos.py")
            sys.exit(1)

        self.arch = platform.machine().lower()
        self.project_root = Path(__file__).resolve().parent
        self.dist_dir = self.project_root / "dist"
        self.build_logs_dir = self.dist_dir / "build_logs"

        # 应用信息
        self._load_app_info()

        # Visual Studio Build Tools 路径
        self.vs_build_tools_path = self._find_vs_build_tools()

        # UPX配置 - 默认不启用
        self.upx_path = None
        self.upx_available = False
        self.upx_enabled = False  # 默认禁用
        self._detect_upx()

        # 创建必要目录
        self.build_logs_dir.mkdir(exist_ok=True, parents=True)

        # 显示初始化信息
        print(f"\n{'='*60}")
        print(f"🔧 Windows专用构建工具")
        print(f"   应用：{self.app_name} v{self.version}")
        print(f"   平台：Windows {self.arch}")
        print(f"   UPX：{'可用' if self.upx_available else '不可用'}")
        print(f"{'='*60}")

    def _load_app_info(self):
        """从app_info.py加载应用信息"""
        try:
            sys.path.insert(0, str(self.project_root))
            from defaults.app_info import AppInfo
            self.app_name = getattr(AppInfo, 'NAME')
            self.version = getattr(AppInfo, 'VERSION')
            self.author = getattr(AppInfo, 'AUTHOR')

        except ImportError:
            print("⚠️  未找到 defaults/app_info.py，使用默认值")
            self.app_name = "BindInterfaceProxy"
            self.version = "1.0.0"
            self.author = "Takeshi"

        except Exception as e:
            print(f"⚠️  读取应用信息时出错: {e}")
            self.app_name = "BindInterfaceProxy"
            self.version = "1.0.0"
            self.author = "Takeshi"

    def _find_vs_build_tools(self) -> Optional[str]:
        """查找Visual Studio Build Tools"""
        # VS 可能路径
        possible_paths = [
            # VS 2026
            r"C:\Program Files\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
            r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
            r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat",
            # VS 2022
            r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
            # 自定义路径

        ]

        for path in possible_paths:
            if os.path.exists(path):
                print(f"✅ 找到VS构建工具: {path}")
                return path

        print("⚠️  未找到Visual Studio Build Tools")
        return None

    def _detect_upx(self):
        """检测UPX压缩工具可用性"""
        # 检查优先级：环境变量 > 项目目录 > 常见路径 > PATH
        upx_paths = []

        if os.environ.get('UPX_PATH'):
            upx_paths.append(os.environ.get('UPX_PATH'))

        project_upx = self.project_root / "upx" / "upx.exe"
        if project_upx.exists():
            upx_paths.append(str(project_upx))

        common_paths = [
            r"C:\Program Files\upx\upx.exe",
            r"C:\Program Files (x86)\upx\upx.exe",
            r"C:\upx\upx.exe",
        ]
        upx_paths.extend(common_paths)

        upx_paths.append("upx.exe")

        for upx_candidate in upx_paths:
            if self._verify_upx(upx_candidate):
                self.upx_path = upx_candidate
                self.upx_available = True
                break

        if self.upx_available:
            print(f"✅ UPX可用: {self.upx_path}")
        else:
            print("ℹ️  UPX不可用")

    def _verify_upx(self, upx_path: str) -> bool:
        """验证UPX可执行文件"""
        try:
            result = subprocess.run(
                [upx_path, '--version'],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0 and 'UPX' in result.stdout
        except:
            return False

    def _check_compiler(self) -> bool:
        """检查编译器状态"""
        try:
            result = subprocess.run(
                'where cl.exe',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except:
            return False

    def _activate_vs_environment(self) -> Tuple[bool, str]:
        """激活MSVC环境"""
        if not self.vs_build_tools_path:
            return False, "未找到Visual Studio Build Tools路径"

        print(f"\n🔧 正在激活MSVC环境...")
        print(f"  使用激活脚本: {self.vs_build_tools_path}")

        # 创建激活批处理
        activation_script = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.bat',
            delete=False,
            encoding='utf-8'
        )

        activation_script.write(f'''@echo off
echo 正在激活Visual Studio Build Tools环境...
call "{self.vs_build_tools_path}"

echo ===============================
echo 环境激活完成
echo ===============================

echo 检查编译器...
where cl.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ cl.exe 可用
    cl.exe 2>&1 | findstr /i "Microsoft" >nul
    if %errorlevel% equ 0 (
        echo ✓ Microsoft C++ 编译器就绪
    )
)

echo.
echo 当前环境变量：
echo PATH中包含的编译器：
where cl.exe 2>nul
where link.exe 2>nul
where nmake.exe 2>nul

echo.
set > "%TEMP%\\vs_env_vars.txt"
echo 环境变量已保存到：%TEMP%\\vs_env_vars.txt

exit 0
''')

        activation_script.close()
        bat_path = activation_script.name

        try:
            # 运行激活脚本
            print("  执行激活脚本...")
            result = subprocess.run(
                ['cmd', '/c', bat_path],
                capture_output=True,
                text=True,
                encoding='gbk',
                errors='replace',
                timeout=30
            )

            # 读取保存的环境变量
            env_vars_file = os.path.join(os.environ.get('TEMP', ''), 'vs_env_vars.txt')
            if os.path.exists(env_vars_file):
                try:
                    with open(env_vars_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if '=' in line:
                                key, value = line.split('=', 1)
                                os.environ[key] = value
                    print("  ✓ 已更新环境变量")
                except:
                    pass

            # 清理临时文件
            try:
                os.unlink(bat_path)
                if os.path.exists(env_vars_file):
                    os.unlink(env_vars_file)
            except:
                pass

            if result.returncode == 0:
                print("✅ MSVC环境激活成功")

                # 验证编译器
                verify_result = subprocess.run(
                    'where cl.exe && cl.exe 2>&1 | findstr /i Microsoft',
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='gbk'
                )

                if verify_result.returncode == 0:
                    print("  ✓ 编译器验证通过")
                    return True, "MSVC环境已激活并验证"
                else:
                    print("  ⚠️  编译器验证失败，但环境可能已激活")
                    return True, "MSVC环境可能已激活"
            else:
                error_msg = result.stderr[:500] if result.stderr else "未知错误"
                return False, f"激活失败: {error_msg}"

        except Exception as e:
            try:
                os.unlink(bat_path)
            except:
                pass
            return False, f"激活异常: {str(e)}"

    def _check_msvc_tools(self) -> Tuple[bool, str]:
        """检查MSVC编译器状态"""
        print("\n🔍 检查MSVC编译器...")

        checks = [
            ("cl.exe", "C/C++ 编译器"),
            ("link.exe", "链接器"),
            ("mt.exe", "清单工具"),
            ("rc.exe", "资源编译器"),
        ]

        all_ok = True
        for tool, description in checks:
            try:
                result = subprocess.run(
                    ['where', tool],
                    capture_output=True,
                    text=True,
                    shell=True,
                    timeout=5
                )

                if result.returncode == 0:
                    path = result.stdout.strip().split('\n')[0]
                    print(f"  ✓ {description}: {path}")
                else:
                    print(f"  ✗ {description}: 未找到")
                    all_ok = False
            except Exception as e:
                print(f"  ✗ {description}: 检查失败 - {e}")
                all_ok = False

        # 检查cl.exe版本
        if all_ok:
            try:
                version_result = subprocess.run(
                    ['cl.exe'],
                    capture_output=True,
                    text=True,
                    shell=True,
                    timeout=5
                )

                output = version_result.stdout + version_result.stderr
                if 'Microsoft' in output:
                    # 提取版本信息
                    for line in output.split('\n'):
                        if 'Version' in line:
                            print(f"  📊 {line.strip()}")
                            break
                else:
                    print("  ⚠️  无法获取编译器版本")
            except:
                print("  ⚠️  无法检查编译器版本")

        return all_ok, "编译器检查完成"

    def _prepare_build_environment(self) -> bool:
        """准备Windows构建环境"""
        print(f"\n{'='*60}")
        print("准备Windows构建环境")
        print(f"{'='*60}")

        # 1. 检查是否已激活
        print("\n1. 检查当前环境状态...")
        compiler_ok, msg = self._check_msvc_tools()

        if compiler_ok:
            print("✅ MSVC编译器已就绪")
            return True

        # 2. 检查VS构建工具路径
        print("\n2. 检查Visual Studio构建工具...")
        if not self.vs_build_tools_path:
            print("❌ 未找到Visual Studio Build Tools")
            self._show_vs_installation_guide()
            return False

        # 3. 激活环境
        print("\n3. 激活MSVC环境...")
        success, msg = self._activate_vs_environment()

        if not success:
            print(f"❌ {msg}")

            # 提供手动激活指南
            print(f"\n💡 手动激活指南:")
            print(f"  1. 打开命令提示符 (cmd.exe)")
            print(f"  2. 运行: \"{self.vs_build_tools_path}\"")
            print(f"  3. 然后在此窗口中重新运行此脚本")
            print(f"  4. 或者直接在激活的环境中运行构建")

            return False

        # 4. 再次检查编译器
        print("\n4. 验证激活结果...")
        compiler_ok, msg = self._check_msvc_tools()

        if not compiler_ok:
            print("❌ 编译器仍然不可用")
            print("💡 请尝试重启命令行或电脑后重试")
            return False

        print("\n✅ Windows构建环境准备完成")
        return True

    def _show_vs_installation_guide(self):
        """显示VS安装指南"""
        print("""
📚 Visual Studio 安装指南：

选项A: 安装 Visual Studio Build Tools 2022
   1. 下载: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
   2. 运行安装程序
   3. 工作负载选择: 'C++ 生成工具'
   4. 安装详情中确保勾选:
      - MSVC v143 - VS 2022 C++ x64/x86 生成工具
      - Windows 10/11 SDK
      - C++ CMake 工具

选项B: 安装完整 Visual Studio 2022
   1. 下载: https://visualstudio.microsoft.com/downloads/
   2. 选择: '使用C++的桌面开发'
   3. 完成安装

选项C: 使用已安装的Visual Studio
   请手动运行对应版本的vcvars64.bat
   例如: "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat"

安装完成后，请重启命令行窗口并重新运行此脚本。
""")

    def _analyze_main_file(self) -> Dict:
        """分析主程序文件"""
        main_file = self.project_root / 'main.py'

        analysis = {
            'exists': main_file.exists(),
            'gui_framework': 'Console',
            'has_main_check': False,
        }

        if not analysis['exists']:
            return analysis

        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查入口点
            if 'if __name__ == "__main__":' in content:
                analysis['has_main_check'] = True

            # 检测GUI框架
            if 'PySide6' in content:
                analysis['gui_framework'] = 'PySide6'
            elif 'PyQt5' in content:
                analysis['gui_framework'] = 'PyQt5'
            elif 'PyQt6' in content:
                analysis['gui_framework'] = 'PyQt6'
            elif 'tkinter' in content:
                analysis['gui_framework'] = 'Tkinter'

        except Exception as e:
            print(f"⚠️  文件分析异常: {e}")

        return analysis

    def _configure_upx(self) -> bool:
        """配置UPX选项"""
        if not self.upx_available:
            print("❌ UPX不可用，无法启用")
            return False

        print(f"\n⚙️  UPX配置")
        print(f"   路径: {self.upx_path}")

        # 显示版本信息
        try:
            result = subprocess.run(
                [self.upx_path, '--version'],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                if lines:
                    print(f"   版本: {lines[0]}")
        except:
            pass

        print("\n💡 UPX压缩可减小文件体积，但可能增加启动时间")
        choice = input("是否启用UPX压缩? (y/n, 默认n): ").strip().lower()

        if choice == 'y':
            self.upx_enabled = True
            print("✅ UPX压缩已启用")
        else:
            self.upx_enabled = False
            print("ℹ️  UPX压缩已禁用")

        return self.upx_enabled

    def _copy_distribution_files(self, target_dir: Path):
        """复制分发文件到目标目录"""
        print("\n📄 复制分发文件...")

        # 需要复制的文件列表
        distribution_files = [
            ('LICENSE', '许可证文件'),
            ('THIRD-PARTY-NOTICES.txt', '第三方组件声明'),
            ('README.md', '使用说明'),
            # ('README.txt', '使用说明'),
            # ('CHANGELOG.md', '更新日志'),
            # ('CHANGELOG.txt', '更新日志'),
        ]

        copied_count = 0
        for filename, description in distribution_files:
            source_path = self.project_root / filename

            if not source_path.exists():
                continue  # 文件不存在，跳过

            try:
                target_path = target_dir / filename
                shutil.copy2(source_path, target_path)
                print(f"  ✓ {description}: {filename}")
                copied_count += 1
            except Exception as e:
                print(f"  ✗ {description}: 复制失败 - {e}")

        if copied_count > 0:
            print(f"✅ 已复制 {copied_count} 个分发文件")
        else:
            print("⚠️  未复制任何分发文件")

        return copied_count

    def _create_build_command(self, main_file: Path, with_console: bool, analysis: Dict) -> Tuple[List[str], str]:
        """创建构建命令"""
        cmd = [sys.executable, '-m', 'nuitka', '--standalone']

        # 核心参数
        cmd.extend([
            '--follow-imports',
            '--assume-yes-for-downloads',
            '--remove-output',
            '--show-progress',
        ])

        # Windows特定参数
        cmd.extend([
            '--msvc=latest',
            '--warn-implicit-exceptions',
        ])

        # 控制台设置
        if with_console:
            cmd.append('--windows-console-mode=force')
        else:
            cmd.append('--windows-console-mode=disable')

        # UPX配置（通过Nuitka插件）
        if self.upx_enabled and self.upx_available:
            cmd.extend([
                '--plugin-enable=upx',
                f'--upx-binary={self.upx_path}',
            ])
            print(f"📦 UPX压缩已启用（Nuitka插件）")

        # GUI框架插件
        if analysis['gui_framework'] == 'PySide6':
            cmd.append('--enable-plugin=pyside6')
        elif analysis['gui_framework'] == 'PyQt5':
            cmd.append('--enable-plugin=pyqt5')
        elif analysis['gui_framework'] == 'PyQt6':
            cmd.append('--enable-plugin=pyqt6')
        elif analysis['gui_framework'] == 'Tkinter':
            cmd.append('--enable-plugin=tk-inter')

        # 图标
        icon_candidates = [
            self.project_root / 'resources' / 'icons' / 'app_icon.ico',
            self.project_root / 'resources' / 'icons' / 'app_icon.png',
            self.project_root / 'app_icon.ico',
        ]

        for icon_path in icon_candidates:
            if icon_path.exists():
                cmd.append(f'--windows-icon-from-ico={icon_path}')
                break

        # 包含数据目录
        data_dirs = ['resources']
        for data_dir in data_dirs:
            full_path = self.project_root / data_dir
            if full_path.exists():
                cmd.append(f'--include-data-dir={full_path}={data_dir}')

        # windows版本信息
        try:
            from defaults.app_info import AppInfo
            win_info = AppInfo.get_windows_version_info()
            cmd.extend([
                f'--product-name={win_info["product_name"]}',
                f'--product-version={win_info["product_version"]}',
                f'--file-description={win_info["product_name"]}',
                f'--file-version={win_info["file_version"]}',
                f'--company-name={win_info["company_name"]}',
                f'--copyright={win_info["legal_copyright"]}',
            ])
            print("🏷️  已添加Windows版本信息")
        except Exception as e:
            print(f"⚠️  读取Windows版本信息失败: {e}")
            # 使用默认值
            cmd.extend([
                f'--product-name={self.app_name}',
                f'--product-version={self.version}',
                f'--file-description={self.app_name}',
                f'--file-version=1.0.0.0',
                f'--company-name={self.author}',
                f'--copyright=Copyright © 2025 {self.author}',
            ])

        # 输出设置
        output_name = self.app_name

        if with_console:
            output_name += "_console"

        cmd.extend([
            f'--output-dir={self.dist_dir}',
            f'--output-filename={output_name}',
            str(main_file)
        ])

        return cmd, output_name

    def _execute_build(self, cmd: List[str], output_name: str) -> Optional[Path]:
        """执行构建命令"""
        print(f"\n{'='*50}")
        print("开始构建")
        print(f"{'='*50}")

        # 创建日志文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.build_logs_dir / f"build_{timestamp}.log"

        start_time = datetime.now()
        print(f"⏳ 构建开始: {start_time.strftime('%H:%M:%S')}")

        try:
            with open(log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"构建命令: {' '.join(cmd)}\n")
                log_f.write(f"开始时间: {start_time}\n\n")

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                # 简化输出处理
                last_progress = ""
                for line in process.stdout:
                    line = line.rstrip()
                    log_f.write(line + '\n')

                    # 只显示关键信息
                    if 'progress:' in line.lower():
                        # 只显示不同的进度信息
                        if line != last_progress:
                            print(f"  {line}")
                            last_progress = line
                    elif any(keyword in line.lower() for keyword in ['error:', 'failed:', 'fatal:']):
                        print(f"  ❌ {line}")
                    elif any(keyword in line.lower() for keyword in ['done', 'success', 'complete']):
                        print(f"  ✅ {line}")
                    elif 'upx' in line.lower() and ('compressing' in line.lower() or 'packed' in line.lower()):
                        print(f"  📦 {line}")

                process.wait()
                end_time = datetime.now()
                elapsed = end_time - start_time

                log_f.write(f"\n结束时间: {end_time}\n")
                log_f.write(f"耗时: {elapsed.total_seconds():.1f}秒\n")
                log_f.write(f"退出码: {process.returncode}\n")

            print(f"⏱️  构建耗时: {elapsed.total_seconds():.1f}秒")

            if process.returncode == 0:
                print("✅ 构建成功")
                return self._locate_output_file(output_name)
            else:
                print(f"❌ 构建失败，退出码: {process.returncode}")
                return None

        except Exception as e:
            print(f"❌ 构建异常: {e}")
            return None

    def _locate_output_file(self, output_name: str) -> Optional[Path]:
        """定位生成的输出文件"""
        # 查找可执行文件
        exe_path = self.dist_dir / f"main.dist" / f"{output_name}.exe"

        if exe_path.exists():
            # 计算整个main.dist文件夹的大小
            folder_size = 0
            for path in exe_path.parent.rglob('*'):
                if path.is_file():
                    folder_size += path.stat().st_size

            size_mb = folder_size / 1024 / 1024

            # 显示可执行文件大小
            exe_size_mb = exe_path.stat().st_size / 1024 / 1024

            print(f"📦 可执行文件: {exe_path}")
            print(f"📊 文件大小: {exe_size_mb:.2f} MB")
            print(f"📁 文件夹总大小: {size_mb:.2f} MB")

            # ✅ 复制分发文件到输出目录
            self._copy_distribution_files(exe_path.parent)

            # 显示文件夹内容摘要
            print(f"📂 文件夹内容:")
            for item in sorted(exe_path.parent.iterdir()):
                if item.is_file():
                    item_size = item.stat().st_size / 1024  # KB
                    print(f"    📄 {item.name} ({item_size:.1f} KB)")
                elif item.is_dir():
                    # 计算子文件夹大小
                    sub_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file()) / 1024
                    print(f"    📁 {item.name}/ ({sub_size:.1f} KB)")

            return exe_path

        # 备选查找（兼容不同版本的Nuitka输出）
        possible_paths = [
            self.dist_dir / f"{output_name}.dist" / f"{output_name}.exe",
            self.dist_dir / f"{output_name}.exe",
            self.dist_dir / f"{output_name}.dist" / f"{output_name}.exe",
        ]

        for path in possible_paths:
            if path.exists():
                # 计算文件夹大小（如果是.dist文件夹）
                folder_size = 0
                folder_path = path.parent

                if folder_path.exists() and folder_path.is_dir():
                    for item in folder_path.rglob('*'):
                        if item.is_file():
                            folder_size += item.stat().st_size

                size_mb = folder_size / 1024 / 1024
                exe_size_mb = path.stat().st_size / 1024 / 1024

                print(f"📦 可执行文件: {path}")
                print(f"📊 文件大小: {exe_size_mb:.2f} MB")
                print(f"📁 文件夹总大小: {size_mb:.2f} MB")

                # ✅ 复制分发文件到输出目录
                self._copy_distribution_files(path.parent)

                return path

        print("⚠️  未找到可执行文件")
        return None

    def _clean_old_builds(self):
        """清理旧的构建文件"""
        print("\n🧹 清理旧构建...")

        patterns = ["build", ".build", "*.dist"]
        cleaned = 0

        for pattern in patterns:
            for path in self.project_root.rglob(pattern):
                if path.is_dir():
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                        cleaned += 1
                    except:
                        pass

        if cleaned > 0:
            print(f"✅ 清理完成，删除了 {cleaned} 个目录")
        else:
            print("ℹ️  无需清理")

    def build(self, with_console: bool = False):
        """执行构建"""
        print(f"\n🔨 开始构建: {'带控制台' if with_console else '无控制台'}版本")

        # 检查主文件
        main_file = self.project_root / 'main.py'
        if not main_file.exists():
            print(f"❌ 主文件不存在: {main_file}")
            return False

        # 分析主文件
        analysis = self._analyze_main_file()
        if not analysis['exists']:
            print("❌ 无法找到主文件")
            return False

        if not analysis['has_main_check']:
            print("⚠️  主文件可能缺少入口点")

        print(f"📄 主程序: {main_file.name}")
        print(f"🖥️  框架: {analysis['gui_framework']}")

        # 准备环境
        if not self._prepare_build_environment():
            print("❌ 构建环境准备失败")
            return False

        # UPX配置询问
        if self.upx_available:
            self._configure_upx()

        # 清理旧构建
        self._clean_old_builds()

        # 创建构建命令
        cmd, output_name = self._create_build_command(main_file, with_console, analysis)

        print(f"\n📋 完整构建命令:")
        print(' '.join(cmd))

        # 执行构建
        result = self._execute_build(cmd, output_name)

        if result:

            print(f"\n🎉 构建完成！")
            print(f"   输出目录: {result.parent}")
            print(f"\n📦 分发说明:")
            print(f"   1. 整个 '{result.parent.name}' 文件夹已包含所有必要文件")
            print(f"   2. 请手动压缩为ZIP格式分发")
            print(f"   3. 包含文件: LICENSE, THIRD-PARTY-NOTICES.txt, README.md 等")
            return True
        else:
            print("\n❌ 构建失败")
            return False

    def diagnose(self):
        """系统诊断"""
        print(f"\n{'='*60}")
        print("🔍 系统诊断")
        print(f"{'='*60}")

        # Python信息
        print(f"\n📝 Python环境:")
        print(f"   版本: {platform.python_version()}")
        print(f"   路径: {sys.executable}")

        # Nuitka检查
        print(f"\n📦 Nuitka检查:")
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'nuitka', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"   版本: {result.stdout.strip()}")
            else:
                print("   ❌ 未安装")
        except:
            print("   ❌ 未安装")

        # 编译器检查
        print(f"\n🔧 编译器检查:")
        compiler_ok, _ = self._check_msvc_tools()
        print(f"   状态: {'✅ 就绪' if compiler_ok else '❌ 未找到'}")

        if self.vs_build_tools_path:
            print(f"   📍 VS构建工具: {self.vs_build_tools_path}")
        else:
            print("   ❌ 未找到VS构建工具")

        # UPX检查
        print(f"\n📦 UPX检查:")
        if self.upx_available:
            print(f"   状态: 可用")
            print(f"   路径: {self.upx_path}")
            print(f"   启用: {'是' if self.upx_enabled else '否'}")
        else:
            print("   ❌ 不可用")

        # 分发文件检查
        print(f"\n📄 分发文件检查:")
        distribution_files = ['LICENSE', 'THIRD-PARTY-NOTICES.txt', 'README.md',]# 'CHANGELOG.md']
        for filename in distribution_files:
            file_path = self.project_root / filename
            if file_path.exists():
                file_size = file_path.stat().st_size / 1024
                print(f"   ✅ {filename} ({file_size:.1f} KB)")
            else:
                print(f"   ⚠️  {filename} (未找到)")

        # 主文件检查
        print(f"\n📄 主文件检查:")
        main_file = self.project_root / 'main.py'
        if main_file.exists():
            analysis = self._analyze_main_file()
            print(f"   ✅ 存在: {main_file}")
            print(f"   框架: {analysis['gui_framework']}")
            print(f"   入口点: {'✅' if analysis['has_main_check'] else '❌'}")
        else:
            print(f"   ❌ 不存在: {main_file}")

    def run(self):
        """运行主界面"""
        while True:
            try:
                print(f"\n请选择操作:")
                print(f"  1. 构建无控制台版本 (发布)")
                print(f"  2. 构建带控制台版本 (调试)")
                print(f"  3. 系统诊断")
                print(f"  4. 清理构建文件")
                print(f"  5. 退出")

                choice = input(f"\n请输入选项 (1-5): ").strip()

                if choice == '1':
                    self.build(with_console=False)
                elif choice == '2':
                    self.build(with_console=True)
                elif choice == '3':
                    self.diagnose()
                elif choice == '4':
                    self._clean_old_builds()
                elif choice == '5':
                    print("👋 再见！")
                    break
                else:
                    print("❌ 无效选项")

                # 询问是否继续
                if choice in ['1', '2', '3', '4']:
                    continue_choice = input("\n是否继续? (y/n, 默认y): ").strip().lower()
                    if continue_choice == 'n':
                        print("👋 再见！")
                        break
                    print("\n" + "="*60)

            except KeyboardInterrupt:
                print("\n\n🛑 用户中断")
                break
            except Exception as e:
                print(f"❌ 错误: {e}")

def main():
    """主函数"""
    try:
        builder = WindowsBuilder()
        builder.run()
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()
