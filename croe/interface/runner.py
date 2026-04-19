#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : runner
# @Software: PyCharm
# @Desc: 接口执行器

import asyncio
from typing import Union, Optional, Tuple, Any, Dict, List

from app.mapper.interfaceApi.interfaceGlobalMapper import InterfaceGlobalHeaderMapper
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
from app.mapper.interfaceApi.interfaceGroupMapper import InterfaceGroupMapper
from app.mapper.interfaceApi.interfaceVarsMapper import InterfaceVarsMapper
from app.mapper.project.env import EnvMapper
from app.model.base.env import EnvModel
from app.model.interfaceAPIModel.interfaceGlobalModel import InterfaceGlobalHeader

from croe.interface.executor.context import CaseStepContext, ExecutionContext
from croe.interface.executor.interface_executor import InterfaceExecutor
from croe.interface.executor.step_content import get_step_strategy
from croe.a_manager import VariableManager
from croe.interface.writer import result_writer
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.starter import APIStarter
from croe.play.starter import UIStarter
from utils import log


class InterfaceRunner:
    """接口执行入口类"""

    __slots__ = ("starter", "variable_manager", "interface_executor", "global_headers")

    def __init__(self, starter: Union[UIStarter, APIStarter]) -> None:
        """
        初始化接口执行器

        Args:
            starter: 启动器实例（UI或API）
        """
        self.starter = starter
        self.variable_manager = VariableManager()
        self.global_headers: List[InterfaceGlobalHeader] = []
        self.interface_executor = InterfaceExecutor(
            starter=self.starter,
            variable_manager=self.variable_manager,
            global_headers=self.global_headers,
        )

    async def try_interface(
        self,
        interface_id: int,
        env_id: int
    ) -> Dict[str, Any]:
        """
        执行单个接口请求调试

        Args:
            interface_id: 接口id
            env_id: 环境id

        Returns:
            接口执行结果
        """
        interface = await InterfaceMapper.get_by_id(ident=interface_id)
        env = await self._get_running_env(env=env_id)
        await self.init_global_headers()
        result, _ = await self.interface_executor.execute(
            interface=interface, env=env
        )
        return result

    async def try_group(
        self,
        group_id: int,
        env_id: int
    ) -> list:
        """
        执行接口组

        Args:
            group_id: 组ID
            env_id: 环境ID

        Returns:
            接口执行结果列表
        """
        interfaces = await InterfaceGroupMapper.query_association_interfaces(
            group_id=group_id
        )
        
        await self.init_global_headers()
        env = await self._get_running_env(env=env_id)
        results = []
        for interface in interfaces:
            await self.starter.send(f"✍️✍️  Execute    {interface}")
            result, _ = await self.interface_executor.execute(
                interface=interface, env=env
            )
            results.append(result)
        return results

    async def run_interface_case(
        self,
        interface_case_id: int,
        env: Union[int, Any],
        error_stop: bool,
        task_result: Optional[Any] = None
    ) -> Tuple[bool, Optional[Any]]:
        """
        执行接口业务流用例

        Args:
            interface_case_id: 接口用例id
            env: 环境id或者对象
            error_stop: 是否遇到错误停止执行
            task_result: 在任务中执行时，需要传递任务执行结果

        Returns:
            Tuple[是否成功, 用例结果对象]
        """
        interface_case = await InterfaceCaseMapper.get_by_id(
            ident=interface_case_id
        )
        log.info(f"查询到业务流用例  {interface_case}")

        if not interface_case:
            await self.starter.send(
                f"未通过{interface_case_id} 找到 相关业务流用例"
            )
            return await self.starter.over()

        case_content_steps = await InterfaceCaseMapper.query_steps(
            case_id=interface_case.id
        )
        await self.starter.send(
            f"用例 {interface_case.case_title} 执行开始。"
            f"执行人 {self.starter.username}"
        )
        await self.starter.send(
            f"查询到关联Step x {len(case_content_steps)} ..."
        )

        if not case_content_steps:
            await self.starter.send("无可执行业务流步骤，结束执行")
            return await self.starter.over()

        await self.init_interface_case_vars(interface_case_id)
        await self.init_global_headers()

        target_env = await self._get_running_env(env=env)
        case_success = True

        case_result = await result_writer.init_case_result(
            interface_case=interface_case,
            starter=self.starter,
            env=target_env,
            task_result=task_result
        )
        log.debug(f"result_writer.init_case_result ={ case_result }")


        try:
            execution_context = ExecutionContext(
                interface_case=interface_case,
                env=target_env,
                case_result=case_result,
                task_result=task_result
            )

            total_steps = len(case_content_steps)
            for index, step_content in enumerate(case_content_steps, start=1):
                await self.starter.send(
                    f"✍️✍️ {'=' * 20} EXECUTE_STEP {index} ： "
                    f"{step_content} {'=' * 20}"
                )
                
                # enable 仅在调试模式下生效 任务执行默认开启
                if step_content.enable == 0 and not task_result:
                    await self.starter.send(
                        f"✍️✍️  EXECUTE_STEP {index} ： 调试禁用 跳过执行"
                    )
                    case_result.progress = (index * 100) // total_steps
                    await result_writer.update_case_progress(case_result)
                    continue
                
         
                
                # 执行步骤  
                step_context = CaseStepContext(
                    index=index,
                    content=step_content,
                    execution_context=execution_context,
                    starter=self.starter,
                    variable_manager=self.variable_manager,
                )

                strategy = get_step_strategy(
                    step_content.content_type,
                    self.interface_executor
                )
                step_success = await strategy.execute(step_context)
                
                case_success = case_success and step_success                
                
                case_result.progress = (index * 100) // total_steps
                
                # 用例执行失败 且 配置了错误停止
                if not case_success and error_stop:
                    await self.starter.send(
                        f"⏭️⏭️  SKIP_STEP {index} ： 遇到错误已停止"
                    )
                    case_result.progress = 100
                    await result_writer.update_case_progress(case_result)
                    break
                
                await self.starter.send(
                    f"✍️✍️  EXECUTE_STEP {index} ： FINISH"
                )

            await self.starter.send(
                f"用例 {interface_case.case_title} 执行结束"
            )
            await self.starter.send(f"{'====' * 20}")
            case_result.interfaceLog = "".join(self.starter.logs)
            await result_writer.finalize_case_result(
                case_result=case_result,
                logs="".join(self.starter.logs)
            )
            
            return case_success, case_result

        except Exception as e:
            log.exception(f"执行业务流用例异常: {e}")
            return False, case_result

        finally:
            await self.variable_manager.clear()
            await self.starter.over(case_result.id)

    async def run_interface_by_task(
        self,
        interface: Any,
        task_result: Any,
        retry: int = 0,
        retry_interval: int = 0,
        env: Optional[Any] = None
    ) -> bool:
        """
        执行接口任务

        Args:
            interface: 接口对象
            task_result: 接口任务结果对象
            retry: 重试次数
            retry_interval: 重试间隔
            env: 环境对象

        Returns:
            是否执行成功
        """
        for attempt in range(retry + 1):
            result, success = await self.interface_executor.execute(
                interface=interface,
                task_result=task_result,
                env=env
            )

            if success:
                await result_writer.write_interface_result(
                    interface_result=InterfaceResult(**result)
                )
                return True

            if attempt == retry:
                await result_writer.write_interface_result(
                    interface_result=InterfaceResult(**result)
                )
                await self.starter.send(
                    f"接口 {interface} 执行结果 FALSE"
                )
                return False

            await self.starter.send(
                f"接口 {interface} 执行结果 FALSE 第 {attempt + 1} 次重试"
            )
            if retry_interval:
                await asyncio.sleep(retry_interval)

        return False

    async def init_interface_case_vars(self, interface_case_id: int) -> None:
        """
        初始化业务流用例变量

        Args:
            interface_case_id: 业务流用例id
        """
        try:
            interface_case_vars = await InterfaceVarsMapper.query_by(
                case_id=interface_case_id
            )
            if interface_case_vars:
                var_dict = {}
                for var in interface_case_vars:
                    var_dict[var.key] = await self.variable_manager.trans(
                        var.value
                    )
                await self.variable_manager.add_vars(var_dict)
                await self.starter.send(
                    f"🫳🫳 初始化业务用例变量 = "
                    f"{self.variable_manager.variables}"
                )
        except Exception as e:
            log.error(f"初始化业务流用例变量失败: {e}")



    async def init_global_headers(self)->Optional[List[InterfaceGlobalHeader]]:
        """
        初始化g headers
        """
        # 添加全局请求头
        global_headers = await InterfaceGlobalHeaderMapper.query_all()
        if not global_headers:
            log.info(f"use global_headers {global_headers}")
            return None
        if global_headers:
            await self.starter.send(
                f"🫳🫳 全局Headers已加载: {len(self.global_headers)} 条"
            )
            self.interface_executor.g_headers = global_headers or []


    async def _get_running_env(self, env: Union[int, EnvModel]) -> Optional[EnvModel]:
        """
        获取当前环境
        """
        if isinstance(env, int):
            target_env = await EnvMapper.get_by_id(ident=env)
        else:
            target_env = env
        await self.starter.send(f"✍️✍️ 使用环境 {target_env}")
        return target_env