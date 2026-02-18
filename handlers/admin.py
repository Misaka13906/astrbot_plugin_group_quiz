import shlex
from datetime import datetime

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from .base import BaseHandler

class AdminHandlers(BaseHandler):
    """管理员指令处理器"""

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
        try:
            datetime.strptime(push_time, "%H:%M")
        except (ValueError, TypeError):
            yield event.plain_result("❌ 时间格式不正确，应为 HH:MM，如 17:00")
            return

        is_active = 1 if action == "on" else 0

        # 处理 default 切换
        if target == "default":
            config = self.config  # 使用插件配置
            if "use_default" not in config:
                config["use_default"] = []

            use_default_groups = config["use_default"]
            group_qq = str(group_qq)

            if action == "on":
                if group_qq not in use_default_groups:
                    use_default_groups.append(group_qq)
                    try:
                        self.config.save_config()
                    except RuntimeError as e:
                        yield event.plain_result(f"⚠️ {str(e)}")
                        return

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

                if self.scheduler:
                    await self.scheduler.reload_tasks_for_group(group_qq)

                yield event.plain_result("✅ 已在本群切换为使用手动配置并生效")
            return

        # 处理 all
        if target == "all":
            if action == "on":
                self.db.set_all_domains_active(group_qq, 1, push_time)
                if self.scheduler:
                    await self.scheduler.reload_tasks_for_group(group_qq)
                yield event.plain_result(
                    f"✅ 已在本群开启所有领域的题目推送。推送时间：{push_time}"
                )
            else:
                self.db.deactivate_all_domains(group_qq)

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
