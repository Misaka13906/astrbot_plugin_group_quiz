"""
数据库助手模块
负责 SQLite 数据库的初始化和 CRUD 操作
"""

import os
import sqlite3

from astrbot.api import logger


class QuizDatabase:
    """群聊答题插件数据库管理类"""

    def __init__(self, db_path: str):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 启用字典式访问

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def initialize_schema(self, schema_sql_path: str):
        """
        初始化数据库表结构

        Args:
            schema_sql_path: schema.sql 文件路径
        """
        if not os.path.exists(schema_sql_path):
            logger.error(f"Schema file not found: {schema_sql_path}")
            return False

        try:
            with open(schema_sql_path, encoding="utf-8") as f:
                schema_sql = f.read()

            cursor = self.conn.cursor()
            # 执行所有 SQL 语句
            cursor.executescript(schema_sql)
            self.conn.commit()
            logger.info("Database schema initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            return False

    # ==================== Groups 相关操作 ====================

    def get_all_groups(self) -> list[dict]:
        """获取所有学习小组"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM groups")
        return [dict(row) for row in cursor.fetchall()]

    def get_group_by_name(self, name: str) -> dict | None:
        """根据名称获取小组"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM groups WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # ==================== Domain 相关操作 ====================

    def get_all_domains(self) -> list[dict]:
        """获取所有领域"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, group_id FROM domain")
        return [dict(row) for row in cursor.fetchall()]

    def get_domain_by_name(self, name: str) -> dict | None:
        """根据名称获取领域"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, group_id FROM domain WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # ==================== Users 和 Subscribes 相关操作 ====================

    def ensure_user_exists(self, qq: str) -> bool:
        """确保用户存在，不存在则创建"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (qq) VALUES (?)", (qq,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}")
            return False

    def get_user_groups(self, user_qq: str) -> list[dict]:
        """获取用户加入的所有小组"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT g.id, g.name
            FROM groups g
            JOIN subscribes s ON g.id = s.group_id
            WHERE s.user_qq = ?
        """,
            (user_qq,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def subscribe_group(self, user_qq: str, group_id: int) -> bool:
        """订阅小组"""
        try:
            self.ensure_user_exists(user_qq)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO subscribes (user_qq, group_id)
                VALUES (?, ?)
            """,
                (user_qq, group_id),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to subscribe group: {e}")
            return False

    def unsubscribe_group(self, user_qq: str, group_id: int) -> bool:
        """取消订阅小组"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                DELETE FROM subscribes
                WHERE user_qq = ? AND group_id = ?
            """,
                (user_qq, group_id),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to unsubscribe group: {e}")
            return False

    def get_group_subscribers(self, group_id: int) -> list[str]:
        """获取订阅某个小组的所有用户 QQ"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT user_qq FROM subscribes WHERE group_id = ?
        """,
            (group_id,),
        )
        return [row["user_qq"] for row in cursor.fetchall()]

    # ==================== Problems 相关操作 ====================

    def get_problem_by_id(self, problem_id: int) -> dict | None:
        """根据 ID 获取题目"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT p.*, d.name as domain_name
            FROM problems p
            LEFT JOIN domain d ON p.domain_id = d.id
            WHERE p.id = ?
        """,
            (problem_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_random_problem(self, domain_name: str) -> dict | None:
        """从指定领域随机获取一道题目"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT p.*, d.name as domain_name
            FROM problems p
            JOIN domain d ON p.domain_id = d.id
            WHERE d.name = ?
            ORDER BY RANDOM()
            LIMIT 1
        """,
            (domain_name,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_problems_for_push(self, domain_id: int, limit: int = 3) -> list[dict]:
        """
        获取用于推送的题目（简单模式，无游标跟踪）
        优先使用 domain_settings 中的范围，如果不存在则 fallback 到简单查询

        注意：这是旧方法，保留用于向后兼容。新代码应使用 get_problems_for_push_with_cursor

        Args:
            domain_id: 领域 ID
            limit: 获取的题目数量（仅在 fallback 时使用）

        Returns:
            题目列表
        """
        cursor = self.conn.cursor()

        # 尝试获取 domain_settings
        cursor.execute(
            """
            SELECT start_index, end_index
            FROM domain_settings
            WHERE domain_id = ?
        """,
            (domain_id,),
        )
        settings = cursor.fetchone()

        if settings:
            # 使用 domain_settings 定义的范围
            start_idx = settings["start_index"]
            end_idx = settings["end_index"]

            cursor.execute(
                """
                SELECT p.*, d.name as domain_name
                FROM problems p
                JOIN domain d ON p.domain_id = d.id
                WHERE p.domain_id = ? AND p.id >= ? AND p.id <= ?
                ORDER BY p.id
            """,
                (domain_id, start_idx, end_idx),
            )

            logger.info(
                f"Using domain_settings for domain {domain_id}: "
                f"start={start_idx}, end={end_idx}"
            )
        else:
            # Fallback: 没有 domain_settings，使用简单的 LIMIT 查询
            cursor.execute(
                """
                SELECT p.*, d.name as domain_name
                FROM problems p
                JOIN domain d ON p.domain_id = d.id
                WHERE p.domain_id = ?
                ORDER BY p.id
                LIMIT ?
            """,
                (domain_id, limit),
            )

            logger.info(
                f"No domain_settings found for domain {domain_id}, "
                f"using fallback with limit={limit}"
            )

        return [dict(row) for row in cursor.fetchall()]

    def get_problems_for_push_with_cursor(
        self, group_qq: str, domain_id: int
    ) -> tuple[list[dict], int]:
        """
        基于游标和批次配置获取推送题目

        Args:
            group_qq: 群号
            domain_id: 领域 ID

        Returns:
            (题目列表, 下一批次的cursor值)
        """
        # 1. 获取当前 cursor（批次的 start_index）
        current_cursor = self.get_cursor(group_qq, domain_id)

        # 2. 查找当前批次配置
        batch_config = self._get_batch_by_start_index(domain_id, current_cursor)

        if not batch_config:
            # 没有找到批次配置，使用第一批
            batch_config = self._get_first_batch(domain_id)
            if not batch_config:
                # 该领域没有配置批次，fallback 到简单查询
                logger.warning(
                    f"No domain_settings for domain {domain_id}, using fallback"
                )
                problems = self.get_problems_for_push(domain_id, limit=3)
                return problems, 0  # cursor 保持为 0

        # 3. 根据批次配置获取题目
        problems = self._fetch_problems_in_range(
            domain_id, batch_config["start_index"], batch_config["end_index"]
        )

        # 4. 查找下一批次
        next_batch = self._get_next_batch(domain_id, current_cursor)

        if next_batch:
            next_cursor = next_batch["start_index"]
        else:
            # 没有下一批次，循环回第一批次
            first_batch = self._get_first_batch(domain_id)
            next_cursor = first_batch["start_index"] if first_batch else 0

        logger.info(
            f"Cursor-based push: domain={domain_id}, cursor={current_cursor} -> {next_cursor}, "
            f"batch=[{batch_config['start_index']}-{batch_config['end_index']}], "
            f"problems={len(problems)}"
        )

        return problems, next_cursor

    def get_cursor(self, group_qq: str, domain_id: int) -> int:
        """
        获取当前游标位置（批次的 start_index）
        如果不存在或为0，返回第一批的 start_index

        Args:
            group_qq: 群号
            domain_id: 领域 ID

        Returns:
            当前批次的 start_index
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT now_cursor FROM group_task_config
            WHERE group_qq = ? AND domain_id = ?
        """,
            (group_qq, domain_id),
        )
        row = cursor.fetchone()

        if row and row["now_cursor"] > 0:
            return row["now_cursor"]

        # 返回第一批的 start_index
        first_batch = self._get_first_batch(domain_id)
        return first_batch["start_index"] if first_batch else 1

    def _get_batch_by_start_index(self, domain_id: int, start_idx: int) -> dict | None:
        """根据 start_index 查找批次配置"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM domain_settings
            WHERE domain_id = ? AND start_index = ?
        """,
            (domain_id, start_idx),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_first_batch(self, domain_id: int) -> dict | None:
        """获取第一批配置"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM domain_settings
            WHERE domain_id = ?
            ORDER BY start_index ASC
            LIMIT 1
        """,
            (domain_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_next_batch(self, domain_id: int, current_start_idx: int) -> dict | None:
        """获取下一批配置"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM domain_settings
            WHERE domain_id = ? AND start_index > ?
            ORDER BY start_index ASC
            LIMIT 1
        """,
            (domain_id, current_start_idx),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _fetch_problems_in_range(
        self, domain_id: int, start_idx: int, end_idx: int
    ) -> list[dict]:
        """获取指定范围内的题目"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT p.*, d.name as domain_name
            FROM problems p
            JOIN domain d ON p.domain_id = d.id
            WHERE p.domain_id = ? AND p.id >= ? AND p.id <= ?
            ORDER BY p.id
        """,
            (domain_id, start_idx, end_idx),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ==================== Group Task Config 相关操作 ====================

    def get_group_task_config(self, group_qq: str) -> list[dict]:
        """获取群聊的任务配置"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT gtc.*, d.name as domain_name
            FROM group_task_config gtc
            LEFT JOIN domain d ON gtc.domain_id = d.id
            WHERE gtc.group_qq = ?
        """,
            (group_qq,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_active_group_task_config(self, group_qq: str) -> list[dict]:
        """获取群聊的激活任务配置"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT gtc.*, d.name as domain_name
            FROM group_task_config gtc
            LEFT JOIN domain d ON gtc.domain_id = d.id
            WHERE gtc.group_qq = ? AND gtc.is_active = 1
        """,
            (group_qq,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def upsert_group_task_config(
        self, group_qq: str, domain_id: int, push_time: str, is_active: int
    ) -> bool:
        """
        插入或更新群聊任务配置

        Args:
            group_qq: 群号
            domain_id: 领域 ID
            push_time: 推送时间 (HH:MM)
            is_active: 是否激活 (0/1)
        """
        try:
            cursor = self.conn.cursor()
            # 先检查是否存在
            cursor.execute(
                """
                SELECT id FROM group_task_config
                WHERE group_qq = ? AND domain_id = ?
            """,
                (group_qq, domain_id),
            )
            existing = cursor.fetchone()

            if existing:
                # 更新
                cursor.execute(
                    """
                    UPDATE group_task_config
                    SET push_time = ?, is_active = ?
                    WHERE group_qq = ? AND domain_id = ?
                """,
                    (push_time, is_active, group_qq, domain_id),
                )
            else:
                # 插入
                cursor.execute(
                    """
                    INSERT INTO group_task_config
                    (group_qq, domain_id, push_time, is_active, now_cursor)
                    VALUES (?, ?, ?, ?, 0)
                """,
                    (group_qq, domain_id, push_time, is_active),
                )

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to upsert group task config: {e}")
            return False

    def set_all_domains_active(
        self, group_qq: str, is_active: int, push_time: str
    ) -> bool:
        """设置群聊所有领域的激活状态"""
        try:
            self.conn.cursor()
            domains = self.get_all_domains()

            for domain in domains:
                self.upsert_group_task_config(
                    group_qq, domain["id"], push_time, is_active
                )

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set all domains active: {e}")
            return False

    def deactivate_all_domains(self, group_qq: str) -> bool:
        """关闭群聊所有领域的推送"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE group_task_config
                SET is_active = 0
                WHERE group_qq = ?
            """,
                (group_qq,),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate all domains: {e}")
            return False

    def update_cursor(self, group_qq: str, domain_id: int, new_cursor: int) -> bool:
        """更新推送游标"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE group_task_config
                SET now_cursor = ?
                WHERE group_qq = ? AND domain_id = ?
            """,
                (new_cursor, group_qq, domain_id),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update cursor: {e}")
            return False
