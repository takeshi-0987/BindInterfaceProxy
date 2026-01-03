# BindInterfaceProxy - 绑定网络接口的代理工具

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52.svg)
![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20|%20Linux%20|%20macOS-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen.svg)

**多网卡场景下通过接口绑定的代理实现流量管理**

[项目简介](#-项目简介) | [两种使用方式](#-两种使用方式) | [快速开始](#-快速开始) | [配置说明](#️-配置说明) | [许可证](#-许可证)

</div>

## 📋 项目简介

BindInterfaceProxy 是一个网络工具，设计用于在多网卡环境下管理网络流量，通过绑定指定网络接口作为流量出口，利用代理服务形式，实现流量分流；单网卡情况下也可以用作普通代理服务器使用。

### 主要特点
- 🚀 **完整GUI**：可视化操作，简化复杂网络配置
- 🛠️ **功能全面**：支持HTTP、HTTPS、SOCKS5主流代理服务协议，支持代理服务认证、PP头解析、远程DNS解析、IP地理位置解析、黑白名单管理、快速连接检测等各项代理服务功能
- 📊 **直观监控**：实时连接和代理流量统计，掌握分流情况
- ⚙️ **高度可配置**：灵活的规则和设置，多级别日志管理

## 🎯 两种使用方式

本项目提供两种使用方式，满足不同用户需求：

### 方式一：Python脚本运行（适合开发者/技术用户）
- **优点**：便于调试、修改源码、查看控制台输出
- **缺点**：需要安装Python环境
- **适用**：开发测试、自定义修改、问题排查

### 方式二：打包Release版本（适合普通用户）
- **优点**：开箱即用，无需安装Python
- **缺点**：体积稍大，无法修改源码
- **适用**：日常使用、部署分发、非技术用户

## 🚀 快速开始

### 方式一：使用Python脚本运行

#### 1. 系统要求
- **Python版本**：3.10 或更高版本
- **操作系统**：Windows 10/11, Linux, macOS

#### 2. 安装步骤
```bash
# 1. 下载项目
git clone https://github.com/takeshi-0987/BindInterfaceProxy.git
cd BindInterfaceProxy

# 2. 安装依赖包
# 必选
pip install pyside6==6.10.1
pip install psutil==7.2.0
pip install requests==2.32.5
pip install dnspython==2.8.0

# 可选
pip install colorlog==6.10.1
pip install maxminddb==3.0.0
pip install IP2Location==8.11.0

# 或使用requirements.txt（如果有）
pip install -r requirements.txt

# 3. 运行程序
# 方式A：带控制台运行（推荐开发调试）
# 可以看到实时日志输出，便于问题排查
python main.py

# 方式B：无控制台运行（GUI专用）
# 只显示图形界面，适合日常使用
pythonw main.py  # Windows
# 或使用后台运行
nohup python main.py &  # Linux/macOS
```

### 方式二：使用打包好的Release版本
#### 1. 下载最新版本
前往 Releases页面 下载对应系统的版本：

| 系统    | 文件名                                | 说明                             |
|---------|---------------------------------------|----------------------------------|
| Windows | `BindInterfaceProxy_Windows_x64.zip`  | 解压后双击 `.exe` 直接运行             |
| Linux   | `BindInterfaceProxy_Linux_x64.tar.gz` | 解压后运行可执行文件             |
| macOS   | `BindInterfaceProxy_macOS_x64.app`    | 拖拽到应用程序文件夹              |

#### 2. Windows用户快速开始
##### 下载 BindInterfaceProxy_Windows_x64.zip
##### 解压到任意文件夹
##### 双击运行 BindInterfaceProxy.exe


#### 3. Linux用户快速开始
##### 确认系统托盘功能
本程序基于 PySide6（Qt6） 开发，使用 QSystemTrayIcon 实现系统托盘功能。在 Linux 上，托盘图标的显示依赖于 **桌面环境** 和 **系统库**。

###### 🔸 第一步：确认是否安装了托盘支持库
PySide6 的 QSystemTrayIcon 在 Linux 上依赖 libappindicator 或 Ayatana Indicators。

✅ 推荐安装（Ubuntu/Debian 及衍生版）：

```bash
# 新版系统（Ubuntu 22.04+、Debian 12+）
sudo apt install libayatana-appindicator3-1

# 旧版系统（Ubuntu 20.04 及更早）
sudo apt install libappindicator3-1
```

###### 🔸 第二步：检查桌面环境
| 桌面环境	|是否原生支持 Qt 托盘	|额外操作|
|-----------|---------------------|--------|
|KDE Plasma	|✅ 完美支持	|无需操作|
|XFCE / MATE / Cinnamon	|✅ 支持	|确保面板启用了“通知区域”插件
|GNOME（Ubuntu 默认）	|❌ 默认不显示	|必须安装扩展

###### Ubuntu / GNOME 用户必看：
GNOME 桌面移除了传统系统托盘，必须安装扩展：

```bash
sudo apt install gnome-shell-extension-appindicator
```

##### 下载、解压并运行
```bash
# 下载并解压（注意：路径中不能有中文）
wget https://github.com/takeshi-0987/BindInterfaceProxy/releases/latest/download/BindInterfaceProxy_Linux_x64.tar.gz
tar -xzf BindInterfaceProxy_Linux_x64.tar.gz
cd BindInterfaceProxy_Linux_x64

# 添加执行权限
chmod +x bindinterfaceproxy

# 运行程序
# 带控制台
./bindinterfaceproxy
# 或者
./run.sh

# 脱离控制台
nohup ./bindinterfaceproxy > /dev/null 2>&1 &
# 或者桌面端手动运行
```

#### 4. macOS用户快速开始
##### 下载 BindInterfaceProxy_macOS_x64.app 文件
##### 双击直接运行或将 BindInterfaceProxy_macOS_x64.app 拖拽到 “应用程序”文件夹完成安装。


#### 5. 自主编译建议
如果没有你所需的版本，可以自主进行编译：

```bash
# 安装运行所需的所有依赖（见上文）
# 或使用requirements.txt（如果有）
pip install -r requirements.txt

#安装编译依赖
pip install nuitka==2.8.9  # 打包工具

# 如有压缩需求，可安装upx压缩工具（可选），并加入环境变量

# 根据编译平台运行对应脚本
# windows
python build_windows.py

# linux
python build_linux.py

# macos
python build_macos.py
```

###### Windows 用户必看：
* windows 编译需安装Visual Studio Build Tools，并在工作负荷中安装 “C++ 生成工具” 或 “使用C++ 的桌面开发”。
* 如果自定义了生成工具安装位置，则需要在build_windows.py文件中_find_vs_build_tools方法的possible_paths列表中添加MSVC的激活脚本位置。
* 如不添加激活脚本位置，则需要手动运行vcvars64.bat脚本激活MSVC环境，并在同一个控制台中运行python build_windows.py。

###### Linux 用户必看：
* 由于Nuitka与linux的兼容性问题，Nuitka 编译的执行程序路径不能包含中文。

###### Macos 用户必看：
* 如编译程序无法启动，可能是遇到了 Nuitka 编译程序在 macOS 上发生段错误（Segmentation Fault），初步排查可能不同版本pyside6、python在编译后和macos存在不兼容问题，建议选择稳定版本进行尝试，我最终成功编译的版本是python(3.12)和pyside6(6.8.0.1)，python脚本执行暂未发现问题。


## ⚙️ 配置说明
### 一、首次运行配置
首次运行会要求配置出口网络，以及SOSKS5代理或HTTP代理

#### 出口网络设置：
* 在“设置”页面中，点击“出口网络配置”，在“网络接口”下拉菜单中选择需要绑定的网卡用于代理流量的出口，程序会自动匹配当前ip，并且在每次启动时都会根据网卡重新匹配当前ip，特别适合DHCP配置动态ip的场合。

* 如果列表中没有网卡，或需要固定ip时，点击“列表中没有，我自己配置ip”，则可手动输入ip地址（仅支持ipv4），此时程序将根据ip来绑定流量出口。

* 端口根据需要可配置固定端口或系统随机端口。

#### SOSKS5代理或HTTP代理（至少配置一个）：
* 在“设置”页面中，点击“SOSKS5代理”或“HTTP/HTTPS代理”表签页，点击“新建”按钮，打开“配置代理”对话框，进行每个代理的配置。
* “**名称**”用于在日志或其它页面中区分不同代理。
* “**网络接口**”和逻辑和出口网络设置相同。
* “**启用用户认证**”会在连接代理时要求提供用户名和密码。
* “**启用安全管理**”会根据“安全管理”设置页的情况开启认证失败次数，快速连接次数的检测，超过阈值会自动加入临时封禁名单。
* “**启用proxy_protocal**”和“**协议版本**”可以在使用frp进行内网连接的场景下，获取原始连接的ip地址，使用此功能，frpc的配置文件中需要添加proxy_protocol_version = v2（根据你选择的版本号）。
* “**启动HTTPS**”会开启HTTPS代理，但需要提供SSL/TSLE的证书文件和私钥文件。

#### 用户管理
* 如有任何一个代理启用了用户认证，则在没有用户的情况下弹出对话框要求配置至少一个用户，否则将无法运行程序。
* 始需添加更多用户，可以“托盘图标”处点击右键，选择“用户管理”进行配置，或在“设置”页面中点击“打开用户管理”按钮。


### 二、DNS解析
* 程序默认使用系统的DNS解析，如果需要通过绑定网卡使用远端DNS解析，需在“DNS解析”设置页面中点击启用远端DNS解析。
* 远端DNS解析支持“串行”和“并行”两种模式，“串行”为根据解析服务器列表由上至下依次尝试解析，在当前服务器解析失败或超时时才会使用下一个服务器解析；“并行”模式下，则会同时尝试多个解析服务器，并使用最快返回的解析结果。
* 远端DNS解析支持缓存，对于频繁连接的网址可以进一步提升解析速度。
* 远端DNS解析支持黑名单，用于阻断域名解析，黑名单域名将不会被访问。

### 三、IP地理位置
* 程序支持在线查询，可以在窗口日志中在ip地址点击右键，在“在线查询”处进行搜索，程序会带调用系统浏览器打开页面，查看ip地址信息。
* 如需实时查看，可以配置本地数据库，目前支持两种类型的数据库：GeoLite2（.mmdb）和IP2Location(.bin)，本程序不提供任何数据库，用户可自行下载，并在“IP地理位置”设置页面中进行配置，如开启本地数据库，则在窗口日志和其他页面中自动显示连接ip的地理信息。

### 四、其他设置
* 安全管理设置，用于配置认证失败次数、快速访问次数、畸形扫描类型等，可根据需要配置。
* 网络健康度检查，通过尝试访问指定网址来验证网络连通性，可自动检查，也可手动检查。
* 日志设置，提供三种查看方式：控制台查看（需启用控制台）；日志窗口（单击托盘图标或右键图标选择窗口日志）；文件日志（默认在程序目录中的logs文件夹中），最大文件大小为单个文的最大占用空间，超过则启用新的文件；备份数量为现有文件的个数，超过则删除最早的单个文件。
* 用户文件夹，默认所有用户数据均存放在程序目录中的data文件夹下，可备份或替换，部分路径可通过设置页面修改。

## 📄 许可证
本项目采用 GNU General Public License v3.0 (GPL v3) 许可证。

#### 许可证摘要
✅ 自由使用：可以免费使用、修改本软件

✅ 开源义务：分发修改版本时必须开源

✅ 版权保护：保留原始版权声明

完整许可证
完整许可证文本请查看 LICENSE 文件，或访问：
https://www.gnu.org/licenses/gpl-3.0.html
https://choosealicense.com/licenses/gpl-3.0/

#### 第三方库许可证
* PySide6: LGPL v3
* psutil: BSD 3-Clause
* requests: Apache 2.0
* dnspython: ISC License
* maxminddb: Apache 2.0
* IP2Location: MIT License
* *colorlog: MIT License
* Nuitka: Apache License 2.0
详细内容请查看 THIRD-PARTY-NOTICES.txt 文件，或访问可项目网站查看

#### 资源许可证
* 字体：Maple Mono，
许可证：SIL Open Font License v1.1 (OFL-1.1)，详见resouces/fonts文件夹

* 启动图标："矿机特写照片"
许可证：Pexels License (https://www.pexels.com/zh-cn/license/)


<div align="center">
  <strong><span style="font-size: 20px;">感谢使用 BindInterfaceProxy！</span></strong><br>
  <span style="font-size: 18px;">如果这个项目对你有帮助，欢迎给个 ⭐ Star ⭐ 支持！</span>
</div>
