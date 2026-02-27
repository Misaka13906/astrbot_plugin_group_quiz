from typing import TYPE_CHECKING

from astrbot.api.event import AstrMessageEvent

if TYPE_CHECKING:
    from ..repository import QuizRepository


class UserHandlers:
    """用户操作指令处理器"""

    db: "QuizRepository"

    async def cmd_my_groups(self, event: AstrMessageEvent):
        """查询你已加入的小组名"""
        user_qq = str(event.get_sender_id())
        groups = self.db.get_user_groups(user_qq)

        if not groups:
            yield event.plain_result("📋 你还没有加入任何小组")
            return

        group_names = [g.name for g in groups]
        result = "📋 你已加入的小组列表：" + "、".join(group_names)
        yield event.plain_result(result)

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
                groups_list = "、".join([g.name for g in all_groups[:5]])
                hint = f"\n\n可用小组：{groups_list}"
                if len(all_groups) > 5:
                    hint += f"\n等共 {len(all_groups)} 个小组"
                hint += "\n使用 /lgroup 查看完整列表"
            else:
                hint = "\n\n系统中暂无小组"

            yield event.plain_result(f"❌ 小组「{group_name}」不存在{hint}")
            return

        user_qq = str(event.get_sender_id())
        success = self.db.subscribe_group(user_qq, group.id)

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
                groups_list = "、".join([g.name for g in my_groups])
                hint = f"\n\n你已加入的小组：{groups_list}"
            else:
                hint = "\n\n你还未加入任何小组"

            yield event.plain_result(f"❌ 小组「{group_name}」不存在{hint}")
            return

        user_qq = str(event.get_sender_id())
        success = self.db.unsubscribe_group(user_qq, group.id)

        if success:
            yield event.plain_result(f"✅ 成功退出小组 [{group_name}]")
        else:
            yield event.plain_result("❌ 退出小组失败，你可能尚未加入该小组")

    async def cmd_myscore(self, event: AstrMessageEvent):
        """查询个人的经验值和积分"""
        user_qq = str(event.get_sender_id())
        stats = self.db.get_user_score_stats(user_qq)

        result_lines = [
            "📊 你的终身荣誉面板：",
            f"⭐ 总积累经验：{stats['exp']} EXP",
            f"🏆 抢得总分：{stats['score']} 分",
        ]

        if stats.get("domains"):
            result_lines.append("\n【各领域专精分布】")
            for d in stats["domains"]:
                d_name = d["domain_name"]
                d_exp = int(d["total_exp"] or 0)
                d_score = round(d["total_score"] or 0, 1)

                # Fetch domain total score explicitly from the query results
                d_total = d.get("domain_total_score")

                # Calculate progress explicitly
                # If d_total is specified and > 0, show percentage and progress bar
                if d_total and d_total > 0:
                    percent = (d_score / d_total) * 100
                    bar_width = 10
                    filled = max(0, min(bar_width, int(bar_width * percent / 100)))
                    bar = "█" * filled + "░" * (bar_width - filled)
                    prog_str = f"{bar} {round(percent, 1)}% ({d_score}/{d_total})"
                else:
                    prog_str = f"{d_score}分"

                result_lines.append(f" - {d_name}: {prog_str} | {d_exp} EXP")

        result_lines.append("\n（每天保持多领域的答题可以成为全栈战神哦~）")
        yield event.plain_result("\n".join(result_lines))
