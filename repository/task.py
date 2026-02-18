from astrbot.api import logger

class TaskMixin:
    """任务配置与推送策略相关操作"""

    # ==================== Group Task Config 相关操作 ====================

    def get_group_task_config(self, group_qq: str) -> list[dict]:
        """获取群聊的任务配置"""
        with self.get_locked_cursor() as cursor:
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
        with self.get_locked_cursor() as cursor:
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
        self,
        group_qq: str,
        domain_id: int,
        push_time: str,
        is_active: int,
        commit: bool = True,
    ) -> bool:
        """
        插入或更新群聊任务配置
        """
        try:
            with self.get_locked_cursor() as cursor:
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
                    logger.info(
                        f"Updated task config for group {group_qq}, domain {domain_id}"
                    )
                else:
                    # 插入前先获取初始 cursor
                    first_batch = self.get_first_batch(domain_id)
                    initial_cursor = first_batch["start_index"] if first_batch else 1

                    # 插入
                    cursor.execute(
                        """
                        INSERT INTO group_task_config
                        (group_qq, domain_id, push_time, is_active, now_cursor)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (group_qq, domain_id, push_time, is_active, initial_cursor),
                    )
                    logger.info(
                        f"Inserted task config for group {group_qq}, domain {domain_id}, "
                        f"initial cursor={initial_cursor}"
                    )

                if commit:
                    self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to upsert group task config: {e}", exc_info=True)
            return False

    def set_all_domains_active(
        self, group_qq: str, is_active: int, push_time: str
    ) -> bool:
        """设置群聊所有领域的激活状态"""
        try:
            # 需要先获取所有 domain，通过 self.get_all_domains()
            # 这是一个 define 在 MetadataMixin 中的方法。
            # 由于最终 QuizRepository 继承所有 Mixin，这里应该能调得到。
            domains = self.get_all_domains()

            with self.get_locked_cursor() as _:
                for domain in domains:
                    # 批量操作时设置 commit=False，最后统一手动提交
                    self.upsert_group_task_config(
                        group_qq, domain["id"], push_time, is_active, commit=False
                    )

                self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set all domains active: {e}", exc_info=True)
            return False

    def deactivate_all_domains(self, group_qq: str) -> bool:
        """关闭群聊所有领域的推送"""
        try:
            with self.get_locked_cursor() as cursor:
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
            logger.error(f"Failed to deactivate all domains: {e}", exc_info=True)
            return False

    # ==================== Cursor & Batch 相关操作 ====================

    def get_group_domain_config(self, group_qq: str, domain_id: int) -> dict | None:
        """检查任务配置是否存在"""
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM group_task_config
                WHERE group_qq = ? AND domain_id = ?
            """,
                (group_qq, domain_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def init_group_domain_config(self, group_qq: str, domain_id: int, push_time: str = "17:00"):
        """初始化任务配置"""
        first_batch = self.get_first_batch(domain_id)
        initial_cursor = first_batch["start_index"] if first_batch else 1

        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO group_task_config
                (group_qq, domain_id, now_cursor, push_time, is_active)
                VALUES (?, ?, ?, ?, 1)
            """,
                (group_qq, domain_id, initial_cursor, push_time),
            )
            self.conn.commit()

        logger.info(
            f"Initialized cursor for group {group_qq}, domain {domain_id}, cursor={initial_cursor}"
        )

    def update_cursor(self, group_qq: str, domain_id: int, new_cursor: int) -> bool:
        """更新推送游标"""
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                UPDATE group_task_config
                SET now_cursor = ?
                WHERE group_qq = ? AND domain_id = ?
            """,
                (new_cursor, group_qq, domain_id),
            )

            if cursor.rowcount == 0:
                logger.error(
                    f"Failed to update cursor: no record found for group {group_qq}, domain {domain_id}"
                )
                self.conn.rollback()
                return False

            self.conn.commit()
            logger.info(
                f"Updated cursor to {new_cursor} for group {group_qq}, domain {domain_id}"
            )
            return True

    def get_cursor(self, group_qq: str, domain_id: int) -> int:
        """获取当前游标位置"""
        with self.get_locked_cursor() as cursor:
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

            first_batch = self.get_first_batch(domain_id)
            return first_batch["start_index"] if first_batch else 1

    def get_batch_by_start_index(self, domain_id: int, start_idx: int) -> dict | None:
        """根据 start_index 查找批次配置"""
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM domain_settings
                WHERE domain_id = ? AND start_index = ?
            """,
                (domain_id, start_idx),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_first_batch(self, domain_id: int) -> dict | None:
        """获取第一批配置"""
        with self.get_locked_cursor() as cursor:
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

    def get_next_batch(self, domain_id: int, current_start_idx: int) -> dict | None:
        """获取下一批配置"""
        with self.get_locked_cursor() as cursor:
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
            
    def get_all_batches(self, domain_id: int) -> list[dict]:
        """获取领域的所有批次配置"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM domain_settings
                WHERE domain_id = ?
                ORDER BY start_index ASC
            """, (domain_id,))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== Strategy Operations (v1.1.0) ====================

    def get_strategy_type(self, group_qq: str, domain_id: int) -> str:
        """获取群-领域的推送策略"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("""
                SELECT strategy_type FROM group_task_config
                WHERE group_qq = ? AND domain_id = ?
            """, (group_qq, domain_id))
            row = cursor.fetchone()
            return row['strategy_type'] if row else 'batch'

    def set_strategy_type(self, group_qq: str, domain_id: int, strategy_type: str) -> bool:
        """设置推送策略"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("""
                UPDATE group_task_config
                SET strategy_type = ?
                WHERE group_qq = ? AND domain_id = ?
            """, (strategy_type, group_qq, domain_id))
            self.conn.commit()
            return cursor.rowcount > 0

    def get_problem_push_counts(self, group_qq: str, problem_ids: list[int]) -> dict[int, int]:
        """批量获取题目推送次数"""
        if not problem_ids:
            return {}
        
        placeholders = ','.join('?' * len(problem_ids))
        args = [group_qq] + problem_ids
        with self.get_locked_cursor() as cursor:
            query = f"""
                SELECT problem_id, push_count 
                FROM problem_push_count
                WHERE group_qq = ? AND problem_id IN ({placeholders})
            """
            cursor.execute(query, args)
            return {row['problem_id']: row['push_count'] for row in cursor.fetchall()}

    def update_push_count(self, group_qq: str, problem_id: int):
        """更新题目推送计数 (+1)"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("""
                INSERT INTO problem_push_count (group_qq, problem_id, push_count, last_push_time)
                VALUES (?, ?, 1, datetime('now'))
                ON CONFLICT(group_qq, problem_id) 
                DO UPDATE SET 
                    push_count = push_count + 1, 
                    last_push_time = datetime('now')
            """, (group_qq, problem_id))
            self.conn.commit()

    def get_domain_stats(self, group_qq: str, domain_id: int) -> dict:
        """获取领域推送统计信息"""
        with self.get_locked_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_problems,
                    SUM(COALESCE(pc.push_count, 0)) as total_pushes,
                    AVG(COALESCE(pc.push_count, 0)) as avg_pushes,
                    MIN(COALESCE(pc.push_count, 0)) as min_pushes,
                    MAX(COALESCE(pc.push_count, 0)) as max_pushes
                FROM problems p
                LEFT JOIN problem_push_count pc 
                    ON p.id = pc.problem_id AND pc.group_qq = ?
                WHERE p.domain_id = ?
            """, (group_qq, domain_id))
            row = cursor.fetchone()
            return dict(row) if row else {}

    def reset_domain_progress(self, group_qq: str, domain_id: int, strategy_type: str):
        """重置领域进度"""
        with self.get_locked_cursor() as cursor:
            if strategy_type == 'counter':
                cursor.execute("""
                    DELETE FROM problem_push_count
                    WHERE group_qq = ? AND problem_id IN (
                        SELECT id FROM problems WHERE domain_id = ?
                    )
                """, (group_qq, domain_id))
            elif strategy_type == 'batch':
                # 重置游标到第一批
                cursor.execute("""
                    SELECT start_index FROM domain_settings
                    WHERE domain_id = ?
                    ORDER BY start_index ASC
                    LIMIT 1
                """, (domain_id,))
                row = cursor.fetchone()
                start_index = row['start_index'] if row else 1
                
                cursor.execute("""
                    UPDATE group_task_config
                    SET now_cursor = ?
                    WHERE group_qq = ? AND domain_id = ?
                """, (start_index, group_qq, domain_id))
            
            self.conn.commit()
