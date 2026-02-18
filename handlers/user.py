from astrbot.api.event import AstrMessageEvent
from .base import BaseHandler

class UserHandlers(BaseHandler):
    """用户操作指令处理器"""

    async def cmd_add_me(self, event: AstrMessageEvent, group_name: str = ""):
        """加入指定小组"""
        if not group_name:
            yield event.plain_result("❌ 请指定小组名称，例如：/addme Java")
            return

        # 查询小组是否存在
        group = self.db.get_group_by_name(group_name)
        if not group:
            all_groups = self.db.get_all_groups()
            if all_groups:
                groups_list = "、".join([g["name"] for g in all_groups[:5]])
                hint = f"\n\n可用小组：{groups_list}"
                if len(all_groups) > 5:
                    hint += f"\n等共 {len(all_groups)} 个小组"
                hint += "\n使用 /lgroup 查看完整列表"
            else:
                hint = "\n\n系统中暂无小组"

            yield event.plain_result(f"❌ 小组「{group_name}」不存在{hint}")
            return

        user_qq = str(event.get_sender_id())
        success = self.db.subscribe_group(user_qq, group["id"])

        if success:
            yield event.plain_result(f"✅ 成功加入小组 [{group_name}]")
        else:
            yield event.plain_result("❌ 加入小组失败，你可能已经加入了该小组")

    async def cmd_remove_me(self, event: AstrMessageEvent, group_name: str = ""):
        """退出指定小组"""
        if not group_name:
            yield event.plain_result("❌ 请指定小组名称，例如：/rmme Java")
            return

        # 查询小组是否存在
        group = self.db.get_group_by_name(group_name)
        if not group:
            user_qq = str(event.get_sender_id())
            my_groups = self.db.get_user_groups(user_qq)
            if my_groups:
                groups_list = "、".join([g["name"] for g in my_groups])
                hint = f"\n\n你已加入的小组：{groups_list}"
            else:
                hint = "\n\n你还未加入任何小组"

            yield event.plain_result(f"❌ 小组「{group_name}」不存在{hint}")
            return

        user_qq = str(event.get_sender_id())
        success = self.db.unsubscribe_group(user_qq, group["id"])

        if success:
            yield event.plain_result(f"✅ 成功退出小组 [{group_name}]")
        else:
            yield event.plain_result("❌ 退出小组失败，你可能尚未加入该小组")

    async def cmd_answer(self, event: AstrMessageEvent, problem_id: str = ""):
        """获取指定题目的参考答案"""
        if not problem_id or not problem_id.isdigit():
            yield event.plain_result("❌ 请提供有效的题目 ID，例如：/ans 123")
            return

        problem = self.db.get_problem_by_id(int(problem_id))

        if not problem:
            yield event.plain_result(f"❌ 未找到题目 ID: {problem_id}")
            return

        # 根据 use_ans 字段决定返回哪个答案
        use_ans = problem.get("use_ans", "default")

        if use_ans == "llm":
            answer = problem.get("llm_ans", "")
        elif use_ans == "none":
            yield event.plain_result(f"📋 题目 ID: {problem_id}\n该题目暂无参考答案")
            return
        else:  # default
            answer = problem.get("default_ans", "")

        if not answer:
            yield event.plain_result(f"📋 题目 ID: {problem_id}\n该题目暂无参考答案")
            return

        result = f"📋 题目 ID: {problem_id}\n参考答案：\n{answer}"
        yield event.plain_result(result)

    async def cmd_problem(self, event: AstrMessageEvent, problem_id: str = ""):
        """获取指定题目的题面内容"""
        if not problem_id or not problem_id.isdigit():
            yield event.plain_result("❌ 请提供有效的题目 ID，例如：/prob 123")
            return

        problem = self.db.get_problem_by_id(int(problem_id))

        if not problem:
            yield event.plain_result(f"❌ 未找到题目 ID: {problem_id}")
            return

        domain_name = problem.get("domain_name", "未知领域")
        result = f"""📋 题目详情 [{domain_name}] [题目 ID: {problem["id"]}]
{problem["question"]}
回复 /ans {problem["id"]} 获取参考答案。"""

        yield event.plain_result(result)

    async def cmd_random(self, event: AstrMessageEvent, domain_name: str = ""):
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

        result = f"""📋 随机题目 [{domain_name}] [题目 ID: {problem["id"]}]
{problem["question"]}
回复 /ans {problem["id"]} 获取参考答案。"""

        yield event.plain_result(result)

    async def cmd_search(self, event: AstrMessageEvent, keyword: str = ""):
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
            domain_name = p.get("domain_name", "Unknown")
            question = p.get("question", "").strip()
            # 简单截断显示
            if len(question) > 30:
                question = question[:30] + "..."

            result_lines.append(f"{idx}. [{domain_name}] [ID:{p['id']}] {question}")

        if len(problems) >= 5:
            result_lines.append("\n(仅显示前 5 条结果，请尝试更精确的关键词)")

        yield event.plain_result("\n".join(result_lines))
