
insert into groups (name) values ('be'), ('go'), ('java'), ('cpp');
insert into domain (name, group_id) values 
('Java', 3),
('C++', 4),
('Golang', 2),
('MySQL', 1),
('Redis', 1),
('网络协议', 1),
('操作系统', 1),
('数据结构', 1),
('消息队列', 1),
('分布式', 1),
('系统设计', 1),
('工具命令', 1);

-- 八股后续手动用脚本导入

-- 更新领域总分
-- update domain set total_score = (select sum(score) from problems where domain.id = bagus.domain_id);
