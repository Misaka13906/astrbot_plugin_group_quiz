"""
调度器管理模块
负责管理定时推送任务
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from astrbot.api import logger
from astrbot.api.event import MessageEventResult
from astrbot.api.message_components import At, Plain
from astrbot.api.star import Context

from .database import QuizDatabase


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

    def __init__(self, context: Context, db: QuizDatabase, config):
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

        # 加载周推送默认配置
        await self._load_weekly_tasks(use_default_groups)

        # 加载手动配置
        await self._load_manual_tasks(use_default_groups)

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

                push_time = day_config.get("time", "17:00")
                domains = day_config.get("domains", [])

                if not domains:
                    continue

                # 为每个领域添加定时任务
                for domain_name in domains:
                    domain = self.db.get_domain_by_name(domain_name)
                    if not domain:
                        logger.warning(f"Domain not found: {domain_name}")
                        continue

                    hour, minute = push_time.split(":")
                    trigger = CronTrigger(
                        day_of_week=self.WEEKDAY_MAP[day_name],
                        hour=int(hour),
                        minute=int(minute),
                    )

                    self.scheduler.add_job(
                        self._push_callback,
                        trigger,
                        args=[group_qq, domain["id"], domain_name],
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
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT gtc.group_qq, gtc.domain_id, gtc.push_time, d.name as domain_name
            FROM group_task_config gtc
            JOIN domain d ON gtc.domain_id = d.id
            WHERE gtc.is_active = 1
        """)
        manual_configs = cursor.fetchall()

        for config in manual_configs:
            group_qq = config["group_qq"]
            domain_id = config["domain_id"]
            push_time = config["push_time"]
            domain_name = config["domain_name"]

            # 跳过使用默认配置的群
            if group_qq in use_default_groups:
                continue

            # 解析时间
            try:
                hour, minute = push_time.split(":")
                trigger = CronTrigger(hour=int(hour), minute=int(minute))

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
                    f"domain {domain_name}: {e}"
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
            # 使用游标和批次配置获取题目
            problems, next_cursor = self.db.get_problems_for_push_with_cursor(
                group_qq, domain_id
            )

            if not problems:
                logger.warning(f"No problems found for domain {domain_name}")
                return

            # 获取该领域对应的小组
            domain_info = self.db.get_domain_by_name(domain_name)
            if not domain_info:
                logger.warning(f"Domain info not found: {domain_name}")
                return

            group_id = domain_info.get("group_id")
            if not group_id:
                logger.warning(f"No group_id for domain: {domain_name}")
                return

            # 获取订阅该小组的用户
            subscribers = self.db.get_group_subscribers(group_id)

            # 构建推送消息
            message_chain = self._format_push_message(
                domain_name, problems, subscribers
            )

            # 发送消息
            result = MessageEventResult()
            for component in message_chain:
                result.use_t2i = False
                result.chain.append(component)

            # 使用统一消息来源发送
            # 格式：platform_id:message_type:session_id
            # 尝试通过所有可用平台发送消息
            if (
                not hasattr(self.context, "platform_manager")
                or not self.context.platform_manager.platform_insts
            ):
                logger.error("No platform available to send message")
                return

            sent_success = False
            for platform in self.context.platform_manager.platform_insts:
                try:
                    platform_id = platform.meta().id
                    # 构建正确的 unified_msg_origin
                    # 格式：platform_id:MessageType:session_id
                    unified_msg_origin = f"{platform_id}:GroupMessage:{group_qq}"

                    await self.context.send_message(unified_msg_origin, result)
                    logger.info(
                        f"Pushed {len(problems)} problems to group {group_qq} via {platform_id}"
                    )
                    sent_success = True
                    break  # 假设一个群只属于一个平台，发送成功即停止
                except Exception as e:
                    # 仅记录调试信息，尝试下一个平台
                    logger.debug(
                        f"Failed to send to group {group_qq} via {platform_id}: {e}"
                    )

            if not sent_success:
                logger.error(
                    f"Failed to push message to group {group_qq}. Use 'debug' level log to see details."
                )

            # 推送成功后更新游标到下一批次
            if next_cursor > 0:  # 只有在使用批次系统时才更新
                self.db.update_cursor(group_qq, domain_id, next_cursor)
                logger.info(
                    f"Updated cursor to {next_cursor} for group {group_qq}, domain {domain_id}"
                )

        except Exception as e:
            logger.error(f"Error in push callback: {e}", exc_info=True)

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
            text_lines.append(f"[题目 ID: {problem['id']}]")
            text_lines.append(problem["question"])
            text_lines.append("")  # 空行

        text_lines.append("回复 /ans {id} 获取参考答案。")

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
