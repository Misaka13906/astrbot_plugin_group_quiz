-- ============================================
-- 样例数据：用于测试所有插件功能
-- ============================================

-- 1. 题目数据 (多个领域，足够测试批次推送)
-- Java 领域题目 (domain_id=1)
INSERT INTO problems (domain_id, category, topic, question, default_ans, score) VALUES 
(1, 'Java基础', 'JVM', 'JVM的内存结构有哪些？', 'JVM内存结构主要包括：方法区、堆、虚拟机栈、本地方法栈、程序计数器。其中堆和方法区是线程共享的，栈和程序计数器是线程私有的。', 10),
(1, 'Java基础', '集合', 'ArrayList和LinkedList的区别？', 'ArrayList基于数组实现，查询快O(1)，插入删除慢O(n)；LinkedList基于链表实现，插入删除快O(1)，查询慢O(n)。ArrayList适合随机访问，LinkedList适合频繁插入删除。', 10),
(1, 'Java基础', '并发', '什么是线程安全？', '线程安全是指多个线程访问同一个对象时，无论运行时环境如何调度这些线程，或者这些线程如何交替执行，都能保证这个对象的状态是正确的。实现方式有synchronized、Lock、原子类等。', 10),
(1, 'Java进阶', 'Spring', 'Spring的IoC是什么？', 'IoC(控制反转)是Spring的核心概念，将对象的创建和依赖关系的管理交给Spring容器，而不是在代码中直接new对象。通过依赖注入(DI)实现，降低代码耦合度。', 10),
(1, 'Java进阶', 'Spring', 'AOP的应用场景有哪些？', 'AOP(面向切面编程)主要应用场景：日志记录、性能监控、事务管理、权限控制、异常处理等。通过在不修改原有业务代码的情况下，增强功能。', 10),
(1, 'Java进阶', 'MyBatis', 'MyBatis的#{}和${}的区别？', '#{}是预编译处理，能防止SQL注入，会自动加上单引号；${}是字符串替换，不能防止SQL注入，不会加引号。一般使用#{}，只有在动态表名、列名时使用${}。', 10),
(1, 'Java基础', '异常', 'Checked异常和Unchecked异常的区别？', 'Checked异常必须显式捕获或声明抛出(如IOException)；Unchecked异常不强制处理(如NullPointerException)。Checked继承Exception，Unchecked继承RuntimeException。', 10),
(1, 'Java基础', '反射', 'Java反射的作用是什么？', '反射允许在运行时获取类的信息、创建对象、调用方法、访问字段。主要应用于框架开发(Spring)、动态代理、序列化等场景。缺点是性能较低、破坏封装性。', 10),
(1, 'Java并发', '锁', 'synchronized和ReentrantLock的区别？', 'synchronized是关键字，自动释放锁，不可中断；ReentrantLock是类，需手动释放，可中断，支持公平锁，可绑定多个条件。ReentrantLock更灵活但使用复杂。', 10),
(1, 'Java并发', '线程池', '线程池的核心参数有哪些？', '核心参数：corePoolSize(核心线程数)、maximumPoolSize(最大线程数)、keepAliveTime(空闲线程存活时间)、workQueue(任务队列)、threadFactory(线程工厂)、handler(拒绝策略)。', 10),
(1, 'JVM', 'GC', 'Java的垃圾回收算法有哪些？', '主要算法：标记-清除(产生碎片)、标记-整理(效率低)、复制算法(浪费空间)、分代收集(结合前三种)。现代JVM多采用分代收集，新生代用复制，老年代用标记-整理。', 10),
(1, 'JVM', '类加载', '什么是双亲委派模型？', '类加载器加载类时，先委托父加载器加载，父加载器无法加载才自己加载。好处：避免重复加载、保证核心类安全。Bootstrap → Extension → Application顺序。', 10);

-- Golang 领域题目 (domain_id=3)
INSERT INTO problems (domain_id, category, topic, question, default_ans, score) VALUES 
(3, 'Golang基础', '协程', '什么是协程(Goroutine)？', '协程是用户态轻量级线程，由Go运行时调度。通过go关键字启动，初始栈2-4KB，可自动扩展。相比线程更轻量，可轻松创建百万级协程。', 10),
(3, 'Golang基础', '通道', 'Channel的作用是什么？', 'Channel是Go中goroutine间通信的管道。分为有缓冲和无缓冲，遵循"不要通过共享内存来通信，而要通过通信来共享内存"的理念。支持select多路复用。', 10),
(3, 'Golang基础', '接口', 'Go的接口是怎么实现的？', 'Go接口是隐式实现，只要实现了接口的所有方法就自动实现了该接口。底层由eface(空接口)和iface(非空接口)两种数据结构表示，包含类型信息和数据指针。', 10),
(3, 'Golang并发', '并发模式', 'Go的并发模式有哪些？', '主要模式：Worker Pool(工作池)、Pipeline(管道)、Fan-out/Fan-in(扇出扇入)、Context(上下文控制)、Select(多路复用)等。常用于任务分发和结果汇总。', 10),
(3, 'Golang并发', 'sync包', 'sync.Mutex和sync.RWMutex的区别？', 'Mutex是互斥锁，同时只能一个goroutine持有；RWMutex是读写锁，允许多个读或一个写。读多写少场景用RWMutex性能更好。', 10),
(3, 'Golang内存', 'GC', 'Go的垃圾回收机制？', 'Go使用三色标记法+写屏障实现并发GC，标记过程与用户程序并行。分为标记准备、并发标记、标记终止、清扫四个阶段。Go1.5后延迟大幅降低。', 10);

-- MySQL 领域题目 (domain_id=4)
INSERT INTO problems (domain_id, category, topic, question, default_ans, score) VALUES 
(4, 'MySQL基础', '索引', '什么是索引？有哪些类型？', '索引是帮助MySQL高效获取数据的数据结构。类型：B+树索引(InnoDB默认)、哈希索引、全文索引、空间索引。主键索引、唯一索引、普通索引、联合索引。', 10),
(4, 'MySQL基础', '事务', 'MySQL事务的ACID特性？', 'A原子性(要么全做要么全不做)、C一致性(数据完整性约束)、I隔离性(并发事务互不干扰)、D持久性(提交后永久保存)。通过undo log、redo log、锁机制实现。', 10),
(4, 'MySQL优化', '查询优化', 'EXPLAIN的作用是什么？', 'EXPLAIN用于分析SQL执行计划，显示type(访问类型)、key(使用索引)、rows(扫描行数)等信息。帮助定位慢查询问题，优化索引使用。', 10),
(4, 'MySQL优化', '索引优化', '什么是覆盖索引？', '查询的所有列都在索引中，不需要回表查询。优点是减少IO、提高性能。通过建立联合索引实现。如index(a,b,c)覆盖select a,b,c。', 10);

-- Redis 领域题目 (domain_id=5)
INSERT INTO problems (domain_id, category, topic, question, default_ans, score) VALUES 
(5, 'Redis基础', '数据类型', 'Redis有哪些数据类型？', '基本类型：String、List、Set、Hash、ZSet。特殊类型：Bitmap、HyperLogLog、GEO、Stream。每种类型有不同的应用场景和底层实现。', 10),
(5, 'Redis基础', '持久化', 'RDB和AOF的区别？', 'RDB是快照持久化，全量备份，恢复快但可能丢数据；AOF是追加日志，实时性好但文件大、恢复慢。可混合使用，RDB做备份，AOF保证数据安全。', 10),
(5, 'Redis高级', '缓存', '缓存穿透、击穿、雪崩的解决方案？', '穿透(查不存在的key)：布隆过滤器、空值缓存；击穿(热点key过期)：永不过期、互斥锁；雪崩(大量key同时过期)：随机过期时间、多级缓存。', 10);

-- 2. 批次配置 (domain_settings) - 用于测试游标推送系统
-- Java 领域分3批推送
INSERT INTO domain_settings (domain_id, start_index, end_index) VALUES
(1, 1, 4),     -- 批次1: 题目 ID 1-4 (基础部分)
(1, 5, 8),     -- 批次2: 题目 ID 5-8 (进阶部分)
(1, 9, 12);    -- 批次3: 题目 ID 9-12 (高级部分)

-- Golang 领域分2批推送
INSERT INTO domain_settings (domain_id, start_index, end_index) VALUES
(3, 13, 15),   -- 批次1: 题目 ID 13-15
(3, 16, 18);   -- 批次2: 题目 ID 16-18

-- MySQL 领域单批推送
INSERT INTO domain_settings (domain_id, start_index, end_index) VALUES
(4, 19, 22);   -- 批次1: 题目 ID 19-22

-- 3. 群任务配置 (group_task_config) - 用于测试推送功能
-- 注意：cursor 的值应该是对应批次的 start_index

-- 测试群: 123456789 - Java 领域，每天21:00推送，已激活
-- Java 第一批 start_index = 1
INSERT INTO group_task_config (group_qq, domain_id, push_time, is_active, now_cursor) VALUES
('123456789', 1, '21:00', 1, 1);

-- 测试群: 123456789 - Golang 领域，每天21:00推送，已激活
-- Golang 第一批 start_index = 13
INSERT INTO group_task_config (group_qq, domain_id, push_time, is_active, now_cursor) VALUES
('123456789', 3, '21:00', 1, 13);

-- 测试群: 123456789 - MySQL 领域，每天21:00推送，未激活
-- MySQL 第一批 start_index = 19
INSERT INTO group_task_config (group_qq, domain_id, push_time, is_active, now_cursor) VALUES
('123456789', 4, '21:00', 0, 19);

-- Redis 没有配置 domain_settings，会使用 fallback 模式，不需要配置 cursor

-- ============================================
-- 测试说明
-- ============================================
-- 
-- 可测试的功能：
-- 
-- 1. 查询命令：
--    /lgroup - 查看所有小组 (应显示: be, go, java, cpp)
--    /ldomain - 查看所有领域 (应显示: Java, Golang, MySQL, Redis等)
--    /mygroup - 查看已加入小组 (需要先用 /addme 加入)
--    /ltask - 查看本群推送状态 (需要在群聊中使用)
-- 
-- 2. 订阅命令：
--    /addme Java - 加入 Java 小组
--    /rmme Java - 退出 Java 小组
-- 
-- 3. 题目命令：
--    /ans 1 - 查看题目1的答案
--    /rand Java - 随机获取一道 Java 题目
-- 
-- 4. 管理命令（需要群管理员权限）：
--    /task on Java 17:00 - 开启 Java 领域推送
--    /task off Java - 关闭 Java 领域推送
--    /task on default - 使用周配置
--    /task on all 18:00 - 开启所有领域推送
-- 
-- 5. 游标推送测试：
--    - Java 领域会按批次推送: 1-4 -> 5-8 -> 9-12 -> 循环
--    - Golang 领域会按批次推送: 13-15 -> 16-18 -> 循环
--    - 每次推送后检查 group_task_config.now_cursor 是否正确更新
-- 
-- 6. @ 提及测试：
--    - 推送时会 @所有订阅该领域小组的用户
--    - 例如 Java 推送会 @张三 和 @赵六
-- 
-- ============================================
-- 注意事项
-- ============================================
-- 
-- 1. 将 group_qq 替换为实际测试群号
-- 2. 推送时间建议设置为几分钟后，方便测试
-- 3. 或者在 _conf_schema.json 中配置周推送默认时间
-- 4. 可以用数据库客户端查看 now_cursor 的变化
-- 
