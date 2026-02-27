from datetime import datetime

from .models import ProblemScoreLog


class AnswerMixin:
    """答题记录与进度相关操作"""

    def check_user_answered_recently(
        self, user_qq: str, problem_id: int, group_qq: str, days: int = 30
    ) -> bool:
        """检查用户近期（默认 30 天）内是否已经**有效**回答过该题，避免刷经验"""
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM user_answer_log
                WHERE user_qq = ? AND problem_id = ? AND group_qq = ?
                AND answer_date >= date('now', ?) AND is_valid = 1
                """,
                (user_qq, problem_id, group_qq, f"-{days} days"),
            )
            return cursor.fetchone() is not None

    def record_user_answer(
        self,
        user_qq: str,
        problem_id: int,
        group_qq: str,
        answer_text: str,
        is_valid: bool,
        ai_copied: bool,
        covered_mask: int,
        llm_feedback: str,
        exp_gained: int,
        score_gained: float,
    ) -> int:
        """记录用户回答，返回插入的行 ID"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_answer_log
                (user_qq, problem_id, group_qq, answer_text, is_valid, ai_copied,
                 covered_mask, llm_feedback, exp_gained, score_gained, answer_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_qq,
                    problem_id,
                    group_qq,
                    answer_text,
                    1 if is_valid else 0,
                    1 if ai_copied else 0,
                    covered_mask,
                    llm_feedback,
                    exp_gained,
                    score_gained,
                    today,
                ),
            )
            return cursor.lastrowid

    def get_problem_score_progress(
        self, problem_id: int, group_qq: str
    ) -> ProblemScoreLog:
        """获取题目当天的全群进度"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                SELECT problem_id, group_qq, push_date, total_score, covered_mask, is_complete
                FROM problem_score_log
                WHERE problem_id = ? AND group_qq = ? AND push_date = ?
                """,
                (problem_id, group_qq, today),
            )
            row = cursor.fetchone()
            if row:
                return ProblemScoreLog(**dict(row))
            return ProblemScoreLog(
                problem_id=problem_id,
                group_qq=group_qq,
                push_date=today,
                total_score=0.0,
                covered_mask=0,
                is_complete=False,
            )

    def update_problem_score_progress(
        self,
        problem_id: int,
        group_qq: str,
        add_score: float,
        new_mask: int,
        is_complete: bool,
    ):
        """更新题目当天的全群进度"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self.get_locked_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM problem_score_log
                WHERE problem_id = ? AND group_qq = ? AND push_date = ?
                """,
                (problem_id, group_qq, today),
            )
            row = cursor.fetchone()
            if row:
                log = ProblemScoreLog(**dict(row))
                total_score = log.total_score + add_score
                covered_mask = log.covered_mask | new_mask
                cursor.execute(
                    """
                    UPDATE problem_score_log
                    SET total_score = ?, covered_mask = ?, is_complete = ?
                    WHERE problem_id = ? AND group_qq = ? AND push_date = ?
                    """,
                    (
                        total_score,
                        covered_mask,
                        1 if is_complete else 0,
                        problem_id,
                        group_qq,
                        today,
                    ),
                )
            else:
                total_score = add_score
                covered_mask = new_mask
                cursor.execute(
                    """
                    INSERT INTO problem_score_log
                    (problem_id, group_qq, push_date, total_score, covered_mask, is_complete)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        problem_id,
                        group_qq,
                        today,
                        total_score,
                        covered_mask,
                        1 if is_complete else 0,
                    ),
                )

    def get_user_score_stats(self, user_qq: str) -> dict:
        """获取用户当前的总经验和总积分（包含分领域统计）"""
        with self.get_locked_cursor() as cursor:
            # Overall stats
            cursor.execute(
                """
                SELECT SUM(exp_gained) as total_exp, SUM(score_gained) as total_score
                FROM user_answer_log
                WHERE user_qq = ?
                """,
                (user_qq,),
            )
            overall = cursor.fetchone()

            # Per-domain stats
            cursor.execute(
                """
                SELECT
                    d.name AS domain_name,
                    d.total_score AS domain_total_score,
                    SUM(u.exp_gained) AS total_exp,
                    SUM(u.score_gained) AS total_score
                FROM user_answer_log u
                JOIN problems p ON u.problem_id = p.id
                JOIN domain d ON p.domain_id = d.id
                WHERE u.user_qq = ?
                GROUP BY d.id, d.name, d.total_score
                HAVING total_exp > 0 OR total_score > 0
                ORDER BY total_score DESC, total_exp DESC
                """,
                (user_qq,),
            )
            domains = [dict(row) for row in cursor.fetchall()]

            return {
                "exp": int(overall["total_exp"] or 0),
                "score": round(overall["total_score"] or 0, 1),
                "domains": domains,
            }

    def get_group_rank(
        self, group_qq: str, domain_id: int = None, limit: int = 10
    ) -> list:
        """获取本群按积分排名的榜单（可指定领域）"""
        query = """
            SELECT u.user_qq, SUM(u.score_gained) as total_score, SUM(u.exp_gained) as total_exp
            FROM user_answer_log u
        """
        params = [group_qq]

        if domain_id is not None:
            query += " JOIN problems p ON u.problem_id = p.id WHERE u.group_qq = ? AND p.domain_id = ?"
            params.append(domain_id)
        else:
            query += " WHERE u.group_qq = ?"

        query += """
            GROUP BY u.user_qq
            HAVING total_score > 0 OR total_exp > 0
            ORDER BY total_score DESC, total_exp DESC
            LIMIT ?
        """
        params.append(limit)

        with self.get_locked_cursor() as cursor:
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
