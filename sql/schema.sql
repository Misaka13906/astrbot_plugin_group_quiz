-- SQLite Schema for Group Quiz Plugin
-- 启用外键约束
PRAGMA foreign_keys = ON;

-- 学习小组
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

-- 学习领域
CREATE TABLE IF NOT EXISTS domain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    group_id INTEGER,
    default_batch_size INTEGER DEFAULT 3,
    total_score INTEGER DEFAULT 0,
    FOREIGN KEY (group_id) REFERENCES groups(id)
);

-- 领域设置（用于控制每次推送题目的范围，闭区间表示法）
CREATE TABLE IF NOT EXISTS domain_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL,
    start_index INTEGER DEFAULT 1,
    end_index INTEGER DEFAULT 1,
    FOREIGN KEY (domain_id) REFERENCES domain(id)
);

-- 题库
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER,
    category TEXT,  -- 如 TCP/IP, HTTP, 进程管理等主题
    topic TEXT,     -- 小主题
    question TEXT,
    default_ans TEXT,
    llm_ans TEXT,
    use_ans TEXT DEFAULT 'default' CHECK(use_ans IN ('default', 'llm', 'none')),
    score INTEGER DEFAULT 10,
    FOREIGN KEY (domain_id) REFERENCES domain(id)
);

-- 为 problems 表创建索引
CREATE INDEX IF NOT EXISTS idx_problems_category ON problems(category);
CREATE INDEX IF NOT EXISTS idx_problems_topic ON problems(topic);

-- 每个群的八股任务配置（注意这是QQ群不是学习小组）
CREATE TABLE IF NOT EXISTS group_task_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_qq TEXT NOT NULL,
    domain_id INTEGER NOT NULL,
    push_time TEXT DEFAULT '17:00',  -- 格式：17:30 或 09:00
    is_active INTEGER DEFAULT 0,     -- SQLite 使用 INTEGER 表示 boolean (0/1)
    now_cursor INTEGER DEFAULT 0,    -- 该领域下一系列推送题的起始索引位置
    FOREIGN KEY (domain_id) REFERENCES domain(id)
);

-- ✅ v1.0.1 修复：使用唯一索引防止重复记录
CREATE UNIQUE INDEX IF NOT EXISTS idx_group_task_unique ON group_task_config(group_qq, domain_id);

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    qq TEXT PRIMARY KEY,
    username TEXT UNIQUE
);

-- 用于存储当前加入状态（用户订阅的学习小组）
CREATE TABLE IF NOT EXISTS subscribes (
    user_qq TEXT NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY (user_qq, group_id),
    FOREIGN KEY (user_qq) REFERENCES users(qq),
    FOREIGN KEY (group_id) REFERENCES groups(id)
);
