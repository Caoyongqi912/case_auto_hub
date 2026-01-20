#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : interface_runner
# @Software: PyCharm
# @Desc: 重构后的接口运行器

from typing import Mapping, Tuple, Union

from app.mapper.interface import InterfaceMapper, InterfaceGroupMapper
from app.mapper.interface.interfaceVarsMapper import InterfaceVarsMapper
from app.mapper.interface.interfaceCaseMapper import InterfaceCaseMapper
from app.mapper.project.env import EnvMapper
from app.model.interface import InterfaceVariables
from app.model.interface.interfaceResultModel import (
    InterfaceGroupResult, InterfaceTaskResult
)
from app.model.base import Env
from play.starter import UIStarter
from utils import MyLoguru, log
from .interface_executor import InterfaceExecutor
from .variable_manager import VariableManager
from .middleware import HttpxMiddleware
from .context import ExecutionContext, StepContext
from .step import get_step_strategy
from .loop import get_loop_executor
from interface.writer import InterfaceAPIWriter, InitInterfaceCaseResult
from interface.types import VARS, InterfaceAPI


class InterfaceRunner:
    """接口运行器 - 重构版本"""
    
    def __init__(self, starter: Union[UIStarter]):
        self.starter = starter
        self.variable_manager = VariableManager()
        self.sender = HttpxMiddleware(self.variable_manager, self.starter)
        self.interface_executor = InterfaceExecutor(
            starter=self.starter,
            variable_manager=self.variable_manager,
            sender=self.sender
        )
    
    async def run_interface_case(
        self,
        interfaceCaseId: int,
        env_id: int | Env,
        error_stop: bool,
        task: InterfaceTaskResult = None
    ) -> Tuple[bool, 'InterfaceCaseResult']:
        """执行业务流用例"""
        from app.model.interface.interfaceResultModel import InterfaceCaseResult
        from enums.InterfaceCaseErrorStep import InterfaceCaseErrorStep
        
        interfaceCase = await InterfaceCaseMapper.get_by_id(ident=interfaceCaseId)
        log.info(f"查询到业务流用例  {interfaceCase}")
        
        if not interfaceCase:
            await self.starter.send(f"未找到用例 {interfaceCaseId}")
            return await self.starter.over()
        
        case_steps = await InterfaceCaseMapper.query_content(case_id=interfaceCaseId)
        
        await self.starter.send(f"用例 {interfaceCase.title} 执行开始。执行人 {self.starter.username}")
        await self.starter.send(f"查询到关联Step x {len(case_steps)} ...")
        
        if not case_steps:
            await self.starter.send("无可执行步骤，结束执行")
            return await self.starter.over()
        
        await self._init_interface_case_vars(interfaceCase)
        log.info(f"加载用例专属变量 = {self.variable_manager.get_vars()}")
        
        if isinstance(env_id, int):
            target_env = await EnvMapper.get_by_id(ident=env_id)
        else:
            target_env = env_id
        
        await self.starter.send(f"✍️✍️ 使用环境 {target_env}")
        
        case_result = await InterfaceAPIWriter.init_interface_case_result(
            InitInterfaceCaseResult(
                interface_case=interfaceCase,
                env=target_env,
                task=task,
                starter=self.starter
            )
        )
        log.info(f"初始化用例结果对象 = {case_result}")
        
        flag = True
        
        try:
            context = ExecutionContext(
                interface_case=interfaceCase,
                env=target_env,
                case_result=case_result,
                task=task,
                error_stop=error_stop,
                total_steps=len(case_steps)
            )
            
            for index, step_content in enumerate(case_steps, start=1):
                context.update_progress(index)
                
                await self.starter.send(
                    f"✍️✍️ {'=' * 20} EXECUTE_STEP {index} ： {step_content} {'=' * 20}"
                )
                
                if step_content.enable == 0 and not task:
                    await self.starter.send(f"✍️✍️  EXECUTE_STEP {index} ： 调试禁用 跳过执行")
                    continue
                
                if not flag and error_stop == InterfaceCaseErrorStep.STOP:
                    await self.starter.send(f"⏭️⏭️  SKIP_STEP {index} ： 遇到错误已停止")
                    continue
                
                step_context = StepContext(
                    step=step_content,
                    step_index=index,
                    execution_context=context,
                    starter=self.starter,
                    variable_manager=self.variable_manager
                )
                
                strategy = get_step_strategy(step_content.content_type, self.interface_executor)
                step_result = await strategy.execute(step_context)
                
                flag = flag and step_result
                
                if not flag and interfaceCase.error_stop == InterfaceCaseErrorStep.STOP:
                    case_result.progress = 100
                    break
                
                log.debug(f"case_result ===== {case_result}")
                await InterfaceAPIWriter.write_process(case_result=case_result)
                await self.starter.send(f"\n")
            
            await self.starter.send(f"用例 {interfaceCase.title} 执行结束")
            await self.starter.send(f"{'====' * 20}")
            case_result.interfaceLog = "".join(self.starter.logs)
            await InterfaceAPIWriter.write_interface_case_result(case_result=case_result)
            return flag, case_result
        except Exception as e:
            log.exception(e)
            return False, case_result
        finally:
            await self.variable_manager.clear()
            await self.starter.over(case_result.id)
    
    async def try_interface(self, interface_id: int, env_id: int) -> Mapping[str, Any]:
        """执行单个接口请求调试"""
        interface = await InterfaceMapper.get_by_id(ident=interface_id)
        env = await EnvMapper.get_by_id(ident=env_id)
        result, _ = await self.interface_executor.execute(interface=interface, env=env)
        return result
    
    async def try_group(self, groupId: int, env_id: int):
        """执行接口组"""
        interfaces = await InterfaceGroupMapper.query_apis(groupId=groupId)
        env = await EnvMapper.get_by_id(env_id)
        results = []
        
        for interface in interfaces:
            await self.starter.send(f"✍️✍️  Execute    {interface}")
            result, _ = await self.interface_executor.execute(interface=interface, env=env)
            results.append(result)
        
        return results
    
    async def execute_interface_by_ui(self, interface: InterfaceAPI, ui_vars: VARS):
        """UI侧执行接口"""
        if ui_vars:
            await self.variable_manager.add_vars(ui_vars)
        result, _ = await self.interface_executor.execute(interface=interface, env=None)
        return result, _
    
    async def run_interface_by_task(
        self,
        interface: InterfaceAPI,
        taskResult: InterfaceTaskResult,
        retry: int = 0,
        retry_interval: int = 0,
        env: Env = None
    ) -> bool:
        """任务执行api"""
        for attempt in range(retry + 1):
            result, success = await self.interface_executor.execute(
                interface=interface, env=env
            )
            
            if success:
                await InterfaceAPIWriter.write_interface_result(**result)
                return True
            
            if attempt == retry:
                await InterfaceAPIWriter.write_interface_result(**result)
                await self.starter.send(f"接口 {interface} 执行结果 FALSE")
                return False
            
            await self.starter.send(f"接口 {interface} 执行结果 FALSE 第 {attempt + 1} 次重试")
            if retry_interval:
                import asyncio
                await asyncio.sleep(retry_interval)
    
    async def _init_interface_case_vars(self, interfaceCase):
        """初始化用例变量"""
        try:
            interfaceCaseVars = await InterfaceVarsMapper.query_by(case_id=interfaceCase.id)
            if interfaceCaseVars:
                var_dict = {}
                for _var in interfaceCaseVars:
                    var_dict[_var.key] = await self.variable_manager.trans(_var.value)
                await self.variable_manager.add_vars(var_dict)
                await self.starter.send(f"🫳🫳 初始化用例变量 = {self.variable_manager.get_vars()}")
        except Exception as e:
            log.error(e)
