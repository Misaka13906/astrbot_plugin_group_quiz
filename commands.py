"""
命令处理器模块
负责处理所有用户命令
"""

import shlex
from datetime import datetime

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
        self.scheduler = None  # ✅ 问题3修复：将在 initialize 后设置

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
/prob {problem_id} - 获取指定题目的题面内容
/search {keyword} - 根据关键词搜索题目
/rand {domain_name} - 随机抽取一道该领域的题目
/task on/off {domain_name}/all/default - （管理员指令）切换本群的题目推送状态
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

                cursor_record = self.db.get_cursor_record(
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

    async def cmd_add_me(self, event: AstrMessageEvent, group_name: str = ""):
        """加入指定小组"""
        if not group_name:
            yield event.plain_result("❌ 请指定小组名称，例如：/addme Java")
            return

        # 查询小组是否存在
        group = self.db.get_group_by_name(group_name)
        if not group:
            # ✅ 问题8修复：提供更多上下文
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
            # ✅ 问题8修复：提供更多上下文
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

    async def cmd_task(self, event: AstrMessageEvent):
        """管理员指令：切换本群的题目推送状态"""
        # 检查管理员权限
        if not event.is_admin():
            yield event.plain_result("❌ 此命令仅限管理员使用")
            return

        # 检查是否在群聊中
        group_qq = event.get_group_id()
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        # 解析命令参数
        message = event.message_str.strip()
        try:
            parts = shlex.split(message)
        except ValueError as e:
            logger.error(f"Failed to split command message: {e}")
            yield event.plain_result(f"❌ 命令解析失败：{str(e)}")
            return

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
            # ✅ 修复配置同步问题：确保 use_default 存在于 config 对象中
            if "use_default" not in config:
                config["use_default"] = []

            use_default_groups = config["use_default"]

            # ✅ 问题2修复：确保群号是字符串
            group_qq = str(group_qq)

            if action == "on":
                if group_qq not in use_default_groups:
                    use_default_groups.append(group_qq)
                    # ✅ 问题1修复：捕获配置保存异常
                    try:
                        self.config.save_config()
                    except RuntimeError as e:
                        yield event.plain_result(f"⚠️ {str(e)}")
                        return

                # ✅ 问题3修复：动态重载任务
                if self.scheduler:
                    await self.scheduler.reload_tasks_for_group(group_qq)

                yield event.plain_result("✅ 已在本群切换为使用周推送默认配置并生效")
            else:
                if group_qq in use_default_groups:
                    use_default_groups.remove(group_qq)
                    try:
                        self.config.save_config()
                    except RuntimeError as e:
                        yield event.plain_result(f"⚠️ {str(e)}")
                        return

                # 动态重载任务
                if self.scheduler:
                    await self.scheduler.reload_tasks_for_group(group_qq)

                yield event.plain_result("✅ 已在本群切换为使用手动配置并生效")
            return

        # 处理 all
        if target == "all":
            if action == "on":
                self.db.set_all_domains_active(group_qq, 1, push_time)
                # ✅ 问题3修复：动态重载任务
                if self.scheduler:
                    await self.scheduler.reload_tasks_for_group(group_qq)
                yield event.plain_result(
                    f"✅ 已在本群开启所有领域的题目推送。推送时间：{push_time}"
                )
            else:
                self.db.deactivate_all_domains(group_qq)

                # ✅ 修复：如果是 default 模式下的群，task off all 也应该将其从 default 列表中移除
                # 否则 reload 后还是会加载 default 的任务
                config = self.config
                if "use_default" not in config:
                    config["use_default"] = []
                use_default_groups = config["use_default"]

                if group_qq in use_default_groups:
                    use_default_groups.remove(group_qq)
                    try:
                        self.config.save_config()
                    except RuntimeError as e:
                        yield event.plain_result(f"⚠️ {str(e)}")
                        return

                if self.scheduler:
                    await self.scheduler.reload_tasks_for_group(group_qq)
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
            # ✅ 修复：配置单个领域后也需要重载任务
            if self.scheduler:
                await self.scheduler.reload_tasks_for_group(group_qq)

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

    async def cmd_push_test(self, event: AstrMessageEvent, domain_name: str = ""):
        """(调试) 立即触发一次推送"""
        if not event.is_admin():
            yield event.plain_result("❌ 此命令仅限管理员使用")
            return

        if not domain_name:
            yield event.plain_result("❌ 请指定领域名称")
            return

        group_qq = str(event.get_group_id())
        domain = self.db.get_domain_by_name(domain_name)
        if not domain:
            yield event.plain_result("❌ 领域不存在")
            return

        if not self.scheduler:
            yield event.plain_result("❌ 调度器未初始化")
            return

        yield event.plain_result(f"🚀 正尝试立即推送 [{domain_name}] 到本群...")
        # 直接调用回调
        await self.scheduler._push_callback(group_qq, domain["id"], domain["name"])

    # ==================== 辅助方法 ====================

    def _validate_time_format(self, time_str: str) -> bool:
        """验证时间格式是否为 HH:MM"""
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except (ValueError, TypeError):
            return False
