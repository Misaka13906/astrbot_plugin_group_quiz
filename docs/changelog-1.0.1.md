# Changelog - v1.0.1

## [1.0.1] - 2026-02-14

### Fixed - Critical Bugs

**核心修复（必须升级）**：

- **周默认配置 cursor 初始化缺失** ⭐ 严重问题
  - 修复使用周配置的群无法正确跟踪推送进度的严重问题
  - 现在加载周任务时会自动检查并初始化 cursor 记录
  - 影响：使用 `use_default` 配置的所有群

- **手动配置 cursor 初始化缺失**
  - 修复手动配置群首次推送时 cursor 未初始化的问题
  - `upsert_group_task_config` 现在会在 INSERT 时自动初始化 cursor 为第一批 `start_index`
  - 影响：所有通过 `/task on <domain> <time>` 配置的群

- **数据库唯一约束缺失**
  - 添加 `UNIQUE(group_qq, domain_id)` 约束，防止重复记录
  - 自动去除现有重复记录（如有）
  - 影响：数据完整性

- **时间格式解析缺失验证**
  - 修复 `scheduler` 加载任务时直接解析时间导致的潜在崩溃风险
  - 现在使用 `datetime.strptime` 严格验证时间格式（HH:MM）和数值范围
  - 遇到无效时间格式（如 "25:00" 或 "abc"）时记录错误日志并跳过该任务，保障插件主进程不崩溃
  - 影响：插件稳定性，防止因配置文件错误或数据库脏数据导致无法启动

- **cursor 更新检查缺失**
  - `update_cursor` 现在会检查更新是否成功（`rowcount`）
  - 更新失败时记录详细错误日志
  - 影响：推送进度跟踪可靠性

- **手动任务加载失败回归** ⭐ 关键修复
  - 修复了由于缩进错误导致手动配置的推送任务无法正确加载到调度器的严重回归 Bug
  - 修复了 `/task on` 配置单个领域后因未重载调度器而需要重启才能生效的问题
  - 修复了 `scheduler` 在重载手动任务时错误排除当前群，导致新配置失效的逻辑 Bug
  - 确保 `/task on {domain} {time}` 配置在插件启动或修改后立即可用

- **推送静默失败修复**
  - 修复了 scheduler 使用错误的协议类型 (`GroupMessage`) 导致部分平台（如 OneBot）无法发出群消息且无报错的问题
  - 优化了平台 ID 识别逻辑，提高多平台环境下的兼容性
  - 增加了详细的推送流程日志，现在因配置缺失（如空题库、无对应群组）导致的跳过操作会有明确的 `Warning` 日志

---

### Fixed - Code Quality & Stability

**并发安全性 (Thread Safety)**:
- **引入数据库锁机制** ⭐ 核心改进
  - 在 `QuizDatabase` 中引入 `threading.RLock` 并使用 `get_locked_cursor` 上下文管理器
  - 确保在多线程环境下（定时调度与指令回复并存）数据库连接的安全重入与并发排他
  - 彻底解决高负载下潜在的 `database is locked` 错误和数据损坏风险

**指令解析鲁棒性 (Robust Parsing)**:
- **采用 shlex 增强参数拆分**
  - 使用 `shlex.split()` 替代原有的 `.split()` 解析指令参数
  - 完美支持包含空格且使用引号包裹的领域名称（如 `/task on "Java Core" 17:00`）
  - 增加了对解析异常（如括号/引号不匹配）的稳健处理

**初始化健壮性 (Hardened Initialization)**:
- **增强数据库状态验证**
  - 在插件启动时增加对关键表（如 `problems`）的存在性校验
  - 即使数据库文件存在且非空，若结构损坏或缺失表，将自动触发 Schema 重刷
  - 解决了因异常中断产生损坏数据文件后插件无法正常运行的问题

**配置管理与事务优化**:
- DummyConfig 现在会在保存时抛出明确异常，避免误导用户
- 统一群号类型为字符串，避免配置失效问题
- 修复 `use_default` 配置可能无法保存的问题
- 通过指令更改配置后立即生效，无需重启插件
- 优化了 `set_all_domains_active` 的事务处理，修复了循环内冗余提交问题

**代码质量与可维护性 (Refactoring)**:
- **应用 Error-First 模式**: 重构了 `cmd_list_task` 等指令处理逻辑，采用“尽早返回”原则减少嵌套，大幅提升代码可读性
- **消除冗余抽象**: 移除了重复封装的 `_get_group_id`，改为直接调用 AstrBot 原生 API
- **指令注册转发器**: 引入 `_delegate_to_cmd_handler` 通用方法，统一对 cmd_handler 未准备好时的处理
- **Pathlib 现代化**: `main.py` 全面迁移至 `pathlib.Path` 处理路径和目录，代码更具 Pythonic 范式
- **日志记录标准化**: 统一使用 `exc_info=True` 捕获完整异常堆栈，提供比手动格式化更精确的调试信息
- 推送批次大小支持通过数据库 `domain.default_batch_size` 配置（默认为 3）
- 补全了核心业务逻辑的异常堆栈日志 (`exc_info=True`)
---

### Changed

**数据库 Schema 更新**：
- `group_task_config` 表添加 `UNIQUE(group_qq, domain_id)` 约束
- 自动去除重复数据
- 无需手动迁移，只需重启插件（schema.sql 会自动应用）
- 添加 `default_batch_size` 字段，用于配置推送批次大小

---

### Added

**产品功能**：
- 新增 `/prob <题号>` 命令，支持直接查询指定题目的完整题面内容
- 新增 `/search <关键词>` 命令，支持模糊搜索题目
- 新增 `/pushnow <domain>` 调试命令，允许管理员立即触发一次指定领域的推送，方便快速排查发送问题
- `/ltask` 命令改进：使用周默认配置时，在底部去重显示每个领域的当前进度（例如 `📊 当前进度：\n- Java: 第10题`）；使用手动配置时直接在领域后显示当前进度

**用户体验**：
- 优化 `/task off all` 逻辑：现在作为一键总开关，不仅关闭手动配置的任务，也会自动将该群从“周推送模式”列表中移除，无需先手动切换模式
- 改进 `/rand` 命令的错误提示，当领域不存在时引导使用 `/ldomain`
- `/addme` 和 `/rmme` 命令在操作失败时会显示当前可用的小组列表建议

---

##  迁移指南

### 从 v1.0.0 升级到 v1.0.1

执行 `ALTER TABLE group_task_config ADD COLUMN default_batch_size INT DEFAULT 3;` 并重启插件即可，会自动执行 schema.sql 中的 sql 语句。

> 注意：如果您的数据库中已存在大量重复数据，建议手动清理或使用 SQLite 工具执行 `DELETE FROM group_task_config WHERE id NOT IN (SELECT MIN(id) FROM group_task_config GROUP BY group_qq, domain_id)`。

---

### 新安装用户

无需任何额外操作，直接使用即可（schema.sql 已更新）。

---

## 已知问题

无

---

## 致谢

感谢所有测试用户的反馈！

---

## 相关链接

- [问题反馈](https://github.com/Misaka13906/astrbot_plugin_group_quiz/issues)
