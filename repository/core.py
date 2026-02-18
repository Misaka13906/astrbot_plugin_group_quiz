import os
import sqlite3
import threading
from contextlib import contextmanager

from astrbot.api import logger

class DatabaseCore:
    """数据库核心功能：连接管理、游标获取、初始化"""

    def __init__(self, db_path: str):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self.lock = threading.RLock()

    def connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 启用字典式访问

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            with self.lock:
                self.conn.close()

    @contextmanager
    def get_locked_cursor(self):
        """
        获取一个带锁的数据库游标 (Context Manager)
        """
        if not self.conn:
            # 这里如果还没连接，抛出异常方便定位问题
            raise RuntimeError("Database not connected. Call connect() first.")

        with self.lock:
            cursor = self.conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

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
            
            # Check and apply migration to v1.1.0
            migration_path = os.path.join(os.path.dirname(schema_sql_path), 'migrate_1.1.0.sql')
            
            with self.get_locked_cursor() as cursor:
                # 执行基础 SQL 语句
                cursor.executescript(schema_sql)
                
                if os.path.exists(migration_path):
                     # Check if we need to migrate (check if column exists)
                    cursor.execute("PRAGMA table_info(group_task_config)")
                    columns = [info[1] for info in cursor.fetchall()]
                    if "strategy_type" not in columns:
                        logger.info("Applying v1.1.0 migration...")
                        with open(migration_path, encoding="utf-8") as mf:
                            cursor.executescript(mf.read())
                            
                self.conn.commit()
            logger.info("Database schema initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}", exc_info=True)
            return False
