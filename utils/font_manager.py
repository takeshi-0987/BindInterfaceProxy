# utils/font_manager.py
import logging
from PySide6.QtGui import QFontDatabase, QFont

from defaults.ui_default import FONT_FILES

logger = logging.getLogger(__name__)



class FontManager:
    """字体管理器"""

    _instance = None

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = FontManager()
        return cls._instance

    def __init__(self):
        """初始化"""
        self.font_family = None
        self.loaded = False

    def load_fonts(self):
        """加载字体文件"""
        if self.loaded:
            return self.font_family is not None

        self.loaded = True
        loaded_count = 0

        for font_file in FONT_FILES:
            try:
                # 直接使用相对路径，与你的配置风格一致
                font_id = QFontDatabase.addApplicationFont(font_file)

                if font_id == -1:
                    logger.warning(f"字体加载失败: {font_file}")
                    continue

                families = QFontDatabase.applicationFontFamilies(font_id)
                if not families:
                    logger.warning(f"未获取到字体家族名: {font_file}")
                    continue

                font_family = families[0]
                loaded_count += 1

                # 使用第一个成功加载的字体作为主字体
                if self.font_family is None:
                    self.font_family = font_family

                logger.info(f"✅ 字体加载成功: {font_file}")

            except Exception as e:
                logger.error(f"加载字体 {font_file} 时出错: {e}")

        if loaded_count > 0:
            logger.info(f"字体加载完成，成功 {loaded_count}/{len(FONT_FILES)} 个")
            return True
        else:
            logger.error("❌ 所有字体文件加载失败，使用系统字体")
            return False

    def is_font_loaded(self):
        """
        检查字体是否已加载成功

        Returns:
            bool: 字体是否已加载
        """
        return self.loaded and self.font_family is not None

    def setup_application_font(self, application, point_size=9):
        """设置应用字体"""
        if not self.load_fonts() or not self.font_family:
            logger.warning("无法设置字体，使用系统默认字体")
            return False

        try:
            font = QFont(self.font_family, point_size)
            application.setFont(font)
            logger.info(f"✅ 应用字体已设置为: {self.font_family}")
            return True
        except Exception as e:
            logger.error(f"设置应用字体失败: {e}")
            return False

    def get_font(self, point_size=9, weight=QFont.Normal):
        """获取字体对象"""
        if self.font_family:
            return QFont(self.font_family, point_size, weight)
        return QFont("", point_size, weight)  # 空字符串使用系统默认字体
