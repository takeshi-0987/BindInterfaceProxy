#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linux平台专用构建脚本
功能：专为Linux平台优化的Nuitka打包工具
要求：仅限Linux系统运行
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict

class LinuxBuilder:
    def __init__(self):
        # 检查操作系统
        self.system = platform.system().lower()
        if self.system != 'linux':
            print("❌ 错误：此脚本仅适用于Linux系统")
            print(f"   当前系统：{platform.system()}")
            print("\n💡 请使用对应平台的构建脚本：")
            print("   Windows: python build_windows.py")
            print("   macOS: python build_macos.py")
            sys.exit(1)

        self.arch = platform.machine().lower()
        self.project_root = Path(__file__).resolve().parent
        self.dist_dir = self.project_root / "dist"
        self.build_logs_dir = self.dist_dir / "build_logs"

        # 应用信息
        self._load_app_info()

        # UPX配置 - 默认不启用
        self.upx_path = None
        self.upx_available = False
        self.upx_enabled = False  # 默认禁用
        self._detect_upx()

        # 编译器状态缓存
        self._compiler_available = None

        # 创建必要目录
        self.build_logs_dir.mkdir(exist_ok=True, parents=True)

        # 显示初始化信息
        print(f"\n{'='*60}")
        print(f"🔧 Linux专用构建工具")
        print(f"   应用：{self.app_name} v{self.version}")
        print(f"   平台：Linux {self.arch}")
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

    def _detect_upx(self):
        """检测UPX压缩工具可用性"""
        # Linux下常见的UPX路径
        upx_paths = [
            "upx",  # 系统PATH
            "/usr/bin/upx",
            "/usr/local/bin/upx",
            str(self.project_root / "upx" / "upx"),  # 项目目录
        ]

        # 检查环境变量
        if os.environ.get('UPX_PATH'):
            upx_paths.insert(0, os.environ.get('UPX_PATH'))

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
                timeout=3
            )
            return result.returncode == 0 and 'UPX' in result.stdout
        except:
            return False

    def _check_compiler(self) -> bool:
        """检查编译器状态"""
        if self._compiler_available is not None:
            return self._compiler_available

        # Linux下检查gcc或clang
        compilers_to_check = ['gcc', 'clang']

        for compiler in compilers_to_check:
            try:
                result = subprocess.run(
                    ['which', compiler],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self._compiler_available = True
                    print(f"✅ 找到编译器: {compiler}")
                    return True
            except:
                continue

        self._compiler_available = False
        return False

    def _check_system_dependencies(self) -> Dict:
        """检查系统依赖"""
        print("\n🔍 检查系统依赖...")

        dependencies = {
            'build-essential': 'GNU编译工具链',
            'python3-dev': 'Python开发头文件',
        }

        results = {}
        missing_deps = []

        # 检测发行版
        distro = self._detect_distribution()

        for pkg, description in dependencies.items():
            try:
                if distro in ['ubuntu', 'debian']:
                    result = subprocess.run(
                        ['dpkg', '-s', pkg],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    installed = result.returncode == 0
                elif distro in ['centos', 'fedora', 'rhel']:
                    result = subprocess.run(
                        ['rpm', '-q', pkg],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    installed = result.returncode == 0
                else:
                    # 未知发行版，假设已安装
                    installed = True

                if installed:
                    print(f"  ✓ {description}")
                    results[pkg] = True
                else:
                    print(f"  ✗ {description}: 未安装")
                    results[pkg] = False
                    missing_deps.append(pkg)

            except Exception as e:
                print(f"  ? {description}: 无法检查 ({e})")
                results[pkg] = None

        if missing_deps:
            print(f"\n⚠️  缺少的依赖包:")
            for dep in missing_deps:
                print(f"  - {dep}")
            print(f"\n📦 安装命令:")
            if distro in ['ubuntu', 'debian']:
                print(f"  sudo apt-get install " + " ".join(missing_deps))
            elif distro in ['centos', 'fedora', 'rhel']:
                print(f"  sudo yum install " + " ".join(missing_deps))

        return results

    def _detect_distribution(self) -> str:
        """检测Linux发行版"""
        try:
            # 检查/etc/os-release
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('ID='):
                            return line.strip().split('=')[1].strip('"').lower()
        except:
            pass

        # 检查其他发行版文件
        distro_files = {
            '/etc/debian_version': 'debian',
            '/etc/redhat-release': 'centos',
            '/etc/fedora-release': 'fedora',
            '/etc/arch-release': 'arch',
        }

        for file, distro in distro_files.items():
            if os.path.exists(file):
                return distro

        return 'unknown'

    def _prepare_build_environment(self) -> bool:
        """准备构建环境"""
        print("\n📋 准备构建环境...")

        # 检查编译器
        if not self._check_compiler():
            print("❌ 未找到GCC或Clang编译器")
            print("\n💡 安装编译器:")
            print("  Debian/Ubuntu: sudo apt-get install build-essential")
            print("  CentOS/RHEL: sudo yum groupinstall 'Development Tools'")
            print("  Fedora: sudo dnf groupinstall 'Development Tools'")
            return False

        # 检查系统依赖
        deps_result = self._check_system_dependencies()

        # 如果有未安装的依赖，警告但不阻止构建
        missing_deps = [pkg for pkg, status in deps_result.items() if status is False]
        if missing_deps:
            print("⚠️  缺少部分依赖，构建可能会失败")
            print("   建议安装缺少的依赖包")

        print("✅ 构建环境准备完成")
        return True

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

    def _create_build_command(self, main_file: Path, analysis: Dict) -> Tuple[List[str], str]:
        """创建构建命令"""
        cmd = [sys.executable, '-m', 'nuitka', '--standalone']

        # 核心参数
        cmd.extend([
            '--follow-imports',
            '--assume-yes-for-downloads',
            '--remove-output',
            '--show-progress',
        ])

        # Linux特定参数
        cmd.extend([
            '--enable-plugin=anti-bloat',
        ])

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

        # 包含数据目录
        data_dirs = ['resources']
        for data_dir in data_dirs:
            full_path = self.project_root / data_dir
            if full_path.exists():
                cmd.append(f'--include-data-dir={full_path}={data_dir}')

        # 输出设置
        output_name = self.app_name.lower().replace(' ', '-')

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
                    errors='replace'
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
        exe_path = self.dist_dir / f"main.dist" / output_name

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

            # 添加执行权限
            try:
                exe_path.chmod(0o755)
                print("🔒 已添加执行权限")
            except:
                pass

            return exe_path

        # 备选查找
        possible_paths = [
            self.dist_dir / f"{output_name}.dist" / output_name,
            self.dist_dir / output_name,
        ]

        for path in possible_paths:
            if path.exists():
                # 计算文件夹大小
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

                # 添加执行权限
                try:
                    path.chmod(0o755)
                except:
                    pass

                return path

        print("⚠️  未找到可执行文件")
        return None

    def _create_launcher_script(self, exe_path: Path):
        """创建启动脚本"""
        launcher_path = exe_path.parent / "run.sh"

        launcher_content = f'''#!/bin/bash
echo ""
echo "════════════════════════════════════════════════"
echo "   {self.app_name} v{self.version}"
echo "   Build Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
echo "   Platform: Linux {self.arch}"
echo "════════════════════════════════════════════════"
echo ""

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "Starting {self.app_name}..."
sleep 1

if [ -f "{exe_path.name}" ]; then
    chmod +x "{exe_path.name}"
    "./{exe_path.name}"
else
    echo "ERROR: Cannot find {exe_path.name}"
    echo ""
    echo "Available files:"
    ls -la
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi
'''

        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write(launcher_content)

        # 添加执行权限
        launcher_path.chmod(0o755)

        print(f"📜 创建启动脚本: run.sh")

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

    def build(self):
        """执行构建"""
        print(f"\n🔨 开始构建")

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
        cmd, output_name = self._create_build_command(main_file, analysis)

        print(f"\n📋 完整构建命令:")
        print(' '.join(cmd))

        # 执行构建
        result = self._execute_build(cmd, output_name)

        if result:
            # 创建启动脚本
            self._create_launcher_script(result)

            print(f"\n🎉 构建完成！")
            print(f"   输出目录: {result.parent}")
            print(f"\n📦 分发说明:")
            print(f"   1. 整个 '{result.parent.name}' 文件夹已包含所有必要文件")
            print(f"   2. 请手动压缩为tar.gz格式分发: tar -czf package.tar.gz {result.parent.name}/")
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
        if self._check_compiler():
            print("   ✅ GCC/Clang编译器就绪")
        else:
            print("   ❌ 未找到GCC或Clang编译器")

        # 系统依赖检查
        print(f"\n📦 系统依赖检查:")
        deps = self._check_system_dependencies()

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
                print(f"  1. 构建应用")
                print(f"  2. 系统诊断")
                print(f"  3. 清理构建文件")
                print(f"  4. 退出")

                choice = input(f"\n请输入选项 (1-4): ").strip()

                if choice == '1':
                    self.build()
                elif choice == '2':
                    self.diagnose()
                elif choice == '3':
                    self._clean_old_builds()
                elif choice == '4':
                    print("👋 再见！")
                    break
                else:
                    print("❌ 无效选项")

                # 询问是否继续
                if choice in ['1', '2', '3']:
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
        builder = LinuxBuilder()
        builder.run()
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()
