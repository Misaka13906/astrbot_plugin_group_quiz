from astrbot.api.event import AstrMessageEvent
from .base import BaseHandler

class QueryHandlers(BaseHandler):
    """查询相关指令处理器"""

    async def cmd_help(self, event: AstrMessageEvent):
        """列出所有可用指令和简要说明"""
        help_text = """📘 插件可用指令：
/lhelp - 列出所有可用指令和简要说明
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
/task on/off {domain_name}/all/default - （管理员指令）切换本群的题目推送状态
/stra set <策略名> <all/领域名> - （管理员指令）切换推送策略
/stra info <领域名> - 查看指定领域的推送进度
/stra reset <领域名> - （管理员指令）重置指定领域的推送进度
/pushnow {domain_name} - （管理员指令）立即触发一次推送"""

        yield event.plain_result(help_text)

    async def cmd_list_groups(self, event: AstrMessageEvent):
        """查询所有可加入的小组名"""
        groups = self.db.get_all_groups()

        if not groups:
            yield event.plain_result("📋 当前没有可加入的小组")
            return

        group_names = [g["name"] for g in groups]
        result = "📋 可加入的小组列表：" + "、".join(group_names)
        yield event.plain_result(result)

    async def cmd_list_domains(self, event: AstrMessageEvent):
        """查询所有可查看的领域名"""
        domains = self.db.get_all_domains()

        if not domains:
            yield event.plain_result("📋 当前没有可查看的领域")
            return

        domain_names = [d["name"] for d in domains]
        result = "📋 可查看的领域列表：" + "、".join(domain_names)
        yield event.plain_result(result)

    async def cmd_my_groups(self, event: AstrMessageEvent):
        """查询你已加入的小组名"""
        user_qq = str(event.get_sender_id())
        groups = self.db.get_user_groups(user_qq)

        if not groups:
            yield event.plain_result("📋 你还没有加入任何小组")
            return

        group_names = [g["name"] for g in groups]
        result = "📋 你已加入的小组列表：" + "、".join(group_names)
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
                domain_name = cfg.get("domain_name", "未知")
                push_time = cfg.get("push_time", "17:00")
                now_cursor = cfg.get("now_cursor", 0)
                domain_lines.append(
                    f"{domain_name}（{push_time}）[进度: 第{now_cursor}题]"
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
                    group_qq_str, domain_info["id"]
                )
                domain_progress_map[domain_name] = (
                    cursor_record["now_cursor"] if cursor_record else 0
                )

            domain_str = "、".join(domains)
            result_lines.append(f"{day} {push_time}：{domain_str}")

        if domain_progress_map:
            result_lines.append("\n📊 当前进度：")
            for domain_name, cursor in domain_progress_map.items():
                if cursor == "?":
                    result_lines.append(f"- {domain_name}: 未知领域")
                elif cursor == 0:
                    result_lines.append(f"- {domain_name}: 尚未开始")
                else:
                    result_lines.append(f"- {domain_name}: 第 {cursor} 题")

        yield event.plain_result("\n".join(result_lines))
