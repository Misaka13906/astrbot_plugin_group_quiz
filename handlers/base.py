from astrbot.api.star import Context
from ..repository import QuizRepository

class BaseHandler:
    """基础命令处理器"""
    
    def __init__(self, context: Context, db: QuizRepository, config):
        """
        初始化命令处理器

        Args:
            context: AstrBot 上下文
            db: 数据库实例
            config: 插件配置
        """
        self.context = context
        self.db = db
        self.config = config
        self.scheduler = None
