from astrbot.api import logger

class ProblemMixin:
    """题目相关操作"""

    def get_problem_by_id(self, problem_id: int) -> dict | None:
        """根据 ID 获取题目"""
        with self.get_locked_cursor() as cursor:
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
        with self.get_locked_cursor() as cursor:
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

        注意：这是旧方法，保留用于向后兼容，或者作为 BatchStrategy 的 fallback
        """
        with self.get_locked_cursor() as cursor:
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

    def search_problems(self, keyword: str, limit: int = 5) -> list[dict]:
        """根据关键词搜索题目"""
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.question, p.category, p.topic, d.name as domain_name
                FROM problems p
                JOIN domain d ON p.domain_id = d.id
                WHERE p.question LIKE ?
                LIMIT ?
            """,
                (f"%{keyword}%", limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_problems_in_range(
        self, domain_id: int, start_idx: int, end_idx: int
    ) -> list[dict]:
        """获取指定范围内的题目"""
        with self.get_locked_cursor() as cursor:
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

    def get_problems_by_push_count(
        self, group_qq: str, domain_id: int, limit: int = 3
    ) -> list[dict]:
        """
        获取题目列表（按推送次数升序排序）
        用于 CounterStrategy
        """
        with self.get_locked_cursor() as cursor:
            cursor.execute("""
                SELECT p.*, COALESCE(pc.push_count, 0) as current_count
                FROM problems p
                LEFT JOIN problem_push_count pc 
                    ON p.id = pc.problem_id AND pc.group_qq = ?
                WHERE p.domain_id = ?
                ORDER BY 
                    COALESCE(pc.push_count, 0) ASC,
                    p.id ASC
                LIMIT ?
            """, (group_qq, domain_id, limit))
            return [dict(row) for row in cursor.fetchall()]
