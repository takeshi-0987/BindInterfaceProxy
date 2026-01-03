# -*- coding: utf-8 -*-
"""
Module: about_tab.py
Author: Takeshi
Date: 2025-12-25
Description: 关于标签页，显示项目信息和声明
此程序是自由软件：您可以根据自由软件基金会发布的 GNU 通用公共许可证条款重新发布和/或修改它；
可以是该许可证的第3版，也可以是（在您的选择下）任何更新的版本。

本程序是基于希望它有用而发布的，但没有任何保证；甚至没有对适销性或特定用途适用性的暗示保证。
有关更多详细信息，请参阅 GNU 通用公共许可证。

您应该已经收到一份 GNU 通用公共许可证的副本以及此程序。
如果没有，请参阅 <http://www.gnu.org/licenses/>。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QGroupBox, QFrame
)
from PySide6.QtCore import Qt
from defaults.app_info import AppInfo

class AboutTab(QWidget):
    """关于标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_info = AppInfo()
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        # 主内容部件
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)

        # 项目信息
        project_group = QGroupBox("项目信息")
        project_layout = QVBoxLayout(project_group)

        about_info = self.app_info.get_about_info()
        project_info = [
            ("项目名:", about_info['name']),
            ("项目描述:", about_info['description']),
            ("版本:", about_info['version']),
            ("作者:", about_info['author']),
            ("源码仓库:", f'<a href="{about_info['repository']}">{about_info['repository']}</a>'),
            ("许可证:", about_info['license']),
        ]

        for label, value in project_info:
            row_layout = QHBoxLayout()
            label_widget = QLabel(f"<b>{label}</b>")
            label_widget.setFixedWidth(80)
            value_widget = QLabel(value)
            value_widget.setOpenExternalLinks(True)
            row_layout.addWidget(label_widget)
            row_layout.addWidget(value_widget)
            row_layout.addStretch()
            project_layout.addLayout(row_layout)

        bottom_info_layout = QHBoxLayout()

        # 感谢信息
        thanks_label = QLabel("感谢使用BindInterfaceProxy, \n如果这个项目对你有帮助，欢迎来源码仓库给个 ⭐ 支持！")
        thanks_label.setStyleSheet("color: #ff6600; font-weight: bold;")
        thanks_label.setWordWrap(True)

        # 版权信息
        copyright_label = QLabel(f"<i>{about_info['copyright']}</i>")
        copyright_label.setStyleSheet("color: #666;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # 添加到底部布局
        bottom_info_layout.addWidget(thanks_label, 1)
        bottom_info_layout.addWidget(copyright_label)

        project_layout.addLayout(bottom_info_layout)

        content_layout.addWidget(project_group)

        # 许可证信息
        license_group = QGroupBox("GNU 通用公共许可证 v3")
        license_layout = QVBoxLayout(license_group)

        license_html = f"""
<b>GNU GENERAL PUBLIC LICENSE</b><br>
<b>Version 3, 29 June 2007</b><br>
<br>
Copyright (C) 2007 Free Software Foundation, Inc. &lt;https://fsf.org/&gt;<br>
<br>
Everyone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed.<br>
<br>
<hr>
<br>
<b>核心条款摘要：</b><br>
<br>
1. <b>自由运行：</b>您可以出于任何目的运行此程序。<br>
2. <b>自由学习与修改：</b>您可以研究程序如何工作，并根据自己的需要修改它。<br>
3. <b>自由分发：</b>您可以分发原始副本。<br>
4. <b>自由分发修改版：</b>您可以分发修改后的版本，但必须遵循以下要求：<br>
   &nbsp;&nbsp;• 保持相同的许可证（GPL v3）<br>
   &nbsp;&nbsp;• 提供完整的源代码<br>
   &nbsp;&nbsp;• 明确说明所做的修改<br>
   &nbsp;&nbsp;• 保留原始版权声明<br>
<br>
<hr>
<br>
<b>完整许可证：</b><br>
完整的 GNU GPL v3 许可证文本可在以下位置找到：<br>
<a href="https://www.gnu.org/licenses/gpl-3.0.html">https://www.gnu.org/licenses/gpl-3.0.html</a><br>
<br>
您也应该收到一份许可证副本以及此程序。如果没有，请查阅：<br>
<a href="http://www.gnu.org/licenses/">http://www.gnu.org/licenses/</a><br>
<br>
项目许可证文件：<br>
<a href="{about_info['license_url']}">{about_info['license_url']}</a>
        """

        license_label = QLabel()
        license_label.setTextFormat(Qt.TextFormat.RichText)
        license_label.setText(license_html)
        license_label.setWordWrap(True)
        license_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        license_label.setOpenExternalLinks(True)
        license_label.setStyleSheet("""
            QLabel {
                padding: 12px;
                line-height: 1.6;
                background-color: #f8f9fa;
                border-radius: 6px;
                border: 1px solid #e9ecef;
            }
            QLabel a {
                color: #0066cc;
                text-decoration: none;
            }
            QLabel a:hover {
                color: #004080;
                text-decoration: underline;
            }
        """)

        license_layout.addWidget(license_label)
        content_layout.addWidget(license_group)

        # 第三方组件许可证
        thirdparty_group = QGroupBox("第三方组件许可证")
        thirdparty_layout = QVBoxLayout(thirdparty_group)

        # 获取依赖信息
        deps_info = self.app_info.get_dependencies_info()

        thirdparty_html = """
<b>第三方库许可信息：</b><br>
<br>
<table style="width:100%; border-collapse: collapse;">
<tr style="background-color: #f2f2f2;">
    <th style="padding: 8px; text-align: left;">组件</th>
    <th style="padding: 8px; text-align: left;">版本</th>
    <th style="padding: 8px; text-align: left;">许可证</th>
    <th style="padding: 8px; text-align: left;">链接</th>
</tr>"""

        # 必选依赖
        thirdparty_html += """
<tr style="background-color: #f8f9fa;">
    <td colspan="4" style="padding: 8px; font-weight: bold;">核心依赖</td>
</tr>"""

        for lib, version in deps_info['required'].items():
            license_type = self.app_info._get_license_for_lib(lib)
            link = self.app_info._get_link_for_lib(lib)
            thirdparty_html += f"""
<tr>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lib}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{version}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{license_type}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><a href="{link}">{link}</a></td>
</tr>"""

        # 可选依赖
        if deps_info['optional']:
            thirdparty_html += """
<tr style="background-color: #f8f9fa;">
    <td colspan="4" style="padding: 8px; font-weight: bold;">可选依赖</td>
</tr>"""

            for lib, version in deps_info['optional'].items():
                license_type = self.app_info._get_license_for_lib(lib)
                link = self.app_info._get_link_for_lib(lib)
                thirdparty_html += f"""
<tr>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lib}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{version}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{license_type}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><a href="{link}">{link}</a></td>
</tr>"""

        # 构建依赖
        if deps_info['dev']:
            thirdparty_html += """
<tr style="background-color: #f8f9fa;">
    <td colspan="4" style="padding: 8px; font-weight: bold;">构建依赖</td>
</tr>"""

            for lib, version in deps_info['dev'].items():
                license_type = self.app_info._get_license_for_lib(lib)
                link = self.app_info._get_link_for_lib(lib)
                thirdparty_html += f"""
<tr>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lib}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{version}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{license_type}</td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><a href="{link}">{link}</a></td>
</tr>"""

        thirdparty_html += """
</table>
<br>
<b>注意：</b>这些第三方库在各自的许可证下分发。详细信息请参阅各项目的官方文档。
        """

        thirdparty_label = QLabel()
        thirdparty_label.setTextFormat(Qt.TextFormat.RichText)
        thirdparty_label.setText(thirdparty_html)
        thirdparty_label.setWordWrap(True)
        thirdparty_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        thirdparty_label.setOpenExternalLinks(True)
        thirdparty_label.setStyleSheet("""
            QLabel {
                padding: 12px;
                line-height: 1.6;
            }
            QLabel a {
                color: #0066cc;
                text-decoration: none;
            }
            QLabel a:hover {
                color: #004080;
                text-decoration: underline;
            }
        """)

        thirdparty_layout.addWidget(thirdparty_label)
        content_layout.addWidget(thirdparty_group)

        # 资源致谢
        thanks_group = QGroupBox("资源致谢")
        thanks_layout = QVBoxLayout(thanks_group)

        # 获取资源信息
        resources_info = self.app_info.get_resources_info()

        # 启动图片
        image_section = QVBoxLayout()
        image_label = QLabel("<b>启动图片：</b>")
        image_info = QLabel(resources_info['startup_image']['name'])
        author_label = QLabel(f"<span style='color: #666;'>作者：{resources_info['startup_image']['author']}</span>")
        link_label = QLabel(f'<a href="{resources_info["startup_image"]["url"]}">{resources_info["startup_image"]["url"]}</a>')
        link_label.setOpenExternalLinks(True)

        image_section.addWidget(image_label)
        image_section.addWidget(image_info)
        image_section.addWidget(author_label)
        image_section.addWidget(link_label)
        thanks_layout.addLayout(image_section)

        # 分隔线
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setFrameShadow(QFrame.Sunken)
        thanks_layout.addWidget(separator1)

        # 字体
        font_section = QVBoxLayout()
        font_label = QLabel("<b>字体：</b>")
        font_info = QLabel(resources_info['font']['name'])
        font_author_label = QLabel(f"<span style='color: #666;'>作者：{resources_info['font']['author']}</span>")
        font_link_label = QLabel(f'<a href="{resources_info["font"]["url"]}">{resources_info["font"]["url"]}</a>')
        font_link_label.setOpenExternalLinks(True)

        font_section.addWidget(font_label)
        font_section.addWidget(font_info)
        font_section.addWidget(font_author_label)
        font_section.addWidget(font_link_label)
        thanks_layout.addLayout(font_section)

        content_layout.addWidget(thanks_group)

        # 免责声明
        disclaimer_group = QGroupBox("重要声明")
        disclaimer_layout = QVBoxLayout(disclaimer_group)

        disclaimer_html = f"""
<b>开源精神声明：</b><br>
本项目采用GPL v3许可证发布，体现了以下自由软件理念：<br>
• 自由使用软件的自由<br>
• 学习软件工作原理的自由<br>
• 修改软件以满足自己需求的自由<br>
• 分发软件副本的自由<br>
• 分发修改版本的自由的自由<br>
<br>
<b>项目信息：</b><br>
• 项目名称：{about_info['name']}<br>
• 版本：{about_info['version']}<br>
• 源码仓库：<a href="{about_info['repository']}">{about_info['repository']}</a><br>
<br>
<b>项目用途说明：</b><br>
本项目是一个网络工具，用于在多网卡环境下通过绑定指定网络接口实现流量分流。<br>
旨在促进技术学习、网络研究和合法的网络管理。<br>
<br>
<b>合法使用要求：</b><br>
• 遵守用户所在地的所有法律法规<br>
• 仅用于授权的网络测试和管理<br>
• 尊重他人的网络权利和隐私<br>
• 不进行任何非法入侵或攻击<br>
<br>
<b>责任声明：</b><br>
• 本程序按"原样"提供，不提供任何明示或暗示的保证<br>
• 使用者应对自己的行为承担全部法律责任<br>
• 开发者不对使用者的任何行为负责<br>
<br>
<b>GPL义务提醒：</b><br>
如果您分发本程序的修改版本，必须：<br>
1. 保持GPL v3许可证<br>
2. 提供完整的源代码<br>
3. 明确标注您所做的修改<br>
4. 保留原始版权声明
        """

        disclaimer_label = QLabel()
        disclaimer_label.setTextFormat(Qt.TextFormat.RichText)
        disclaimer_label.setText(disclaimer_html)
        disclaimer_label.setWordWrap(True)
        disclaimer_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        disclaimer_label.setOpenExternalLinks(True)
        disclaimer_label.setStyleSheet("""
            QLabel {
                padding: 12px;
                line-height: 1.6;
                background-color: #fff9e6;
                border-radius: 6px;
                border: 1px solid #ffe680;
            }
            QLabel a {
                color: #0066cc;
                text-decoration: none;
            }
            QLabel a:hover {
                color: #004080;
                text-decoration: underline;
            }
        """)

        disclaimer_layout.addWidget(disclaimer_label)
        content_layout.addWidget(disclaimer_group)

        # 添加拉伸
        content_layout.addStretch()

        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def validate_config(self):
        """验证配置（关于页不需要验证）"""
        return True, ""
