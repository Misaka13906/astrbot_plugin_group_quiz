"""
调度器管理模块
负责管理定时推送任务
"""

import sqlite3
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from astrbot.api import logger
from astrbot.api.event import MessageEventResult
from astrbot.api.message_components import At, Plain
from astrbot.api.star import Context

from .push_strategy.factory import StrategyFactory
from .repository import QuizRepository
from .repository.models import GroupTaskConfig


class QuizScheduler:
    """题目推送调度器"""

    # 星期映射
    WEEKDAY_MAP = {
        "星期一": 0,
        "星期二": 1,
        "星期三": 2,
        "星期四": 3,
        "星期五": 4,
        "星期六": 5,
        "星期日": 6,
    }

    def __init__(self, context: Context, db: QuizRepository, config):
        """
        初始化调度器

        Args:
            context: AstrBot 上下文
            db: 数据库实例
            config: 插件配置
        """
        self.context = context
        self.db = db
        self.config = config  # 保存插件配置
        self.scheduler: AsyncIOScheduler | None = None

    async def initialize(self):
        """初始化调度器并加载所有任务"""
        self.scheduler = AsyncIOScheduler()
        await self._load_all_tasks()
        self.scheduler.start()
        logger.info("Scheduler started")

    async def _load_all_tasks(self):
        """加载所有推送任务（周配置 + 手动配置）"""
        config = self.config  # 使用插件配置
        use_default_groups = config.get("use_default", [])

        # ✅ 问题2修复：统一转换为字符串
        use_default_groups = [str(g) for g in use_default_groups]

        # 加载周推送默认配置
        await self._load_weekly_tasks(use_default_groups)

        # 加载手动配置
        await self._load_manual_tasks(use_default_groups)

    async def reload_tasks_for_group(self, group_qq: str):
        """
        ✅ 问题3修复：重新加载指定群的任务

        Args:
            group_qq: 群号
        """
        group_qq = str(group_qq)

        # 1. 移除该群的所有任务
        jobs = self.scheduler.get_jobs()
        removed_count = 0
        for job in jobs:
            if group_qq in job.id:
                self.scheduler.remove_job(job.id)
                removed_count += 1

        logger.info(f"Removed {removed_count} existing tasks for group {group_qq}")

        # 2. 检查该群是否使用默认配置
        use_default_groups = [str(g) for g in self.config.get("use_default", [])]

        if group_qq in use_default_groups:
            # 重新加载周配置任务
            await self._load_weekly_tasks([group_qq])
            logger.info(f"Reloaded weekly tasks for group {group_qq}")
        else:
            # 重新加载手动配置任务
            # ✅ 修复：这里应该传真实的 use_default_groups，而不是 [group_qq]
            # 否则 _load_manual_tasks 会把当前群当在这个列表里从而跳过加载
            await self._load_manual_tasks(use_default_groups)
            logger.info(f"Reloaded manual tasks for group {group_qq}")

    async def _load_weekly_tasks(self, use_default_groups: list[str]):
        """
        加载周推送默认配置的任务

        Args:
            use_default_groups: 使用默认配置的群号列表
        """
        config = self.config  # 使用插件配置
        weekly_settings = config.get("settings", {})

        for group_qq in use_default_groups:
            for day_name, day_config in weekly_settings.items():
                if day_name not in self.WEEKDAY_MAP:
                    continue

                push_time = day_config.get("time", "12:00")
                domains = day_config.get("domains", [])

                if not domains:
                    continue

                # 为每个领域添加定时任务
                for domain_name in domains:
                    domain = self.db.get_domain_by_name(domain_name)
                    if not domain:
                        logger.warning(f"Domain not found: {domain_name}")
                        continue

                    # ✅ Bug 1 修复：确保 cursor 记录存在
                    cursor_record = self.db.get_group_domain_config(group_qq, domain.id)
                    if not cursor_record:
                        self.db.init_group_domain_config(group_qq, domain.id, push_time)
                        logger.info(
                            f"Initialized cursor for weekly config: "
                            f"group={group_qq}, domain={domain_name}"
                        )

                    # 解析并验证时间格式
                    try:
                        dt = datetime.strptime(push_time, "%H:%M")
                        hour, minute = dt.hour, dt.minute
                    except (ValueError, TypeError):
                        logger.error(
                            f"Invalid time format '{push_time}' for group {group_qq}, "
                            f"domain {domain_name}, skipping task"
                        )
                        continue

                    trigger = CronTrigger(
                        day_of_week=self.WEEKDAY_MAP[day_name],
                        hour=hour,
                        minute=minute,
                    )

                    self.scheduler.add_job(
                        self._push_callback,
                        trigger,
                        args=[group_qq, domain.id, domain_name],
                        id=f"default_{group_qq}_{day_name}_{domain_name}",
                        replace_existing=True,
                        misfire_grace_time=300,
                    )
                    logger.info(
                        f"Added weekly task: group={group_qq}, day={day_name}, "
                        f"domain={domain_name}, time={push_time}"
                    )

    async def _load_manual_tasks(self, use_default_groups: list[str]):
        """
        加载手动配置的任务

        Args:
            use_default_groups: 使用默认配置的群号列表（需跳过）
        """
        with self.db.get_locked_cursor() as cursor:
            cursor.execute("""
                SELECT gtc.*, d.name as domain_name
                FROM group_task_config gtc
                JOIN domain d ON gtc.domain_id = d.id
                WHERE gtc.is_active = 1
            """)
            manual_configs = [GroupTaskConfig(**dict(row)) for row in cursor.fetchall()]

        for config in manual_configs:
            group_qq = config.group_qq
            domain_id = config.domain_id
            push_time = config.push_time
            domain_name = config.domain_name or ""

            # 跳过使用默认配置的群
            if group_qq in use_default_groups:
                continue

            # 解析并验证时间格式
            try:
                dt = datetime.strptime(push_time, "%H:%M")
                trigger = CronTrigger(hour=dt.hour, minute=dt.minute)
            except (ValueError, TypeError):
                logger.error(
                    f"Invalid time format '{push_time}' in database for "
                    f"group {group_qq}, domain {domain_name}, skipping task"
                )
                continue

            try:
                self.scheduler.add_job(
                    self._push_callback,
                    trigger,
                    args=[group_qq, domain_id, domain_name],
                    id=f"manual_{group_qq}_{domain_name}",
                    replace_existing=True,
                    misfire_grace_time=300,
                )
                logger.info(
                    f"Added manual task: group={group_qq}, "
                    f"domain={domain_name}, time={push_time}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to add manual task for group {group_qq}, "
                    f"domain {domain_name}: {e}",
                    exc_info=True,
                )

    async def _push_callback(self, group_qq: str, domain_id: int, domain_name: str):
        """
        定时推送回调函数（使用游标系统）

        Args:
            group_qq: 群号
            domain_id: 领域 ID
            domain_name: 领域名称
        """
        logger.info(f"Push callback triggered: group={group_qq}, domain={domain_name}")

        try:
            # 获取该领域对应的信息 (包含 default_batch_size)
            domain_info = self.db.get_domain_by_name(domain_name)
            if not domain_info:
                logger.warning(f"Push aborted: Domain info not found for {domain_name}")
                return

            batch_size = domain_info.default_batch_size or 3

            # 1. 获取策略实例
            strategy = StrategyFactory.get_group_strategy(self.db, group_qq, domain_id)

            # 2. 使用策略获取题目
            problems = strategy.get_problems_to_push(
                group_qq, domain_id, limit=batch_size
            )

            if not problems:
                logger.warning(
                    f"Push skipped: No problems found for domain {domain_name} (ID: {domain_id})"
                )
                msg_text = f"📅 今日八股推送 [{domain_name}]\n\n该领域暂无题目"
                from astrbot.api.message_components import Plain

                await self._send_push_message(group_qq, [Plain(msg_text)])
                return

            group_id = domain_info.group_id
            if not group_id:
                logger.warning(
                    f"Push metadata missing: No group_id defined for domain {domain_name}"
                )
                return

            # 获取订阅该小组的用户
            subscribers = self.db.get_group_subscribers(group_id)
            logger.debug(
                f"Pushing to {group_qq}, domain {domain_name}, subscribers count: {len(subscribers)}"
            )

            # 构建推送消息
            message_chain = self._format_push_message(
                domain_name, problems, subscribers
            )

            # 3. 发送消息
            sent_success = await self._send_push_message(group_qq, message_chain)

            if not sent_success:
                logger.error(
                    f"Final Failure: Could not push message to group {group_qq} on any available platform"
                )
                return

            # 4. 推送成功回调 (更新状态)
            problem_ids = [p.id for p in problems]
            strategy.on_push_success(group_qq, domain_id, problem_ids)
            logger.info(f"Strategy callback completed: {type(strategy).__name__}")

        except sqlite3.Error as e:
            logger.error(
                f"Database error in push callback for group {group_qq}, domain {domain_name}: {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in push callback for group {group_qq}, domain {domain_name}: {e}",
                exc_info=True,
            )

    async def _send_push_message(self, group_qq: str, message_chain: list) -> bool:
        """
        发送推送消息到所有可用平台

        Args:
            group_qq: 群号
            message_chain: 消息链

        Returns:
            bool: 是否发送成功
        """
        # 发送消息
        result = MessageEventResult()
        result.use_t2i = False
        result.chain = message_chain

        # 尝试通过所有可用平台发送消息
        if (
            not hasattr(self.context, "platform_manager")
            or not self.context.platform_manager.platform_insts
        ):
            logger.error(
                "Critical: No platform instances found in context.platform_manager"
            )
            return False

        sent_success = False
        for platform in self.context.platform_manager.platform_insts:
            try:
                # 使用 platform.meta().id 是最稳健的方式
                platform_id = platform.meta().id

                # 构建正确的 unified_msg_origin
                # 格式：platform_id:MessageType:session_id
                # 绝大多数 adapter 期望 MessageType 为 GroupMessage (帕斯卡命名)
                unified_msg_origin = f"{platform_id}:GroupMessage:{group_qq}"

                await self.context.send_message(unified_msg_origin, result)
                logger.info(
                    f"Successfully pushed to group {group_qq} via platform {platform_id}"
                )
                sent_success = True
                break  # 发送成功即停止
            except Exception as e:
                logger.warning(
                    f"Failed push attempt to group {group_qq} via {platform_id if 'platform_id' in locals() else 'unknown'}: {e}"
                )

        return sent_success

    def _format_push_message(
        self, domain_name: str, problems: list[dict], subscribers: list[str]
    ) -> list:
        """
        格式化推送消息

        Args:
            domain_name: 领域名称
            problems: 题目列表
            subscribers: 订阅用户 QQ 列表

        Returns:
            消息链组件列表
        """
        # 构建完整的文本消息（用列表拼接，然后用 \n 连接）
        text_lines = []
        text_lines.append(f"📅 今日八股推送 [{domain_name}]")
        text_lines.append("")  # 空行

        for problem in problems:
            category_name = problem.category_name or "未知分类"
            topic = problem.topic or "无主题"
            text_lines.append(f"[ID: {problem.id}] [{category_name}] [{topic}]")
            text_lines.append(problem.question)
            text_lines.append("")  # 空行

        text_lines.append("💡 互动提示：")
        text_lines.append("▶ 回复 /a <题目ID> <你的回答> 参与抢分！")
        text_lines.append("▶ 回复 /h <题目ID> 获取下一考点提示。")
        text_lines.append("▶ 回复 /ans <题目ID> 查看详细参考答案。")

        # 如果有订阅者，添加到文本末尾
        message_text = "\n".join(text_lines)

        # 构建消息链
        message_chain = []
        message_chain.append(Plain(message_text))

        # 只有 @ 用 message_chain
        if subscribers:
            message_chain.append(Plain("\n\n"))
            for user_qq in subscribers:
                message_chain.append(At(qq=user_qq))
                message_chain.append(Plain(" "))

        return message_chain

    def shutdown(self):
        """关闭调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
