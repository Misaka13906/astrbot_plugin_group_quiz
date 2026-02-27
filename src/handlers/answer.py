import json
from typing import TYPE_CHECKING

from astrbot.api.event import AstrMessageEvent
from astrbot.core.star.filter.command import GreedyStr

from ..llm.judge import build_judge_prompt_a, build_judge_prompt_b

if TYPE_CHECKING:
    from ..repository import QuizRepository


class AnswerHandlers:
    """互动答题相关命令处理器"""

    db: "QuizRepository"

    async def cmd_submit_answer(
        self, event: AstrMessageEvent, problem_id: str, answer_parts: GreedyStr
    ):
        """提交回答：/a <题目ID> <你的回答>"""
        if not problem_id or not problem_id.isdigit():
            yield event.plain_result(
                "❌ 请提供有效的题目 ID，例如：/a 123 我的回答是..."
            )
            return

        user_answer = answer_parts.strip()
        if not user_answer:
            yield event.plain_result("❌ 请提供回答内容，例如：/a 123 我的回答是...")
            return

        if len(user_answer) < 5:
            yield event.plain_result("❌ 回答太短啦，至少得写几个字吧~")
            return

        pid = int(problem_id)
        problem = self.db.get_problem_by_id(pid)
        if not problem:
            yield event.plain_result(f"❌ 未找到题目 ID: {pid}")
            return

        user_qq = str(event.get_sender_id())
        group_qq = (
            str(event.message_obj.group_id)
            if getattr(event.message_obj, "group_id", None)
            else "private_" + user_qq
        )

        # Check if already answered recently (for base EXP rule)
        # 允许多次回答抢分，但基础经验同人同题一定天数内只给一次
        cooldown_days = self.config.get("exp_cooldown_days", 30)
        has_answered_recently = self.db.check_user_answered_recently(
            user_qq, pid, group_qq, days=cooldown_days
        )

        domain_name = problem.domain_name or "未知领域"
        question = problem.question or ""
        default_ans = problem.default_ans or ""
        max_score = problem.score or 10
        score_points_raw = problem.score_points

        has_score_points = False
        score_points = []
        if score_points_raw:
            try:
                score_points = json.loads(score_points_raw)
                if isinstance(score_points, list) and len(score_points) > 0:
                    has_score_points = True
            except Exception:
                pass

        if has_score_points:
            sys_p, user_p = build_judge_prompt_a(
                domain_name, question, score_points, user_answer
            )
        else:
            sys_p, user_p = build_judge_prompt_b(
                domain_name, question, default_ans, max_score, user_answer
            )

        # Call LLM
        # 优先使用用户在配置页选择的 provider
        llm_provider_id = self.config.get("llm_provider") if self.config else None
        prov = None

        if llm_provider_id and hasattr(self.context, "provider_manager"):
            prov = self.context.provider_manager.get_provider_by_id(llm_provider_id)

        # 如果未配或者找不到指定 provider，则降级使用消息源当前的 provider
        if not prov:
            prov = self.context.get_using_provider(event.unified_msg_origin)

        if not prov:
            yield event.plain_result("❌ 未找到可用的 LLM 提供商，无法评判回答。")
            return

        yield event.plain_result(f"🔍 正在仔细审阅你的回答 (ID: {pid})...")

        try:
            resp = await prov.text_chat(
                prompt=user_p,
                system_prompt=sys_p,
                temperature=0.3,  # Optional: Might not be supported directly by AstrBot text_chat config
            )
            llm_reply = resp.completion_text.strip()

            # extract JSON
            if "```json" in llm_reply:
                json_str = llm_reply.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_reply:
                json_str = llm_reply.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_reply

            judge_res = json.loads(json_str)
        except json.JSONDecodeError as e:
            yield event.plain_result(
                f"❌ 大模型反馈的结果解析失败，再试一次吧（JSON解析错误：{e}）"
            )
            return
        except Exception as e:
            yield event.plain_result(
                f"❌ 判题网络或者大模型接口开小差了，请稍后再试（请求错误：{e}）"
            )
            return

        ai_copied = judge_res.get("ai_copied", False)
        valid = judge_res.get("valid", False)
        llm_feedback = judge_res.get("feedback", "无评价")

        if ai_copied:
            self.db.record_user_answer(
                user_qq, pid, group_qq, user_answer, False, True, 0, llm_feedback, 0, 0
            )
            yield event.plain_result(
                f"👮 复制粘贴达咩！还是自己组织语言再试一次吧~\n点评：{llm_feedback}"
            )
            return

        if not valid:
            self.db.record_user_answer(
                user_qq, pid, group_qq, user_answer, False, False, 0, llm_feedback, 0, 0
            )
            yield event.plain_result(f"❌ 回答好像没有踩在点子上\n点评：{llm_feedback}")
            return

        # Valid answer, compute score
        user_add_score = 0.0
        exp_gained = 0
        if not has_answered_recently:
            base_exp = problem.base_exp or 5
            exp_gained = base_exp  # 冷却期外首次有效作答给所在的领域的基础经验
        covered_mask = 0

        progress = self.db.get_problem_score_progress(pid, group_qq)
        group_total = progress.total_score
        group_mask = progress.covered_mask
        is_complete = progress.is_complete

        points_str = ""

        if has_score_points:
            covered_indices = judge_res.get("covered_indices", [])
            hit_points = []

            for pt in score_points:
                idx = pt.get("idx")
                val = pt.get("score", 0)
                if idx in covered_indices:
                    covered_mask |= 1 << idx
                    hit_points.append(pt.get("point"))
                    if not (group_mask & (1 << idx)):
                        # 新知识点！
                        user_add_score += val

            # if user got any new points, give exp
            if user_add_score > 0:
                exp_gained += int(user_add_score)

            if hit_points:
                pts_list = "、".join(hit_points)
                points_str = f"覆盖要点：{pts_list}"
            else:
                points_str = "覆盖要点：无具体要点，但意思到了。"

        else:
            # 降级模式
            points_covered = min(
                float(judge_res.get("points_covered", 0.0)), float(max_score)
            )
            covered_mask = -1
            predicted_add = points_covered
            remaining = max(0.0, float(max_score) - group_total)
            user_add_score = min(predicted_add, remaining)

            if user_add_score > 0:
                exp_gained += int(user_add_score)

        # Update progress
        new_is_complete = is_complete or ((group_total + user_add_score) >= max_score)

        # Check if score pool is drawn
        if is_complete:
            yield event.plain_result(
                f"✅ 回答有效！\n点评：{llm_feedback}\n{points_str}\n\n太遗憾了，本题全群 {max_score} 分已被抢空~\n获得 {exp_gained} 经验值。"
            )
            self.db.record_user_answer(
                user_qq,
                pid,
                group_qq,
                user_answer,
                True,
                False,
                covered_mask,
                llm_feedback,
                exp_gained,
                0,
            )
            return

        self.db.update_problem_score_progress(
            pid,
            group_qq,
            user_add_score,
            covered_mask if covered_mask != -1 else 0,
            new_is_complete,
        )
        self.db.record_user_answer(
            user_qq,
            pid,
            group_qq,
            user_answer,
            True,
            False,
            covered_mask,
            llm_feedback,
            exp_gained,
            user_add_score,
        )

        bonus_msg = ""
        hint_msg = ""
        if new_is_complete and not is_complete:
            bonus_msg = "\n🎉 恭喜你给本题画上圆满句号！全群点亮了该题的所有知识树！"
        elif has_score_points and not new_is_complete:
            missing_hints = []
            current_mask = group_mask | covered_mask
            for pt in score_points:
                idx = pt.get("idx")
                if idx is not None and not (current_mask & (1 << idx)):
                    if pt.get("hint"):
                        missing_hints.append(pt["hint"])

            if missing_hints:
                hint_msg = f"\n💡 [ID: {pid}] 还有 {max_score - (group_total + user_add_score)} 分可以抢！回复 /h {pid} 获取下一考点提示~"

        yield event.plain_result(
            f"✅ 回答惊艳！\n点评：{llm_feedback}\n{points_str}\n\n💰 抢得 {user_add_score} 分！获得 {exp_gained} 经验值。{bonus_msg}{hint_msg}"
        )

    async def cmd_get_answer(self, event: AstrMessageEvent, problem_id: str):
        """获取指定题目的参考答案"""
        if not problem_id or not problem_id.isdigit():
            yield event.plain_result("❌ 请提供有效的题目 ID，例如：/ans 123")
            return

        pid = int(problem_id)
        problem = self.db.get_problem_by_id(pid)

        if not problem:
            yield event.plain_result(f"❌ 未找到题目 ID: {problem_id}")
            return

        # 答案保护逻辑
        group_qq = str(event.get_group_id()) if event.get_group_id() else None
        if group_qq:
            from datetime import datetime

            today = datetime.now().strftime("%Y-%m-%d")

            is_admin = event.is_admin()
            progress = self.db.get_problem_score_progress(pid, group_qq)
            is_completed = progress.is_complete

            last_push_date = None
            with self.db.get_locked_cursor() as cursor:
                cursor.execute(
                    "SELECT last_push_time FROM problem_push_count WHERE group_qq = ? AND problem_id = ?",
                    (group_qq, pid),
                )
                row = cursor.fetchone()
                if row and row["last_push_time"]:
                    last_push_date = row["last_push_time"][:10]

            is_active_today = (last_push_date == today) or (
                progress.total_score > 0 or progress.covered_mask > 0
            )
            has_been_pushed = last_push_date is not None

            can_view = (
                is_admin or is_completed or (not is_active_today and has_been_pushed)
            )

            if not can_view:
                max_score = problem.score or 10
                remain = max_score - progress.total_score
                yield event.plain_result(
                    f"⚠️ 本题还剩 {remain} 分未被发掘，多看看提示再抢答一波吧！（或者等明天/下轮出新题后再来查看答案~）"
                )
                return

        # 根据 use_ans 字段决定返回哪个答案
        use_ans = problem.use_ans or "default"
        answer = problem.default_ans or ""
        if use_ans == "llm":
            answer = problem.llm_ans or ""
        elif use_ans == "web":
            answer = problem.web_ans or ""

        if not answer and use_ans != "none":
            yield event.plain_result(f"📋 题目 ID: {problem_id}\n该题目暂无参考答案")
            return

        result_lines = [
            f"📋 [题目 ID {problem_id}]",
            "【参考答案原文】",
            answer if answer else "(暂无)",
        ]

        # 解析并展示 score_points
        score_points_raw = problem.score_points
        if score_points_raw:
            try:
                score_points = json.loads(score_points_raw)
                if isinstance(score_points, list) and len(score_points) > 0:
                    result_lines.append("\n【评分点分布】")
                    for i, pt in enumerate(score_points, 1):
                        point_text = pt.get("point", "未知考点")
                        score_val = pt.get("score", 0)
                        result_lines.append(f"🎯 {i}. {point_text}: {score_val} 分")
            except Exception:
                pass

        try:
            from ..utils import build_mixed_message

            yield build_mixed_message("\n".join(result_lines), event.make_result())
        except ImportError:
            yield event.plain_result("\n".join(result_lines))

    async def cmd_get_hint(self, event: AstrMessageEvent, problem_id: str):
        """获取指定题目的下一考点提示"""
        group_qq = str(event.get_group_id()) if event.get_group_id() else None
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        if not problem_id or not problem_id.isdigit():
            yield event.plain_result("❌ 请提供有效的题目 ID，例如：/h 123")
            return

        pid = int(problem_id)
        problem = self.db.get_problem_by_id(pid)
        if not problem:
            yield event.plain_result(f"❌ 未找到题目 ID: {problem_id}")
            return

        score_points_raw = problem.score_points
        if not score_points_raw:
            yield event.plain_result(
                f"❌ 题目 ID: {problem_id} 是一道综合题，没有具体考点可供提示。"
            )
            return

        progress = self.db.get_problem_score_progress(pid, group_qq)
        is_completed = progress.is_complete
        if is_completed:
            yield event.plain_result(
                f"✅ 题目 ID: {problem_id} 已经被全群满分通关啦，回复 /ans {problem_id} 即可查看完整参考答案！"
            )
            return

        group_mask = progress.covered_mask

        missing_hints = []
        try:
            score_points = json.loads(score_points_raw)
            score_points.sort(key=lambda x: x.get("idx", 0))
            for pt in score_points:
                idx = pt.get("idx")
                if idx is not None and not (group_mask & (1 << idx)):
                    if pt.get("hint"):
                        missing_hints.append((idx + 1, pt["hint"]))
        except Exception:
            pass

        if not missing_hints:
            yield event.plain_result(f"❌ 题目 ID: {problem_id} 暂无未解锁的线索。")
            return

        step_idx, chosen_hint = missing_hints[0]
        yield event.plain_result(
            f"💡 [ID: {problem_id}] (考点 {step_idx}) 提示：\n{chosen_hint}"
        )
