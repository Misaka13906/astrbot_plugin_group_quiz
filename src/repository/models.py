from dataclasses import dataclass


@dataclass
class Group:
    id: int
    name: str


@dataclass
class Domain:
    id: int
    name: str
    group_id: int
    default_batch_size: int = 3
    total_score: int = 0
    base_exp: int = 5


@dataclass
class Category:
    id: int
    domain_id: int
    name: str


@dataclass
class DomainSetting:
    id: int
    domain_id: int
    category_id: int
    start_index: int = 1
    end_index: int = 1


@dataclass
class Problem:
    id: int
    domain_id: int
    category_id: int
    json_id: int
    question: str
    default_ans: str
    topic: str | None = None
    llm_ans: str | None = None
    web_ans: str | None = None
    use_ans: str = "default"
    score: int = 10
    score_points: str | None = None
    domain_name: str | None = None  # Used in queries that join with domain table
    category_name: str | None = None  # Used in queries that join with category table
    current_count: int | None = (
        None  # Used in queries that join with problem_push_count
    )
    base_exp: int | None = None  # Used in queries that join with domain table


@dataclass
class GroupTaskConfig:
    id: int
    group_qq: str
    domain_id: int
    now_category_id: int
    push_time: str = "12:00"
    is_active: bool = False
    now_cursor: int = 0
    strategy_type: str = "batch"
    domain_name: str | None = None  # Used in queries that join with domain table


@dataclass
class ProblemPushCount:
    group_qq: str
    problem_id: int
    id: int = 0
    push_count: int = 0
    last_push_time: str | None = None


@dataclass
class User:
    qq: str
    username: str | None = None


@dataclass
class Subscribe:
    user_qq: str
    group_id: int
    id: int = 0


@dataclass
class UserAnswerLog:
    id: int
    user_qq: str
    problem_id: int
    group_qq: str
    answer_text: str
    is_valid: bool = False
    ai_copied: bool = False
    covered_mask: int = 0
    llm_feedback: str | None = None
    exp_gained: int = 0
    score_gained: float = 0.0
    answer_date: str = ""
    answered_at: str = ""


@dataclass
class ProblemScoreLog:
    problem_id: int
    group_qq: str
    push_date: str
    id: int = 0
    total_score: float = 0.0
    covered_mask: int = 0
    is_complete: bool = False
