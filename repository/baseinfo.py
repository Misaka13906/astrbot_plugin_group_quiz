from astrbot.api import logger

class BaseInfoMixin:
    """基础信息操作：Groups, Domains, Users, Subscribes"""

    # ==================== Groups 相关操作 ====================

    def get_all_groups(self) -> list[dict]:
        """获取所有学习小组"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("SELECT id, name FROM groups")
            return [dict(row) for row in cursor.fetchall()]

    def get_group_by_name(self, name: str) -> dict | None:
        """根据名称获取小组"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("SELECT id, name FROM groups WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== Domain 相关操作 ====================

    def get_all_domains(self) -> list[dict]:
        """获取所有领域"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("SELECT * FROM domain")
            return [dict(row) for row in cursor.fetchall()]

    def get_domain_by_name(self, name: str) -> dict | None:
        """根据名称获取领域"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("SELECT * FROM domain WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== Users 和 Subscribes 相关操作 ====================

    def ensure_user_exists(self, qq: str) -> bool:
        """确保用户存在，不存在则创建"""
        try:
            with self.get_locked_cursor() as cursor:
                cursor.execute("INSERT OR IGNORE INTO users (qq) VALUES (?)", (qq,))
                self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}", exc_info=True)
            return False

    def get_user_groups(self, user_qq: str) -> list[dict]:
        """获取用户加入的所有小组"""
        with self.get_locked_cursor() as cursor:
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
            with self.get_locked_cursor() as cursor:
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
            logger.error(f"Failed to subscribe group: {e}", exc_info=True)
            return False

    def unsubscribe_group(self, user_qq: str, group_id: int) -> bool:
        """取消订阅小组"""
        try:
            with self.get_locked_cursor() as cursor:
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
            logger.error(f"Failed to unsubscribe group: {e}", exc_info=True)
            return False

    def get_group_subscribers(self, group_id: int) -> list[str]:
        """获取订阅某个小组的所有用户 QQ"""
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                SELECT user_qq FROM subscribes WHERE group_id = ?
            """,
                (group_id,),
            )
            return [row["user_qq"] for row in cursor.fetchall()]
