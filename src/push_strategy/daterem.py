import datetime

from .base import PushStrategy


class DateRemainderStrategy(PushStrategy):
    """
    日期取余策略
    根据日期自动选择批次，无状态循环
    """

    def get_problems_to_push(
        self, group_qq: str, domain_id: int, limit: int = 3
    ) -> list[dict]:
        # 1. 获取所有批次
        batches = self.db.get_all_batches(domain_id)
        if not batches:
            # Fallback to simple limit
            return self.db.get_problems_for_push(domain_id, limit=limit)

        # 2. 根据日期计算批次索引
        epoch = datetime.date(2020, 1, 1)
        today = datetime.date.today()
        days_since_epoch = (today - epoch).days
        batch_index = days_since_epoch % len(batches)

        # 3. 获取今天的批次
        batch = batches[batch_index]
        return self.db.get_problems_in_range(
            domain_id, batch.category_id, batch.start_index, batch.end_index
        )

    def on_push_success(
        self, group_qq: str, domain_id: int, problem_ids: list[int]
    ) -> None:
        # 无状态策略，无需更新
        pass

    def get_strategy_info(self, group_qq: str, domain_id: int) -> str:
        batches = self.db.get_all_batches(domain_id)
        if not batches:
            return "📅 日期策略 (未配置批次)"

        epoch = datetime.date(2020, 1, 1)
        today = datetime.date.today()
        days_since_epoch = (today - epoch).days
        batch_index = days_since_epoch % len(batches)
        batch = batches[batch_index]

        return (
            f"📅 日期取余策略 (无状态循环)\n"
            f"循环周期: {len(batches)}天\n"
            f"今日批次: [{batch.start_index}-{batch.end_index}] (第{batch_index + 1}批)"
        )
