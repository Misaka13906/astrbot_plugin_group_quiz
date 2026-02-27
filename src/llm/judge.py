"""
judge.py - LLM 判题逻辑，负责拼 prompt、调 API、解析结果
"""

from .prompts import (
    JUDGE_SYSTEM_A,
    JUDGE_SYSTEM_B,
    JUDGE_USER_A,
    JUDGE_USER_B,
)


def _fmt_score_points(score_points: list[dict]) -> str:
    """将 score_points 列表格式化为 prompt 内嵌文本"""
    lines = []
    for sp in score_points:
        lines.append(f"  [{sp['idx']}] {sp['point']}（{sp['score']} 分）")
    return "\n".join(lines)


def build_judge_prompt_a(
    domain: str,
    question: str,
    score_points: list[dict],
    user_answer: str,
) -> tuple[str, str]:
    """
    精确评分模式（有 score_points）。
    返回 (system_prompt, user_prompt)
    """
    user = JUDGE_USER_A.format(
        domain=domain,
        question=question,
        score_points_text=_fmt_score_points(score_points),
        user_answer=user_answer,
    )
    return JUDGE_SYSTEM_A, user


def build_judge_prompt_b(
    domain: str,
    question: str,
    default_ans: str,
    max_score: int,
    user_answer: str,
) -> tuple[str, str]:
    """
    降级综合打分模式（无 score_points）。
    返回 (system_prompt, user_prompt)
    """
    user = JUDGE_USER_B.format(
        domain=domain,
        question=question,
        default_ans=default_ans,
        max_score=max_score,
        user_answer=user_answer,
    )
    return JUDGE_SYSTEM_B, user
