-- SQLite Schema for Group Quiz Plugin
-- 启用外键约束
PRAGMA foreign_keys = ON;

-- 学习小组
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- 学习领域
CREATE TABLE IF NOT EXISTS domain (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    group_id INTEGER,
    default_batch_size INTEGER DEFAULT 3,
    total_score INTEGER DEFAULT 0,
    base_exp INTEGER DEFAULT 5,
    FOREIGN KEY (group_id) REFERENCES groups(id)
);

-- 分类
CREATE TABLE IF NOT EXISTS category (
    id INTEGER PRIMARY KEY,
    domain_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (domain_id) REFERENCES domain(id),
    UNIQUE(domain_id, name)
);

-- 领域设置（用于控制每次推送题目的范围，闭区间表示法）
CREATE TABLE IF NOT EXISTS domain_settings (
    id INTEGER PRIMARY KEY,
    domain_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL, -- 类别外键，配合 json_id 确定批次范围
    start_index INTEGER DEFAULT 1, -- 对应问题的 json_id 下限
    end_index INTEGER DEFAULT 1, -- 对应问题的 json_id 上限
    FOREIGN KEY (domain_id) REFERENCES domain(id),
    FOREIGN KEY (category_id) REFERENCES category(id),
    UNIQUE(domain_id, category_id, start_index, end_index)
);

-- 题库
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY,
    domain_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,  -- 类别关联
    topic TEXT,     -- 小主题
    json_id INTEGER NOT NULL, -- 数据源 JSON 中的原始 ID，方便热更新比对
    question TEXT NOT NULL,
    default_ans TEXT NOT NULL, -- 默认答案，如果没有别的需求则只填这个
    llm_ans TEXT,
    web_ans TEXT,
    use_ans TEXT DEFAULT 'default' CHECK(use_ans IN ('default', 'llm', 'web')),
    score INTEGER DEFAULT 10, -- 满分
    -- v2.0.0: 知识点评分表（JSON）。格式：[{"idx": N, "point": "...", "hint": "...", "score": N}, ...]，总和应为满分
    -- idx 显式存储，不依赖数组位置。如果为 NULL，评分时降级为 LLM 直接打 0-满分 综合分
    score_points TEXT DEFAULT NULL,
    FOREIGN KEY (domain_id) REFERENCES domain(id),
    FOREIGN KEY (category_id) REFERENCES category(id),
    UNIQUE(category_id, json_id)
);

-- 为 problems 表创建索引
CREATE INDEX IF NOT EXISTS idx_problems_topic ON problems(topic);

-- 每个群的八股任务配置（注意这是QQ群不是学习小组）
CREATE TABLE IF NOT EXISTS group_task_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_qq TEXT NOT NULL,
    domain_id INTEGER NOT NULL,
    push_time TEXT DEFAULT '12:00',  -- 格式：17:30 或 09:00
    is_active INTEGER DEFAULT 0,     -- SQLite 使用 INTEGER 表示 boolean (0/1)
    now_category_id INTEGER NOT NULL,  -- 当前正在推送的分类ID
    now_cursor INTEGER DEFAULT 0,    -- 此时起着 json_id / start_index 的作用
    strategy_type TEXT DEFAULT 'batch' CHECK(strategy_type IN ('counter', 'batch', 'daterem')),
    FOREIGN KEY (domain_id) REFERENCES domain(id),
    FOREIGN KEY (now_category_id) REFERENCES category(id)
    -- ✅ v1.0.1 修复：使用唯一索引防止重复记录
    UNIQUE(group_qq, domain_id)
);

-- v1.1.0 新增表：题目推送计数
CREATE TABLE IF NOT EXISTS problem_push_count (
    id INTEGER PRIMARY KEY,
    group_qq TEXT NOT NULL,
    problem_id INTEGER NOT NULL,
    push_count INTEGER DEFAULT 0,
    last_push_time DATETIME,
    UNIQUE(group_qq, problem_id),
    FOREIGN KEY (problem_id) REFERENCES problems(id)
);

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    qq TEXT PRIMARY KEY,
    username TEXT UNIQUE
);

-- 用户订阅的学习小组
CREATE TABLE IF NOT EXISTS subscribes (
    id INTEGER PRIMARY KEY,
    user_qq TEXT NOT NULL,
    group_id INTEGER NOT NULL,
    UNIQUE(user_qq, group_id),
    FOREIGN KEY (user_qq) REFERENCES users(qq),
    FOREIGN KEY (group_id) REFERENCES groups(id)
);

-- ========== v2.0.0 新增 ==========

-- 用户答题记录
CREATE TABLE IF NOT EXISTS user_answer_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_qq TEXT NOT NULL,
    problem_id INTEGER NOT NULL,
    group_qq TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    is_valid INTEGER DEFAULT 0,         -- LLM 判定是否有效
    ai_copied INTEGER DEFAULT 0,        -- LLM 判定是否 AI 复制
    -- 覆盖位掉码：第 i 位为 1 表示覆盖了 score_points[i] 知识点
    -- 降级模式（无 score_points）下为 -1
    covered_mask INTEGER DEFAULT 0,
    llm_feedback TEXT,                  -- LLM 点评
    exp_gained INTEGER DEFAULT 0,
    score_gained REAL DEFAULT 0,        -- 实际发放的 Score
    answer_date TEXT NOT NULL,          -- YYYY-MM-DD，用于同天去重（如果需要的话，按最新业务不需要严格唯一）
    answered_at DATETIME DEFAULT (datetime('now'))
);

-- 题目每轮推送的得分进度
CREATE TABLE IF NOT EXISTS problem_score_log (
    id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL,
    group_qq TEXT NOT NULL,
    push_date TEXT NOT NULL,            -- YYYY-MM-DD，与推送当天对齐
    total_score REAL DEFAULT 0,         -- 本轮已累计发出的总 Score（0-10）
    -- 覆盖位掉码：所有回答者已覆盖知识点的并集
    -- 新回答进来用 (llm_mask & ~covered_mask) 得到新增部分
    covered_mask INTEGER DEFAULT 0,
    is_complete INTEGER DEFAULT 0,      -- 本轮是否已满分
    UNIQUE(problem_id, group_qq, push_date)
);

CREATE INDEX IF NOT EXISTS idx_answer_log_date ON user_answer_log(user_qq, problem_id, group_qq, answer_date);
