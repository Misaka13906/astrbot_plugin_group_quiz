import shlex
from astrbot.api.event import AstrMessageEvent
from .base import BaseHandler
from ..push_strategy.factory import StrategyFactory

class StrategyHandlers(BaseHandler):
    """策略管理指令处理器"""

    async def cmd_list_strategy(self, event: AstrMessageEvent):
        """查看本群当前使用的推送策略及状态"""
        group_qq = event.get_group_id()
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        group_qq_str = str(group_qq)
        
        # 获取所有激活的配置
        configs = self.db.get_active_group_task_config(group_qq_str)
        if not configs:
            yield event.plain_result("📋 本群当前没有已激活的推送任务")
            return

        result_lines = ["🎯 本群推送策略状态："]
        
        for config in configs:
            domain_name = config['domain_name']
            domain_id = config['domain_id']
            strategy_type = config.get('strategy_type', 'batch')
            
            # 获取策略信息
            strategy = StrategyFactory.get_group_strategy(self.db, group_qq_str, domain_id)
            info = strategy.get_strategy_info(group_qq_str, domain_id)
            
            result_lines.append(f"\n--- {domain_name} ({strategy_type}) ---")
            result_lines.append(info)
            
        yield event.plain_result("\n".join(result_lines))

    async def cmd_strategy(self, event: AstrMessageEvent):
        """策略管理指令 /stra"""
        message = event.message_str.strip()
        try:
            parts = shlex.split(message)
        except ValueError:
            yield event.plain_result("❌ 命令解析失败")
            return
            
        if len(parts) < 2:
            yield event.plain_result(
                "❌ 参数不足。用法：\n"
                "/stra set <counter/batch/daterem> <all/领域名> - 设置推送策略\n"
                "/stra info <领域名> - 查看详细状态\n"
                "/stra reset <领域名> - 重置进度"
            )
            return
            
        action = parts[1].lower()
        group_qq = str(event.get_group_id())
        
        if not group_qq:
            yield event.plain_result("❌ 此命令仅在群聊中可用")
            return

        # /stra set <type> <target>
        if action == "set":
            if not event.is_admin():
                yield event.plain_result("❌ 此命令仅限管理员使用")
                return
                
            if len(parts) < 4:
                yield event.plain_result("❌ 参数不足。用法：/stra set <counter/batch/daterem> <all/领域名>")
                return
                
            strategy_type = parts[2].lower()
            if strategy_type not in ['counter', 'batch', 'daterem']:
                yield event.plain_result("❌ 未知的策略类型。可选: counter, batch, daterem")
                return

            target = parts[3]
            
            if target.lower() == 'all':
                # 更新所有激活的配置
                active_configs = self.db.get_active_group_task_config(group_qq)
                if not active_configs:
                    yield event.plain_result("❌ 本群没有已开启的推送任务")
                    return
                    
                count = 0
                for config in active_configs:
                    self.db.set_strategy_type(group_qq, config['domain_id'], strategy_type)
                    count += 1
                    
                yield event.plain_result(
                    f"✅ 已将 {count} 个领域的推送策略切换为 [{strategy_type}]\n"
                    f"原有进度已保留，立即生效。"
                )
            else:
                # 更新指定领域
                domain = self.db.get_domain_by_name(target)
                if not domain:
                    yield event.plain_result(f"❌ 领域 [{target}] 不存在")
                    return

                # 确保有任务配置记录（即使未激活），否则无法设置策略
                # 如果没有，可能需要先初始化？或者提示用户先开启任务。
                # set_strategy_type 依赖 group_task_config 表中存在记录。
                # 如果用户从未开启过任务，记录可能不存在。
                # 检查记录是否存在
                # 检查或初始化任务配置
                record = self.db.get_group_domain_config(group_qq, domain['id'])
                if not record:
                     # 自动初始化配置，默认时间 17:00
                     self.db.init_group_domain_config(group_qq, domain['id'])

                self.db.set_strategy_type(group_qq, domain['id'], strategy_type)
                yield event.plain_result(
                    f"✅ 已将领域 [{target}] 的推送策略切换为 [{strategy_type}]\n"
                    f"原有进度已保留，立即生效。"
                )
            return

        # /stra info <domain>
        if action == "info":
            if len(parts) < 3:
                yield event.plain_result("❌ 请指定领域名称")
                return
                
            domain_name = parts[2]
            domain = self.db.get_domain_by_name(domain_name)
            if not domain:
                yield event.plain_result(f"❌ 领域 [{domain_name}] 不存在")
                return
                
            strategy = StrategyFactory.get_group_strategy(self.db, group_qq, domain['id'])
            info = strategy.get_strategy_info(group_qq, domain['id'])
            
            yield event.plain_result(info)
            return

        # /stra reset <domain>
        if action == "reset":
            if not event.is_admin():
                yield event.plain_result("❌ 此命令仅限管理员使用")
                return

            if len(parts) < 3:
                yield event.plain_result("❌ 请指定领域名称")
                return
                
            domain_name = parts[2]
            domain = self.db.get_domain_by_name(domain_name)
            if not domain:
                yield event.plain_result(f"❌ 领域 [{domain_name}] 不存在")
                return
                
            strategy_type = self.db.get_strategy_type(group_qq, domain['id'])
            self.db.reset_domain_progress(group_qq, domain['id'], strategy_type)
            
            yield event.plain_result(
                f"✅ 已重置 [{domain_name}] 的推送进度\n"
                f"当前策略: {strategy_type}"
            )
            return
            
        yield event.plain_result("❌ 未知指令，请输入 /stra 查看帮助")
