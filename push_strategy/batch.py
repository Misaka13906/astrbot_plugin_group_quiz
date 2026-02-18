from typing import List
from astrbot.api import logger
from .base import PushStrategy

class BatchStrategy(PushStrategy):
    """
    批次推送策略 (兼容 v1.0.x)
    按预设批次顺序循环推送
    """
    
    def get_problems_to_push(
        self, group_qq: str, domain_id: int, limit: int = 3
    ) -> List[dict]:
        # 1. 获取当前 cursor
        current_cursor = self.db.get_cursor(group_qq, domain_id)
        
        # 2. 查找当前批次
        batch = self.db.get_batch_by_start_index(domain_id, current_cursor)
        
        if not batch:
            # 尝试回退到第一批
            batch = self.db.get_first_batch(domain_id)
            if not batch:
                # 该领域完全没有配置批次 -> Fallback 简单模式
                logger.warning(
                    f"No batch config found for domain {domain_id}, fallback to simple limit={limit}"
                )
                # 使用 legacy 的 get_problems_for_push (简单 limit 查询)
                # 注意：这里我们直接用 get_problems_for_push，它内部会由 cursor 决定吗？
                # 不，get_problems_for_push 是简单查询。
                return self.db.get_problems_for_push(domain_id, limit=limit)
        
        # 3. 获取批次内的题目
        problems = self.db.get_problems_in_range(
            domain_id, batch['start_index'], batch['end_index']
        )
        
        return problems

    def on_push_success(
        self, group_qq: str, domain_id: int, problem_ids: List[int]
    ) -> None:
        # 计算并更新下一个 cursor
        
        # 1. 获取当前 cursor
        # 注意：这里假设 push 期间 cursor 没变。
        # 如果并发 push，可能导致竞态。但 group+domain 维度的 push 应该是单线程调度的（scheduler）。
        current_cursor = self.db.get_cursor(group_qq, domain_id)
        
        # 2. 查找下一批次
        next_batch = self.db.get_next_batch(domain_id, current_cursor)
        
        if next_batch:
            next_cursor = next_batch['start_index']
        else:
            # 循环回第一批
            first_batch = self.db.get_first_batch(domain_id)
            next_cursor = first_batch['start_index'] if first_batch else 0
            
        if next_cursor > 0:
            self.db.update_cursor(group_qq, domain_id, next_cursor)

    def get_strategy_info(self, group_qq: str, domain_id: int) -> str:
        current_cursor = self.db.get_cursor(group_qq, domain_id)
        batch = self.db.get_batch_by_start_index(domain_id, current_cursor)
        
        if not batch:
            # 可能是 fallback 状态或第一批
            batch = self.db.get_first_batch(domain_id)
            
        if not batch:
             return "📚 批次策略 (未配置批次)"
             
        # 计算这是第几批
        # 这需要查询所有批次来确定 index，稍微有点耗时但这是 info 指令，还好。
        # 为简化，只显示当前批次范围
        return (
             f"📚 批次策略\n"
             f"当前进度: 批次 [{batch['start_index']}-{batch['end_index']}]\n"
             f"下一次: 完成当前批次后自动流转"
        )
