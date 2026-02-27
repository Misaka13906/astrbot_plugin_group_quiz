from astrbot.api import logger

from .base import PushStrategy


class BatchStrategy(PushStrategy):
    """
    批次推送策略 (兼容 v1.0.x)
    按预设批次顺序循环推送
    """

    def get_problems_to_push(
        self, group_qq: str, domain_id: int, limit: int = 3
    ) -> list[dict]:
        # 1. 获取当前 cursor (category_id, start_index)
        current_category_id, current_cursor = self.db.get_cursor(group_qq, domain_id)

        # 2. 查找当前批次
        batch = self.db.get_batch_by_start_index(
            domain_id, current_category_id, current_cursor
        )

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
            domain_id, batch.category_id, batch.start_index, batch.end_index
        )

        return problems

    def on_push_success(
        self, group_qq: str, domain_id: int, problem_ids: list[int]
    ) -> None:
        # 计算并更新下一个 cursor

        # 1. 获取当前 cursor
        # 注意：这里假设 push 期间 cursor 没变。
        current_category_id, current_cursor = self.db.get_cursor(group_qq, domain_id)

        # 2. 查找下一批次
        next_batch = self.db.get_next_batch(
            domain_id, current_category_id, current_cursor
        )

        if next_batch:
            next_category_id = next_batch.category_id
            next_cursor = next_batch.start_index
        else:
            # 循环回第一批
            first_batch = self.db.get_first_batch(domain_id)
            if first_batch:
                next_category_id = first_batch.category_id
                next_cursor = first_batch.start_index
            else:
                next_category_id = 0
                next_cursor = 0

        if next_cursor > 0:
            self.db.update_cursor(group_qq, domain_id, next_category_id, next_cursor)

    def get_strategy_info(self, group_qq: str, domain_id: int) -> str:
        current_category_id, current_cursor = self.db.get_cursor(group_qq, domain_id)
        batch = self.db.get_batch_by_start_index(
            domain_id, current_category_id, current_cursor
        )

        if not batch:
            # 可能是 fallback 状态或第一批
            batch = self.db.get_first_batch(domain_id)

        if not batch:
            return "📚 连续顺序推送 (未配置批次)"

        # 需要获取分类名称
        category_name = "未知分类"
        with self.db.get_locked_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM category WHERE id = ?", (batch.category_id,)
            )
            row = cursor.fetchone()
            if row:
                category_name = row["name"]

        return (
            f"📚 连续顺序推送\n"
            f"当前进度: [{category_name}] 第 {batch.start_index} - {batch.end_index} 题\n"
            f"下一次: 完成当前批次后顺延"
        )
