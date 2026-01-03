# -*- coding: utf-8 -*-
"""
Module: app_info.py
Author: Takeshi
Date: 2025-12-26

Description:
    应用信息
"""


class AppInfo:
    """应用信息类"""

    # 基本信息
    NAME = "BindInterfaceProxy"
    DESCRIPTION = "绑定网络接口的代理工具"
    VERSION = "1.0.0"
    AUTHOR = "Takeshi"
    COPYRIGHT = f"Copyright © 2026 Takeshi. GPL v3 License"

    # 仓库信息
    REPOSITORY = "https://github.com/takeshi-0987/BindInterfaceProxy"
    LICENSE_URL = f"{REPOSITORY}/blob/main/LICENSE"

    # 资源信息
    class Resources:
        """资源文件信息"""
        # 字体
        FONT_NAME = "Maple Mono"
        FONT_AUTHOR = "subframe7536"
        FONT_URL = "https://github.com/subframe7536/maple-font/tree/variable"
        FONT_FILE = "MapleMonoNormalNL-NFMono-CN-Regular.ttf"

        # 启动图片
        STARTUP_IMAGE_NAME = "矿机特写照片"
        STARTUP_IMAGE_AUTHOR = "panumas nikhomkhai"
        STARTUP_IMAGE_URL = "https://www.pexels.com/zh-cn/photo/1148820/"

    # 依赖信息（用于打包和检查）
    class Dependencies:
        """依赖包信息"""
        REQUIRED = {
            'pyside6': '6.10.1',
            'psutil': '7.2.0',
            'requests': '2.32.5',
            'dnspython': '2.8.0',
        }

        OPTIONAL = {
            'maxminddb': '3.0.0',
            'IP2Location': '8.11.0',
            'colorlog': '6.10.1',
        }

        DEV = {
            'nuitka': '2.8.9',
        }

    @classmethod
    def get_about_info(cls):
        """获取关于页面的信息"""
        return {
            'name': cls.NAME,
            'description': cls.DESCRIPTION,
            'version': cls.VERSION,
            'author': cls.AUTHOR,
            'copyright': cls.COPYRIGHT,
            'license': 'GNU GPL v3',
            'repository': cls.REPOSITORY,
            'license_url': cls.LICENSE_URL,
        }

    @classmethod
    def get_windows_version_info(cls):
        """获取Windows版本信息"""
        return cls.Windows.get_all_info()

    @classmethod
    def get_resources_info(cls):
        """获取资源致谢信息"""
        return {
            'font': {
                'name': cls.Resources.FONT_NAME,
                'author': cls.Resources.FONT_AUTHOR,
                'url': cls.Resources.FONT_URL,
            },
            'startup_image': {
                'name': cls.Resources.STARTUP_IMAGE_NAME,
                'author': cls.Resources.STARTUP_IMAGE_AUTHOR,
                'url': cls.Resources.STARTUP_IMAGE_URL,
            }
        }

    @classmethod
    def get_dependencies_info(cls):
        """获取依赖信息"""
        return {
            'required': cls.Dependencies.REQUIRED,
            'optional': cls.Dependencies.OPTIONAL,
            'dev': cls.Dependencies.DEV,
        }

    @classmethod
    def _get_license_for_lib(cls, lib_name):
        """获取库的许可证类型"""
        licenses = {
            'pyside6': 'LGPL v3 / 商业许可证',
            'psutil': 'BSD 3-Clause',
            'requests': 'Apache 2.0',
            'dnspython': 'ISC License',
            'maxminddb': 'Apache 2.0',
            'IP2Location': 'MIT License',
            'colorlog': 'MIT License',
            'nuitka': 'Apache 2.0',
        }
        return licenses.get(lib_name, '未知许可证')

    @classmethod
    def _get_link_for_lib(cls, lib_name):
        """获取库的项目链接"""
        links = {
            'pyside6': 'https://wiki.qt.io/Qt_for_Python',
            'psutil': 'https://github.com/giampaolo/psutil',
            'requests': 'https://github.com/psf/requests',
            'dnspython': 'https://github.com/rthalley/dnspython',
            'maxminddb': 'https://github.com/maxmind/MaxMind-DB-Reader-python',
            'IP2Location': 'https://pypi.org/project/IP2Location/',
            'colorlog': 'https://github.com/borntyping/python-colorlog',
            'nuitka': 'https://nuitka.net/'
        }
        return links.get(lib_name, '#')


    # Windows特定版本信息（用于嵌入到.exe文件中）
    class Windows:
        """Windows可执行文件版本信息"""

        @classmethod
        def get_product_name(cls):
            """获取产品名称"""
            return AppInfo.NAME

        @classmethod
        def get_product_version(cls):
            """获取产品版本"""
            return AppInfo.VERSION

        @classmethod
        def get_file_description(cls):
            """获取文件描述"""
            return AppInfo.DESCRIPTION

        @classmethod
        def get_file_version(cls):
            """获取文件版本（Windows格式：主版本.次版本.修订号.构建号）"""
            return f"{AppInfo.VERSION}.0"  # 例如 "1.0.0.0"

        @classmethod
        def get_company_name(cls):
            """获取公司名称"""
            return "个人项目"

        @classmethod
        def get_legal_copyright(cls):
            """获取版权信息"""
            return f"Copyright © 2025 {AppInfo.AUTHOR}. 基于GPL v3许可"

        @classmethod
        def get_internal_name(cls):
            """获取内部名称"""
            return AppInfo.NAME

        @classmethod
        def get_original_filename(cls):
            """获取原始文件名"""
            return f"{AppInfo.NAME}.exe"

        @classmethod
        def get_legal_trademarks(cls):
            """获取商标信息"""
            return "GPL v3 License"

        @classmethod
        def get_comments(cls):
            """获取注释"""
            return f"Version {AppInfo.VERSION} - {AppInfo.AUTHOR}"

        @classmethod
        def get_all_info(cls):
            """获取所有Windows版本信息"""
            return {
                'product_name': cls.get_product_name(),
                'product_version': cls.get_product_version(),
                'file_description': cls.get_file_description(),
                'file_version': cls.get_file_version(),
                'company_name': cls.get_company_name(),
                'legal_copyright': cls.get_legal_copyright(),
                'internal_name': cls.get_internal_name(),
                'original_filename': cls.get_original_filename(),
                'legal_trademarks': cls.get_legal_trademarks(),
                'comments': cls.get_comments(),
            }
