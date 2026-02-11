"""
群聊答题插件 - AstrBot Group Quiz Plugin
提供定时推送题目、查询题目答案、小组订阅管理等功能
"""

import os
import traceback

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
        logger.warning("Config is dummy, changes will not be saved.")


@register("group_quiz", "Misaka13906", "群聊答题插件", "v1.0.0")
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

            # 初始化数据库
            # 使用 StarTools 获取标准数据目录
            data_dir = StarTools.get_data_dir("astrbot_plugin_group_quiz")
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            plugin_dir = os.path.dirname(__file__)
            db_path = os.path.join(data_dir, "quiz.db")
            schema_path = os.path.join(plugin_dir, "sql", "schema.sql")

            self.db = QuizDatabase(db_path)
            self.db.connect()

            # 检查数据库是否存在，不存在则初始化
            if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
                logger.info(f"Database not found at {db_path}, initializing schema...")
                self.db.initialize_schema(schema_path)  # noqa: ASYNC240
                logger.info(
                    "Database schema initialized. Please populate data manually using insert.sql"
                )
            else:
                logger.info(f"Database found at {db_path}")

            # 初始化命令处理器
            self.cmd_handlers = CommandHandlers(self.context, self.db, self.config)
            logger.info("Command handlers initialized")

            # 初始化调度器
            self.quiz_scheduler = QuizScheduler(self.context, self.db, self.config)
            await self.quiz_scheduler.initialize()
            logger.info("Scheduler initialized")

            logger.info("Group Quiz Plugin initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Group Quiz Plugin: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # 确保 cmd_handlers 至少被创建，即使scheduler失败
            if self.cmd_handlers is None and self.db is not None:
                self.cmd_handlers = CommandHandlers(self.context, self.db, self.config)
            raise

    # ==================== 命令注册 ====================
    # 将命令处理委托给 CommandHandlers

    @filter.command("lhelp")
    async def cmd_help(self, event: AstrMessageEvent):
        """列出所有可用指令和简要说明"""
        async for result in self.cmd_handlers.cmd_help(event):
            yield result

    @filter.command("lgroup")
    async def cmd_list_groups(self, event: AstrMessageEvent):
        """查询所有可加入的小组名"""
        async for result in self.cmd_handlers.cmd_list_groups(event):
            yield result

    @filter.command("ldomain")
    async def cmd_list_domains(self, event: AstrMessageEvent):
        """查询所有可查看的领域名"""
        async for result in self.cmd_handlers.cmd_list_domains(event):
            yield result

    @filter.command("mygroup")
    async def cmd_my_groups(self, event: AstrMessageEvent):
        """查询你已加入的小组名"""
        async for result in self.cmd_handlers.cmd_my_groups(event):
            yield result

    @filter.command("ltask")
    async def cmd_list_task(self, event: AstrMessageEvent):
        """查看本群当前的题目推送状态"""
        async for result in self.cmd_handlers.cmd_list_task(event):
            yield result

    @filter.command("addme")
    async def cmd_add_me(self, event: AstrMessageEvent, group_name: str = ""):
        """加入指定小组"""
        async for result in self.cmd_handlers.cmd_add_me(event, group_name):
            yield result

    @filter.command("rmme")
    async def cmd_remove_me(self, event: AstrMessageEvent, group_name: str = ""):
        """退出指定小组"""
        async for result in self.cmd_handlers.cmd_remove_me(event, group_name):
            yield result

    @filter.command("ans")
    async def cmd_answer(self, event: AstrMessageEvent, problem_id: str = ""):
        """获取指定题目的参考答案"""
        async for result in self.cmd_handlers.cmd_answer(event, problem_id):
            yield result

    @filter.command("rand")
    async def cmd_random(self, event: AstrMessageEvent, domain_name: str = ""):
        """随机抽取一道该领域的题目"""
        async for result in self.cmd_handlers.cmd_random(event, domain_name):
            yield result

    @filter.command("task")
    async def cmd_task(self, event: AstrMessageEvent):
        """管理员指令：切换本群的题目推送状态"""
        async for result in self.cmd_handlers.cmd_task(event):
            yield result

    @filter.command("debugconfig")
    async def cmd_debugconfig(self, event: AstrMessageEvent):
        """临时调试命令：查看配置信息"""
        config = self.config  # 使用插件配置
        use_default = config.get("use_default", [])
        settings = config.get("settings", {})
        group_id = event.get_group_id()

        debug_info = f"""🔍 配置调试信息：
群号: {group_id}
群号类型: {type(group_id)}

use_default: {use_default}
use_default 类型: {type(use_default)}

settings 键: {list(settings.keys())}

群号是否在列表中: {group_id in use_default if isinstance(use_default, list) else "N/A"}
字符串群号是否在列表中: {str(group_id) in [str(x) for x in use_default] if isinstance(use_default, list) else "N/A"}
"""
        yield event.plain_result(debug_info)

    async def terminate(self):
        """插件销毁"""
        if self.quiz_scheduler:
            self.quiz_scheduler.shutdown()

        if self.db:
            self.db.close()
            logger.info("Database connection closed")

        logger.info("Group Quiz Plugin terminated")
