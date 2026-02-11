"""
命令处理器模块
负责处理所有用户命令
"""

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context

from .database import QuizDatabase


class CommandHandlers:
    """命令处理器类"""

    def __init__(self, context: Context, db: QuizDatabase, config):
        """
        初始化命令处理器

        Args:
            context: AstrBot 上下文
            db: 数据库实例
            config: 插件配置
        """
        self.context = context
        self.db = db
        self.config = config  # 保存插件配置

    async def cmd_help(self, event: AstrMessageEvent):
        """列出所有可用指令和简要说明"""
        help_text = """📘 插件可用指令：
/lhelp - 列出所有可用指令和简要说明
/lgroup - 查询所有可加入的小组名
/ldomain - 查询所有可查看的领域名
/mygroup - 查询你已加入的小组名
/ltask - 查看本群当前的题目推送状态
/addme {group_name} - 加入指定小组
/rmme {group_name} - 退出指定小组
/ans {problem_id} - 获取指定题目的参考答案
/rand {domain_name} - 随机抽取一道该领域的题目
/task on/off {domain_name}/all/default - （管理员指令）切换本群的题目推送状态"""

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
        # 获取群号
        group_qq = self._get_group_id(event)
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        config = self.config  # 使用插件配置
        use_default_groups = config.get("use_default", [])

        # 调试日志
        logger.info(f"cmd_list_task: group_qq={group_qq} (type={type(group_qq)})")
        logger.info(f"cmd_list_task: use_default_groups={use_default_groups}")

        # 确保类型一致性：统一转换为字符串比较
        group_qq_str = str(group_qq)
        use_default_groups_str = [str(g) for g in use_default_groups]

        # 检查是否使用默认配置
        if group_qq_str in use_default_groups_str:
            # 显示周推送默认配置
            weekly_settings = config.get("settings", {})
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
            for day in weekday_names:
                day_config = weekly_settings.get(day, {})
                push_time = day_config.get("time", "")
                domains = day_config.get("domains", [])

                if domains:
                    domain_str = "、".join(domains)
                    result_lines.append(f"{day} {push_time}：{domain_str}")
                else:
                    result_lines.append(f"{day}：无推送")

            yield event.plain_result("\n".join(result_lines))
        else:
            # 显示手动配置
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
                domain_lines.append(f"{domain_name}（{push_time}）")

            result_lines.append("已开启的领域：" + "、".join(domain_lines))
            yield event.plain_result("\n".join(result_lines))

    async def cmd_add_me(self, event: AstrMessageEvent, group_name: str = ""):
        """加入指定小组"""
        if not group_name:
            yield event.plain_result("❌ 请指定小组名称，例如：/addme Java")
            return

        # 查询小组是否存在
        group = self.db.get_group_by_name(group_name)
        if not group:
            yield event.plain_result(
                f"❌ 小组 [{group_name}] 不存在，请使用 /lgroup 查看可用小组"
            )
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
            yield event.plain_result(f"❌ 小组 [{group_name}] 不存在")
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

    async def cmd_random(self, event: AstrMessageEvent, domain_name: str = ""):
        """随机抽取一道该领域的题目"""
        if not domain_name:
            yield event.plain_result("❌ 请指定领域名称，例如：/rand Java")
            return

        problem = self.db.get_random_problem(domain_name)

        if not problem:
            yield event.plain_result(f"❌ 领域 [{domain_name}] 中没有题目或领域不存在")
            return

        result = f"""📋 随机题目 [{domain_name}] [题目 ID: {problem["id"]}]
{problem["question"]}
回复 /ans {problem["id"]} 获取参考答案。"""

        yield event.plain_result(result)

    async def cmd_task(self, event: AstrMessageEvent):
        """管理员指令：切换本群的题目推送状态"""
        # 检查管理员权限
        if not event.is_admin():
            yield event.plain_result("❌ 此命令仅限管理员使用")
            return

        # 检查是否在群聊中
        group_qq = self._get_group_id(event)
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        # 解析命令参数
        message = event.message_str.strip()
        parts = message.split()

        if len(parts) < 2:
            yield event.plain_result(
                "❌ 参数不足。用法：/task on/off {domain_name}/all/default {HH:MM}"
            )
            return

        action = parts[1].lower()  # on/off

        if action not in ["on", "off"]:
            yield event.plain_result("❌ 第一个参数必须是 on 或 off")
            return

        if len(parts) < 3:
            yield event.plain_result("❌ 请指定领域名称、all 或 default")
            return

        target = parts[2]  # domain_name/all/default
        push_time = parts[3] if len(parts) > 3 else "17:00"

        # 验证时间格式
        if not self._validate_time_format(push_time):
            yield event.plain_result("❌ 时间格式不正确，应为 HH:MM，如 17:00")
            return

        is_active = 1 if action == "on" else 0

        # 处理 default 切换
        if target == "default":
            config = self.config  # 使用插件配置
            use_default_groups = config.get("use_default", [])

            if action == "on":
                if group_qq not in use_default_groups:
                    use_default_groups.append(group_qq)
                    self.config.save_config()
                yield event.plain_result("✅ 已在本群切换为使用周推送默认配置")
            else:
                if group_qq in use_default_groups:
                    use_default_groups.remove(group_qq)
                    self.config.save_config()
                yield event.plain_result("✅ 已在本群切换为使用手动配置")
            return

        # 处理 all
        if target == "all":
            if action == "on":
                self.db.set_all_domains_active(group_qq, 1, push_time)
                yield event.plain_result(
                    f"✅ 已在本群开启所有领域的题目推送。推送时间：{push_time}"
                )
            else:
                self.db.deactivate_all_domains(group_qq)
                yield event.plain_result("✅ 已在本群关闭所有领域的题目推送")
            return

        # 处理单个领域
        domain = self.db.get_domain_by_name(target)
        if not domain:
            yield event.plain_result(
                f"❌ 领域 [{target}] 不存在，请使用 /ldomain 查看可用领域"
            )
            return

        success = self.db.upsert_group_task_config(
            group_qq, domain["id"], push_time, is_active
        )

        if success:
            action_text = "开启" if is_active else "关闭"
            if is_active:
                yield event.plain_result(
                    f"✅ 已在本群{action_text}领域 [{target}] 的题目推送。推送时间：{push_time}"
                )
            else:
                yield event.plain_result(
                    f"✅ 已在本群{action_text}领域 [{target}] 的题目推送"
                )
        else:
            yield event.plain_result("❌ 操作失败")

    # ==================== 辅助方法 ====================

    def _get_group_id(self, event: AstrMessageEvent) -> str | None:
        """获取群号"""
        # 使用 AstrBot API 提供的方法获取群号
        group_id = event.get_group_id()
        # 如果不是群聊消息，返回空字符串或 None
        if not group_id:
            return None
        return group_id

    def _validate_time_format(self, time_str: str) -> bool:
        """验证时间格式是否为 HH:MM"""
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except Exception:
            return False
