from abc import ABC, abstractmethod
from typing import List

from ..repository import QuizRepository

class PushStrategy(ABC):
    """推送策略抽象基类"""
    
    def __init__(self, db: QuizRepository):
        self.db = db
    
    @abstractmethod
    def get_problems_to_push(
        self, group_qq: str, domain_id: int, limit: int = 3
    ) -> List[dict]:
        """
        获取待推送的题目列表
        
        Args:
            group_qq: 群号
            domain_id: 领域ID
            limit: 限制数量
            
        Returns:
            List[dict]: 题目列表
        """
        pass
    
    @abstractmethod
    def on_push_success(
        self, group_qq: str, domain_id: int, problem_ids: List[int]
    ) -> None:
        """
        推送成功后的回调
        
        Args:
            group_qq: 群号
            domain_id: 领域ID
            problem_ids: 推送的题目ID列表
        """
        pass
    
    @abstractmethod
    def get_strategy_info(self, group_qq: str, domain_id: int) -> str:
        """
        获取策略状态信息（用于 /stra info）
        
        Args:
            group_qq: 群号
            domain_id: 领域ID
            
        Returns:
            str: 格式化的状态信息
        """
        pass
