from typing import TYPE_CHECKING

from astrbot.api.event import AstrMessageEvent
from astrbot.core.star.filter.command import GreedyStr

if TYPE_CHECKING:
    from ..repository import QuizRepository


class ProblemHandlers:
    """题目查询与检索处理器"""

    db: "QuizRepository"

    async def cmd_problem(self, event: AstrMessageEvent, problem_id: str):
        """获取指定题目的题面内容"""
        if not problem_id or not problem_id.isdigit():
            yield event.plain_result("❌ 请提供有效的题目 ID，例如：/prob 123")
            return

        problem = self.db.get_problem_by_id(int(problem_id))

        if not problem:
            yield event.plain_result(f"❌ 未找到题目 ID: {problem_id}")
            return

        domain_name = problem.domain_name or "未知领域"
        category_name = problem.category_name or "未知分类"
        topic = problem.topic or "无主题"
        result_lines = []
        result_lines.append(
            f"📋 [ID: {problem.id}] 题目详情 [{domain_name}] [{category_name}] [{topic}]"
        )
        result_lines.append(problem.question)
        result_lines.append("")
        result_lines.append("💡 互动提示：")
        result_lines.append(f"▶ 回复 /a {problem.id} <你的回答> 参与抢分！")
        result_lines.append(f"▶ 回复 /h {problem.id} 获取下一考点提示。")
        result_lines.append(f"▶ 回复 /ans {problem.id} 查看详细参考答案。")
        result = "\n".join(result_lines)

        yield event.plain_result(result)

    async def cmd_random(self, event: AstrMessageEvent, domain_name: str = None):
        """随机抽取一道该领域的题目"""
        if not domain_name:
            yield event.plain_result("❌ 请指定领域名称，例如：/rand Java")
            return

        problem = self.db.get_random_problem(domain_name)

        if not problem:
            yield event.plain_result(
                f"❌ 领域 [{domain_name}] 不存在或该领域中暂无题目。\n\n请使用 /ldomain 查看所有可用领域"
            )
            return

        category_name = problem.category_name or "未知分类"
        topic = problem.topic or "无主题"
        result_lines = []
        result_lines.append(
            f"📋 [ID: {problem.id}] 随机题目 [{domain_name}] [{category_name}] [{topic}]"
        )
        result_lines.append(problem.question)
        result_lines.append("")
        result_lines.append("💡 互动提示：")
        result_lines.append(f"▶ 回复 /a {problem.id} <你的回答> 参与抢分！")
        result_lines.append(f"▶ 回复 /h {problem.id} 获取下一考点提示。")
        result_lines.append(f"▶ 回复 /ans {problem.id} 查看详细参考答案。")
        result = "\n".join(result_lines)

        yield event.plain_result(result)

    async def cmd_search(self, event: AstrMessageEvent, keyword: GreedyStr):
        """根据关键词搜索题目"""
        if not keyword:
            yield event.plain_result("❌ 请提供搜索关键词，例如：/search Java")
            return

        # 默认只显示前 5 条
        problems = self.db.search_problems(keyword, limit=5)

        if not problems:
            yield event.plain_result(f"❌ 未找到包含「{keyword}」的题目")
            return

        result_lines = [f"🔍 搜索结果 (关键字: {keyword}):"]
        for idx, p in enumerate(problems, 1):
            domain_name = p.domain_name or "Unknown"
            category_name = p.category_name or "未知分类"
            topic = p.topic or "无主题"
            question = (p.question or "").strip()
            # 简单截断显示
            if len(question) > 30:
                question = question[:30] + "..."

            result_lines.append(
                f"{idx}. [ID:{p.id}] [{domain_name}] [{category_name}] [{topic}] {question}"
            )

        if len(problems) >= 5:
            result_lines.append("\n(仅显示前 5 条结果，请尝试更精确的关键词)")

        yield event.plain_result("\n".join(result_lines))
