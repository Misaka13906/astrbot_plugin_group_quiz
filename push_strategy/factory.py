from astrbot.api import logger
from ..repository import QuizRepository
from .base import PushStrategy
from .counter import CounterStrategy
from .batch import BatchStrategy
from .daterem import DateRemainderStrategy

class StrategyFactory:
    """策略工厂类"""
    
    _strategies = {
        'counter': CounterStrategy,
        'batch': BatchStrategy,
        'daterem': DateRemainderStrategy
    }
    
    @classmethod
    def create(cls, strategy_type: str, db: QuizRepository) -> PushStrategy:
        """
        创建策略实例
        
        Args:
            strategy_type: 策略类型 (counter/batch/daterem)
            db: 数据库实例
            
        Returns:
            PushStrategy: 策略实例
        """
        if strategy_type not in cls._strategies:
            logger.warning(f"Unknown strategy: {strategy_type}, fallback to batch")
            strategy_type = 'batch'
            
        return cls._strategies[strategy_type](db)
    
    @classmethod
    def get_group_strategy(cls, db: QuizRepository, group_qq: str, domain_id: int) -> PushStrategy:
        """
        获取群-领域对应的策略实例
        
        Args:
            db: 数据库实例
            group_qq: 群号
            domain_id: 领域ID
            
        Returns:
            PushStrategy: 策略实例
        """
        strategy_type = db.get_strategy_type(group_qq, domain_id)
        return cls.create(strategy_type, db)
