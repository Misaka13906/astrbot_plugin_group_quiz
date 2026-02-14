"""
群聊答题插件 - AstrBot Group Quiz Plugin
提供定时推送题目、查询题目答案、小组订阅管理等功能
"""

from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.config.astrbot_config import AstrBotConfig

from .commands import CommandHandlers
from .database import QuizDatabase
from .scheduler import QuizScheduler


class DummyConfig(dict):
    """
    当插件配置为空时使用的占位符配置
    """

    def save_config(self):
        raise RuntimeError(
            "插件配置未初始化，无法保存。请在 AstrBot 配置文件中添加本插件配置。"
        )


@register("group_quiz", "Misaka13906", "群聊答题插件", "v1.0.1")
class GroupQuizPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.context = context
        self.config = config  # 保存插件配置（可能为 None）
        self.db: QuizDatabase | None = None
        self.quiz_scheduler: QuizScheduler | None = None
        self.cmd_handlers: CommandHandlers | None = None

    async def initialize(self):
        """插件初始化"""
        try:
            logger.info("Initializing Group Quiz Plugin...")

            # 检查 config 是否可用
            if self.config is None:
                logger.warning(
                    "Plugin config is None! Using empty config with default behaviors."
                )
                self.config = DummyConfig()
            else:
                # ✅ 问题2修复：统一群号类型为字符串
                if "use_default" in self.config:
                    self.config["use_default"] = [
                        str(g) for g in self.config["use_default"]
                    ]
                    logger.info(
                        f"Normalized use_default group IDs: {self.config['use_default']}"
                    )

            # 初始化数据库
            # 使用 StarTools 获取标准数据目录
            data_dir = StarTools.get_data_dir("astrbot_plugin_group_quiz")
            # StarTools 返回的是 Path 对象
            data_dir.mkdir(parents=True, exist_ok=True)

            plugin_dir = Path(__file__).parent
            db_path = data_dir / "quiz.db"
            schema_path = plugin_dir / "sql" / "schema.sql"

            self.db = QuizDatabase(str(db_path))
            self.db.connect()

            # 检查数据库是否已正确初始化
            is_initialized = False
            if db_path.exists() and db_path.stat().st_size > 0:
                try:
                    with self.db.get_locked_cursor() as cursor:
                        # 检查关键表是否存在
                        cursor.execute(
                            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='problems'"
                        )
                        if cursor.fetchone():
                            is_initialized = True
                except Exception:
                    logger.warning(
                        "Database exists but verification failed, re-initializing..."
                    )

            if not is_initialized:
                logger.info(
                    f"Database not initialized at {db_path}, initializing schema..."
                )
                self.db.initialize_schema(str(schema_path))  # noqa: ASYNC240
                logger.info(
                    "Database schema initialized. Please populate data manually using insert.sql"
                )
            else:
                logger.info(f"Database verified at {db_path}")

            # 初始化命令处理器
            self.cmd_handlers = CommandHandlers(self.context, self.db, self.config)
            logger.info("Command handlers initialized")

            # 初始化调度器
            self.quiz_scheduler = QuizScheduler(self.context, self.db, self.config)
            await self.quiz_scheduler.initialize()
            logger.info("Scheduler initialized")

            # ✅ 问题3修复：将 scheduler 传给 cmd_handlers 以支持动态重载
            self.cmd_handlers.scheduler = self.quiz_scheduler

            logger.info("Group Quiz Plugin initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Group Quiz Plugin: {e}", exc_info=True)
            # 确保 cmd_handlers 至少被创建，即使scheduler失败
            if self.cmd_handlers is None and self.db is not None:
                self.cmd_handlers = CommandHandlers(self.context, self.db, self.config)
            raise

    # ==================== 命令注册 ====================
    # 将命令处理委托给 CommandHandlers

    async def _delegate_to_cmd_handler(
        self, handler_name: str, event: AstrMessageEvent, *args, **kwargs
    ):
        """通用指令转发器"""
        if not self.cmd_handlers:
            yield event.plain_result("❌ 插件尚未准备好，请稍后再试")
            return

        handler = getattr(self.cmd_handlers, handler_name, None)
        if not handler:
            logger.error(f"Command handler {handler_name} not found")
            return

        async for result in handler(event, *args, **kwargs):
            yield result

    @filter.command("lhelp")
    async def cmd_help(self, event: AstrMessageEvent):
        """列出所有可用指令和简要说明"""
        async for result in self._delegate_to_cmd_handler("cmd_help", event):
            yield result

    @filter.command("lgroup")
    async def cmd_list_groups(self, event: AstrMessageEvent):
        """查询所有可加入的小组名"""
        async for result in self._delegate_to_cmd_handler("cmd_list_groups", event):
            yield result

    @filter.command("ldomain")
    async def cmd_list_domains(self, event: AstrMessageEvent):
        """查询所有可查看的领域名"""
        async for result in self._delegate_to_cmd_handler("cmd_list_domains", event):
            yield result

    @filter.command("mygroup")
    async def cmd_my_groups(self, event: AstrMessageEvent):
        """查询你已加入的小组名"""
        async for result in self._delegate_to_cmd_handler("cmd_my_groups", event):
            yield result

    @filter.command("ltask")
    async def cmd_list_task(self, event: AstrMessageEvent):
        """查看本群当前的题目推送状态"""
        async for result in self._delegate_to_cmd_handler("cmd_list_task", event):
            yield result

    @filter.command("addme")
    async def cmd_add_me(self, event: AstrMessageEvent, group_name: str = ""):
        """加入指定小组"""
        async for result in self._delegate_to_cmd_handler(
            "cmd_add_me", event, group_name
        ):
            yield result

    @filter.command("rmme")
    async def cmd_remove_me(self, event: AstrMessageEvent, group_name: str = ""):
        """退出指定小组"""
        async for result in self._delegate_to_cmd_handler(
            "cmd_remove_me", event, group_name
        ):
            yield result

    @filter.command("ans")
    async def cmd_answer(self, event: AstrMessageEvent, problem_id: str = ""):
        """获取指定题目的参考答案"""
        async for result in self._delegate_to_cmd_handler(
            "cmd_answer", event, problem_id
        ):
            yield result

    @filter.command("prob")
    async def cmd_problem(self, event: AstrMessageEvent, problem_id: str = ""):
        """获取指定题目的题面内容"""
        async for result in self._delegate_to_cmd_handler(
            "cmd_problem", event, problem_id
        ):
            yield result

    @filter.command("pushnow")
    async def cmd_push_test(self, event: AstrMessageEvent, domain_name: str = ""):
        """(调试) 立即触发一次推送"""
        async for result in self._delegate_to_cmd_handler(
            "cmd_push_test", event, domain_name
        ):
            yield result

    @filter.command("rand")
    async def cmd_random(self, event: AstrMessageEvent, domain_name: str = ""):
        """随机抽取一道该领域的题目"""
        async for result in self._delegate_to_cmd_handler(
            "cmd_random", event, domain_name
        ):
            yield result

    @filter.command("search")
    async def cmd_search(self, event: AstrMessageEvent, keyword: str = ""):
        """搜索题目：/search <关键词>"""
        async for result in self._delegate_to_cmd_handler("cmd_search", event, keyword):
            yield result

    @filter.command("task")
    async def cmd_task(self, event: AstrMessageEvent):
        """管理员指令：切换本群的题目推送状态"""
        async for result in self._delegate_to_cmd_handler("cmd_task", event):
            yield result

    async def terminate(self):
        """插件销毁"""
        if self.quiz_scheduler:
            self.quiz_scheduler.shutdown()

        if self.db:
            self.db.close()
            logger.info("Database connection closed")

        logger.info("Group Quiz Plugin terminated")
