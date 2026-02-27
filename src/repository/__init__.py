from .answer import AnswerMixin
from .baseinfo import BaseInfoMixin
from .core import DatabaseCore
from .problem import ProblemMixin
from .task import TaskMixin


class QuizRepository(DatabaseCore, BaseInfoMixin, ProblemMixin, TaskMixin, AnswerMixin):
    """
    群聊答题插件数据仓库类
    聚合了所有功能模块：
    - Core: 连接管理
    - BaseInfo: 基础信息（群组、领域、用户）
    - Problem: 题目查询
    - Task: 任务配置、游标、策略
    - Answer: 答题记录与分数计算
    """

    def __init__(self, db_path: str):
        super().__init__(db_path)
