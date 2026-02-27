from typing import TYPE_CHECKING

from astrbot.api.event import AstrMessageEvent

if TYPE_CHECKING:
    from ..repository import QuizRepository


class QueryHandlers:
    """查询相关指令处理器"""

    db: "QuizRepository"

    async def cmd_help(self, event: AstrMessageEvent):
        """列出所有可用指令和简要说明"""
        help_text = """每日技术问答插件帮助
用户手册：https://github.com/Misaka13906/astrbot_plugin_group_quiz/blob/master/README.md
📘 插件可用指令：
/lhelp - 列出所有插件可用指令和简要说明
/lgroup - 查询所有可加入的小组名
/ldomain - 查询所有可查看的领域名
/mygroup - 查询你已加入的小组名
/ltask - 查看本群当前的推送任务状态
/lstra - 查看本群当前使用的推送策略及状态
/addme {group_name} - 加入指定小组
/rmme {group_name} - 退出指定小组
/ans {problem_id} - 获取指定题目的参考答案
/prob {problem_id} - 获取指定题目的题面内容
/search {keyword} - 根据关键词搜索题目
/rand {domain_name} - 随机抽取一道该领域的题目
/a {problem_id} {ans_content} - 提交答案
/h {problem_id} - 获取指定题目的下一考点提示
/myscore - 查询个人的经验值和积分
/lrank [领域名] - 查看本群的技术积分榜 (可指定领域)
/task on/off {domain_name}/all/default - （管理员指令）切换本群的题目推送状态
/stra set <策略名> <all/领域名> - （管理员指令）切换推送策略
/stra info <领域名> - 查看指定领域的推送进度
/stra reset <领域名> - （管理员指令）重置指定领域的推送进度
/pushnow {domain_name} - （管理员指令）立即触发一次推送
/vans {problem_id} {default|llm|web} - （管理员指令）查看题目的特定答案字段"""

        yield event.plain_result(help_text)

    async def cmd_list_groups(self, event: AstrMessageEvent):
        """查询所有可加入的小组名"""
        groups = self.db.get_all_groups()

        if not groups:
            yield event.plain_result("📋 当前没有可加入的小组")
            return

        group_names = [g.name for g in groups]
        result = "📋 可加入的小组列表：" + "、".join(group_names)
        yield event.plain_result(result)

    async def cmd_list_domains(self, event: AstrMessageEvent):
        """查询所有可查看的领域名"""
        domains = self.db.get_all_domains()

        if not domains:
            yield event.plain_result("📋 当前没有可查看的领域")
            return

        domain_names = [d.name for d in domains]
        result = "📋 可查看的领域列表：" + "、".join(domain_names)
        yield event.plain_result(result)

    async def cmd_list_task(self, event: AstrMessageEvent):
        """查看本群当前的题目推送状态"""
        group_qq = event.get_group_id()
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        group_qq_str = str(group_qq)
        use_default_groups = [str(g) for g in self.config.get("use_default", [])]

        # 1. 手动配置模式
        if group_qq_str not in use_default_groups:
            configs = self.db.get_active_group_task_config(group_qq_str)
            if not configs:
                yield event.plain_result(
                    "📋 本群当前推送状态设置：\n使用：手动配置\n当前无激活的领域推送"
                )
                return

            result_lines = ["📋 本群当前推送状态设置：", "使用：手动配置"]
            domain_lines = []
            for cfg in configs:
                domain_name = getattr(cfg, "domain_name", "未知") or "未知"
                push_time = cfg.push_time
                now_category_id = cfg.now_category_id or 0
                now_cursor = cfg.now_cursor

                category_name = "未知分类"
                if now_category_id > 0:
                    with self.db.get_locked_cursor() as db_cur:
                        db_cur.execute(
                            "SELECT name FROM category WHERE id = ?", (now_category_id,)
                        )
                        cat_row = db_cur.fetchone()
                        if cat_row:
                            category_name = cat_row["name"]

                domain_lines.append(
                    f"{domain_name}（{push_time}）[进度: {category_name} - 第{now_cursor}题]"
                )

            result_lines.append("已开启的领域：" + "、".join(domain_lines))
            yield event.plain_result("\n".join(result_lines))
            return

        # 2. 周推送默认配置模式
        weekly_settings = self.config.get("settings", {})
        result_lines = ["📋 本群当前推送状态设置：", "使用：周推送默认配置\n"]
        weekday_names = [
            "星期一",
            "星期二",
            "星期三",
            "星期四",
            "星期五",
            "星期六",
            "星期日",
        ]
        domain_progress_map = {}

        for day in weekday_names:
            day_config = weekly_settings.get(day, {})
            push_time = day_config.get("time", "")
            domains = day_config.get("domains", [])

            if not domains:
                result_lines.append(f"{day}：无推送")
                continue

            for domain_name in domains:
                if domain_name in domain_progress_map:
                    continue

                domain_info = self.db.get_domain_by_name(domain_name)
                if not domain_info:
                    domain_progress_map[domain_name] = "?"
                    continue

                cursor_record = self.db.get_group_domain_config(
                    group_qq_str, domain_info.id
                )
                if cursor_record:
                    # 获取分类名
                    cat_id = cursor_record.now_category_id or 0
                    now_cur = cursor_record.now_cursor
                    cat_name = "未知分类"
                    if cat_id > 0:
                        with self.db.get_locked_cursor() as db_cur:
                            db_cur.execute(
                                "SELECT name FROM category WHERE id = ?", (cat_id,)
                            )
                            cat_row = db_cur.fetchone()
                            if cat_row:
                                cat_name = cat_row["name"]
                    domain_progress_map[domain_name] = (cat_name, now_cur)
                else:
                    domain_progress_map[domain_name] = 0

            domain_str = "、".join(domains)
            result_lines.append(f"{day} {push_time}：{domain_str}")

        if domain_progress_map:
            result_lines.append("\n📊 当前进度：")
            for domain_name, cursor_info in domain_progress_map.items():
                if cursor_info == "?":
                    result_lines.append(f"- {domain_name}: 未知领域")
                elif cursor_info == 0:
                    result_lines.append(f"- {domain_name}: 尚未开始")
                else:
                    cat_name, json_cursor = cursor_info
                    result_lines.append(
                        f"- {domain_name}: {cat_name} - 第 {json_cursor} 题"
                    )

        yield event.plain_result("\n".join(result_lines))

    async def cmd_lrank(self, event: AstrMessageEvent, domain_name: str = None):
        """查看本群的技术积分榜"""
        group_qq = event.get_group_id()
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        domain_id = None
        if domain_name:
            domain = self.db.get_domain_by_name(domain_name)
            if not domain:
                yield event.plain_result(f"❌ 领域 [{domain_name}] 不存在")
                return
            domain_id = domain.id
            title = f"🏆 【本群 {domain_name} 领域 战神榜 Top 10】"
        else:
            title = "🏆 【本群八股战神榜 总榜 Top 10】"

        rank_data = self.db.get_group_rank(str(group_qq), domain_id=domain_id, limit=10)

        if not rank_data:
            yield event.plain_result(
                "📊 本群目前还没有答题得分记录，快使用 /rand 随机一道题目答起来吧！"
            )
            return

        result_lines = [title]
        for idx, row in enumerate(rank_data, 1):
            user_id = str(row["user_qq"])
            # 将 ID 脱敏一部分展示
            display_id = (
                user_id[:4] + "***" + user_id[-3:] if len(user_id) > 6 else user_id
            )
            score = round(row["total_score"], 1)
            exp = int(row["total_exp"])
            result_lines.append(f"{idx}. {display_id} - {score}分 ({exp} EXP)")

        yield event.plain_result("\n".join(result_lines))
