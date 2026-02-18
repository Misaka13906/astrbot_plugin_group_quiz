from astrbot.api.star import Context
from ..repository import QuizRepository

# 导入各个 Handler Mixins
from .query import QueryHandlers
from .user import UserHandlers
from .admin import AdminHandlers
from .strategy import StrategyHandlers

class CommandHandlers(
    QueryHandlers, 
    UserHandlers, 
    AdminHandlers, 
    StrategyHandlers
):
    """
    命令处理器聚合类
    继承所有分模块的 Handler Mixins
    """
    def __init__(self, context: Context, db: QuizRepository, config):
        """
        初始化命令处理器
        
        Args:
            context: AstrBot 上下文
            db: 数据库实例
            config: 插件配置
        """
        # 调用基类 BaseHandler 的初始化
        # MRO 保证这也将作为公共基类被正确初始化
        super().__init__(context, db, config)
