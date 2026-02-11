📘 第一版 产品 & 设计文档

版本：V1.0.0

### 产品概述
一个轻量级的题目推送插件。本版本不设对错判定，只做 “点名-推送-查阅” 的闭环，依靠群友讨论。

### 功能范围 (Scope)
- 小组管理：查询可用小组、加入/退出小组。
- 定时推送：管理员可开启/关闭的定时推送题目的任务，该推送消息会定向艾特小组成员。
- 查阅功能：根据题目 ID 或关键词快速获取参考答案。
- 基础存储：使用 SQLite 持久化存储静态题库和动态成员关系。

### 指令集 (Commands)
   | 指令      | 权限 | 逻辑 |
   |-----------|-----|------|
   | /lhelp    |所有人| 列出所有可用指令和简要说明|
   | /lgroup   |所有人| 查询 groups 表，列出所有可加入的小组名|
   | /ldomain  |所有人| 查询 domains 表，列出所有可查看的领域名|
   | /mygroup  |所有人| 查询 subscribe 表，列出当前用户已加入的小组名|
   | /ltask    |所有人| 查看本群当前的题目推送状态|
   | /addme {group_name} |所有人| 在 subscribe 中建立当前用户与小组的关联|
   | /rmme {group_name}  |所有人| 删除 subscribe 中的关联记录|
   | /ans {problem_id}   |所有人| 根据 problem_id 查询并返回 default_ans|
   | /rand {domain_name} |所有人| 随机抽取一道该领域的题目，手动触发|
   | /task on/off {domain_name}/all/default {hour:min} |管理员| 切换插件在本群是否推送某领域|

### 技术设计
#### 技术使用
代码使用Python实现，注意使用 astrbot api，以便集成到 AstrBot 中。注意代码风格和结构符合 AstrBot 插件规范。某一步失败时，需在日志中打出清晰的错误信息，方便排查。
#### 数据库
实现直接使用 sqlite3。虽然表结构较多，但 本阶段仅重点实现本文档中描述的功能，不要在意预留未来的字段。
初始化逻辑：插件启动时，检查 .db 文件是否存在，若不存在则执行提供的建表 SQL，并打log提示文件不存在。
数据行由我人工导入，不需要写这一部分。

schema.sql 中包含了完整的表结构定义。

#### 定时任务模块
利用 AstrBot 内置定时逻辑。
配置分为周推送默认配置和手动群聊配置两部分。

##### 周推送默认配置
周推送配置：定义每周几推送哪些领域的题目。
请使用 astrbot 提供的插件配置加载器，不要擅自读取。

代码示例：
```python
def get_week_config(self, day: string):  
    """获取指定星期的配置"""  
    if day in self.config.get("settings", {}):  
        return self.config["settings"][day]
    return None  
  
# 使用示例  
monday_config = self.get_week_config("星期一")  
if monday_config:  
    time = monday_config.get("time", "")  
    domains = monday_config.get("domains", [])
```

use_default 列表：如果某个群聊 QQ 号在该列表中，则表示该群使用默认配置进行推送，否则按照手动配置规则进行推送。如果某一天没有配置任何领域，则表示该天不进行推送。

##### 群聊手动配置
配置表：group_task_config，记录每个群聊的推送配置。
   字段说明：
   - group_qq：群聊 QQ 号，主键。
   - domain_id：领域 ID，指向 domain 表。如果为 NULL 则表示关闭该群的所有领域推送。
   - per_day：每天推送多少道题目，默认3道。本阶段暂时不使用该字段。
   - push_time：推送时间。 格式为 "HH:MM"，24小时制。注意检查格式合法性。
   - is_active：是否开启该领域的推送，0 代表关闭，1 代表开启。
   - now_cursor：该群该领域下一次推送的批次起始位置，存储的是 `domain_settings.start_index` 的值。

##### 游标推送系统 (Cursor-based Push System)

**核心概念**：

插件使用基于批次的游标系统来跟踪每个群的推送进度，实现顺序、不重复的题目推送。

**批次配置表：domain_settings**

每个领域可以配置多个批次，每个批次定义一个题目范围：

```sql
CREATE TABLE domain_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL,           -- 领域 ID
    start_index INTEGER DEFAULT 1,        -- 批次起始题目 ID（闭区间）
    end_index INTEGER DEFAULT 1,          -- 批次结束题目 ID（闭区间）
    FOREIGN KEY (domain_id) REFERENCES domain(id)
);
```

**配置示例**：

```sql
-- Java 领域分 3 批推送
INSERT INTO domain_settings (domain_id, start_index, end_index) VALUES
(1, 1, 10),   -- 批次1: 推送题目 ID 1-10
(1, 11, 20),  -- 批次2: 推送题目 ID 11-20
(1, 21, 30);  -- 批次3: 推送题目 ID 21-30
```

**now_cursor 字段说明**：

- **含义**：`now_cursor` 存储的是**当前批次的 start_index**，而非题目 ID
- **初始值**：
  - `0`：未初始化，首次推送时会自动查找第一批的 start_index
  - 非零值：直接使用该值作为当前批次的起点
- **更新逻辑**：
  1. 推送前：根据 `now_cursor` 在 `domain_settings` 中查找对应批次
  2. 推送时：获取该批次 `[start_index, end_index]` 范围内的所有题目
  3. 推送后：查找下一批次的 `start_index` 并更新 `now_cursor`
  4. 循环：推完所有批次后，自动回到第一批的 `start_index`

**配置示例**：

```sql
-- 群 123456 的 Java 领域配置
-- 假设 Java 第一批 start_index = 1
INSERT INTO group_task_config (group_qq, domain_id, push_time, is_active, now_cursor) VALUES
('123456', 1, '17:00', 1, 1);  -- cursor=1 表示从第一批开始

-- 假设 Golang 第一批 start_index = 50
INSERT INTO group_task_config (group_qq, domain_id, push_time, is_active, now_cursor) VALUES
('123456', 3, '18:00', 1, 50);  -- cursor=50 表示从 start_index=50 的批次开始
```

**推送进度示例**：

| 推送次数 | now_cursor | 查找批次 | 推送题目 | 更新后 cursor |
|---------|-----------|---------|---------|--------------|
| 第 1 次 | 1         | [1-10]  | ID 1-10 | 11           |
| 第 2 次 | 11        | [11-20] | ID 11-20| 21           |
| 第 3 次 | 21        | [21-30] | ID 21-30| 1 (循环)     |
| 第 4 次 | 1         | [1-10]  | ID 1-10 | 11           |

**Fallback 机制**：

如果某个领域没有配置 `domain_settings`：
- 插件会自动使用简单模式
- 每次推送按题目 ID 顺序返回前 N 道题（默认 3 道）
- `now_cursor` 不会更新（保持为 0）

**注意事项**：

1. ⚠️ `now_cursor` 的值必须是某个批次的 `start_index`，否则推送会失败
2. ⚠️ 批次配置必须连续且有序，避免出现跳跃或重叠
3. ✅ 每个群、每个领域的 cursor 是独立的，互不影响
4. ✅ 可以随时修改 `domain_settings` 调整批次范围

default 配置：如果 _conf_schema.json 中没有配置周推送规则，或群号不在 use_default 列表中，则使用 group_task_config 表中的配置进行推送。


#### 配置指令讲解
- /task on/off {domain_name}/all/default {hour:min} ：管理员指令
   - on/off：开启或关闭推送。
   - domain_name：指定领域名称，开启/关闭该领域的推送。
   - all：开启/关闭所有领域的推送。
   - default：切换为使用周推送默认配置（on）或手动配置（off）。
   - hour:min：可选参数，指定每天推送的时间点，格式为小时:分钟（24小时制）。如果不提供，则使用默认时间17:00。仅在开启推送时有效。

#### 具体格式

1. 查询指令输出格式

- /lhelp 输出格式：
```
📘 插件可用指令：
/lhelp - 列出所有可用指令和简要说明
/lgroup - 查询所有可加入的小组名
/ldomain - 查询所有可查看的领域名
/mygroup - 查询你已加入的小组名
/ltask  - 查看本群当前的题目推送状态
/addme {group_name} - 加入指定小组
/rmme {group_name} - 退出指定小组
/ans {problem_id} - 获取指定题目的参考答案
/rand {domain_name} - 随机抽取一道该领域的题目
/task on/off {domain_name}/all/default - （管理员指令）切换本群的题目推送状态
```
- /lgroup 输出格式：`📋 可加入的小组列表：小组名1、小组名2、...`
- /ldomain 输出格式：`📋 可查看的领域列表：领域名1、领域名2、...`
- /mygroup 输出格式：`📋 你已加入的小组列表：小组名1、小组名2、...`

- /ltask 输出格式：
```
📋 本群当前推送状态设置：
使用：{周推送默认配置 / 手动配置}
// 以下为手动配置示例
已开启的领域：领域1（{hour:min}），领域2（{hour:min}）
// 以下为周推送默认配置
周一 {hour:min}：领域名1，领域名2，领域名3
周二 {hour:min}：无推送
...
周日 {hour:min}：领域名1，领域名4
```

- /task on/off {domain_name}/all/default 输出格式：
  - domain_name 有值时：
`✅ 已在本群 {开启/关闭} 领域 [{domain_name}] 的题目推送。推送时间： {hour}:{min} `
  - all 时：
`✅ 已在本群 {开启/关闭} 所有领域的题目推送。推送时间： {hour}:{min} `
  - default 时：
`✅ 已在本群切换为使用{周推送默认配置/手动配置}`

2. 八股题目推送格式
- 随机抽题 /rand 输出格式：
```
📋 随机题目 [领域] [题目 ID: {id}]
{question}
回复 /ans {id} 获取参考答案。
```

- 推送输出格式（每个领域一条消息）：
```
📅 今日八股推送 [领域] 
[题目1 ID: {id}] 
{question} 
[题目2 ID: {id}] 
{question}
...
@xxx @xxx
回复 /ans {id} 获取参考答案。
```

注意：at 小组成员需要使用 AstrBot 提供的 at 功能，而非纯文字。

#### 数据库表应用备注 
use_ans ：在本版本中，返回 default_ans。
多余字段：schema.sql 中有一些字段是为未来功能预留的，本阶段不需要使用这些字段。

