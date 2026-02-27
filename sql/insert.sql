
insert into groups (name) values ('be'), ('go'), ('java'), ('cpp'), ('test');
insert into domain (id, group_id, name) values 
(1, 3, 'Java'),
(2, 4, 'C++'),
(3, 2, 'Golang'),
(4, 1, 'MySQL'),
(5, 1, 'Redis'),
(6, 1, '网络协议'),
(7, 1, '操作系统'),
(8, 1, '数据结构'),
(9, 1, '消息队列'),
(10, 1, '分布式'),
(11, 1, '系统设计'),
(12, 1, '工具命令'),
(13, 5, '测试开发');
insert into category (id, domain_id, name) values 
(1, 1, 'Java基础面试题'),
(2, 1, 'Java集合面试题'),
(3, 1, 'Java并发编程面试题'),
(4, 1, 'Java虚拟机面试题'),
(5, 1, 'Spring面试题'),
(6, 2, 'C++面试题'),
(7, 3, 'Go语言基础'),
(8, 4, 'MySQL面试题'),
(9, 5, 'Redis面试题'),
(10, 6, '网络协议面试题'),
(11, 7, '操作系统面试题'),
(12, 8, '数据结构面试题'),
(13, 9, '消息队列面试题'),
(14, 10, '分布式面试题'),
(15, 11, '系统设计面试题'),
(16, 12, 'Linux命令面试题'),
(17, 12, 'Git面试题'),
(18, 13, '业务测试面试题'),
(19, 13, 'Python自动化测试面试题'),
(20, 13, 'Java自动化测试面试题'),
(21, 13, '性能测试面试题');


-- 题目后续手动用脚本导入

-- 更新领域总分
-- update domain set total_score = (select sum(score) from problems where domain.id = bagus.domain_id);
