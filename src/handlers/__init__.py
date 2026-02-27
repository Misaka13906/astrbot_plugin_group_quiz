from astrbot.api.star import Context

from ..repository import QuizRepository
from .admin import AdminHandlers
from .answer import AnswerHandlers
from .problem import ProblemHandlers

# 导入各个 Handler Mixins
from .query import QueryHandlers
from .strategy import StrategyHandlers
from .user import UserHandlers


class CommandHandlers(
    QueryHandlers,
    UserHandlers,
    AdminHandlers,
    StrategyHandlers,
    AnswerHandlers,
    ProblemHandlers,
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
        self.context = context
        self.db = db
        self.config = config
        self.scheduler = None
