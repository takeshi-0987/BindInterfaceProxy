
# 启动窗口随机图片文件夹
STARTUP_BG_LIST = [
                "resources/startup_bg/",
            ]
# 启动窗口随机图片格式, 尺寸900x500px
STARTUP_BG_FORMAT = ['.jpg', '.jpeg', '.png', '.bmp',]

# 字体文件：
FONT_FILES = [
    'resources/fonts/MapleMonoNormalNL-NFMono-CN-Regular.ttf',
    'resources/fonts/MapleMonoNormalNL-NFMono-CN-Bold.ttf',
]

# 对话框图标
DIALOG_ICOINS = [
    "resources/icons/app_16x16.png",
    "resources/icons/app_32x32.png",
    "resources/icons/app_48x48.png"
]

# 托盘图标
TRAY_ICON_MAPPING = {
    'all_stopped': 'resources/icons/tray_gray.png',      # 所有代理停止
    'healthy': 'resources/icons/tray_blue.png',          # 网络正常且有运行代理
    'unhealthy': 'resources/icons/tray_red.png',         # 网络异常但有运行代理
    'checking': 'resources/icons/tray_yellow.png',       # 检测中
    'unknown': 'resources/icons/tray_blue.png',          # 未知状态（默认）
}


# 托盘图标菜单刷新间隔（毫秒）
MENU_REFRESH_INTERVAL = 60000  # 1分钟

# 日志窗口尺寸
LOG_WINDOW_SIZE = 850, 600

# 设置窗口最小尺寸
SETTINGS_DIALOG_MIN_SIZE = 850, 600


# 安全管理对话框尺寸
SECURITY_MANAGER_WINDOW_SIZE = 800, 600
# 安全管理对话框的刷新时间（毫秒）
SECURITY_MANAGER_WINDOW_REFRESH_INTERVAL = 5000

# 安全管理ip详情页尺寸
SECURITY_IP_DETAIL_DIALOG_SIZE = 400, 600

# 安全管理临时封禁历史页尺寸
SECURITY_BAN_HISTORY_DIALOG_SIZE = 1100, 500

# 连接和流量统计窗口尺寸
STATS_DIALOG_SIZE = 1200, 700
# 连接和流量统计刷新频率（毫秒）
STATS_REFRESH_INTERVAL = 1000

# 用户管理窗口尺寸
USER_MANAGER_WINDOW_SIZE = 600, 400

# 启动错误对话框尺寸
ERROR_DIALOG_SIZE = 800, 600


#健康检查对话框尺寸
HEALTHCHECK_DIALOG_SIZE = 500, 400
#健康检查对话框刷新频率（毫秒）
HEALTHCHECK_REFRESH_INTERVAL = 30000
# 健康检查示例服务器
HEALTHCHECK_SERVICES = [
    'https://www.baidu.com/',
    'https://www.sohu.com/',
    'https://www.qq.com/'
]
