from .base import PushStrategy


class CounterStrategy(PushStrategy):
    """
    计数器策略
    优先推送推送次数最少的题目
    """

    def get_problems_to_push(
        self, group_qq: str, domain_id: int, limit: int = 3
    ) -> list[dict]:
        return self.db.get_problems_by_push_count(group_qq, domain_id, limit)

    def on_push_success(
        self, group_qq: str, domain_id: int, problem_ids: list[int]
    ) -> None:
        for problem_id in problem_ids:
            self.db.update_push_count(group_qq, problem_id)

    def get_strategy_info(self, group_qq: str, domain_id: int) -> str:
        stats = self.db.get_domain_stats(group_qq, domain_id)

        if not stats or stats["total_problems"] == 0:
            return "📊 计数器策略 (暂无数据)"

        return (
            f"📊 计数器策略\n"
            f"总题数: {stats['total_problems']}\n"
            f"累计推送: {stats['total_pushes']}次\n"
            f"平均每题: {stats['avg_pushes']:.1f}次\n"
            f"推送分布: {stats['min_pushes']}~{stats['max_pushes']}次"
        )
