#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : task
# @Software: PyCharm
# @Desc: 任务执行模块

import time
from dataclasses import dataclass
from typing import List, Union, Optional, Any

from app.mapper.interfaceApi.interfaceTaskMapper import (
    InterfaceTaskMapper,
)

from app.mapper.project.env import EnvMapper
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceTaskResult
from app.model.interfaceAPIModel.interfaceTaskModel import InterfaceTask
from common.notifyManager import NotifyManager
from enums import InterfaceAPIResultEnum
from croe.interface.runner import InterfaceRunner
from croe.interface.starter import APIStarter, log
# BUG-F8 修复: 改用 TaskRunner 实例的 self.result_writer
from croe.interface.writer import ResultWriter


CASE = "CASE"
API = "API"


@dataclass
class TaskParams:
    """任务执行参数封装"""

    task_id: Union[int, str]
    env_id: Optional[int] = None
    retry: int = 0
    retry_interval: int = 0
    options: Optional[List[str]] = None
    notify_id: Optional[int] = None
    variables: Optional[Any] = None
    env: Optional[Any] = None

    def __post_init__(self) -> None:
        """初始化后处理"""
        if self.options is None:
            self.options = [API, CASE]


class TaskRunner:
    """任务执行器"""

    task: InterfaceTask

    def __init__(self, starter: APIStarter) -> None:
        """
        初始化任务执行器

        Args:
            starter: API启动器实例
        """
        self.starter = starter
        self.progress = 0
        self._last_progress_update = 0.0
        self._progress_update_interval = 0.5
        # BUG-F8 修复: TaskRunner 自有 result_writer, 替代模块级单例
        # (原单例 finalize_task_result 调 _flush_cache 时, 会把其他并发 case 的
        #  数据冲掉; 自有实例隔离)
        self.result_writer = ResultWriter()
        # BUG-T1 修复: TaskRunner 自有 _shared_vm, 任务级 variables 注入到这里,
        # 后续每个 InterfaceRunner 用这个 vm 而不是新建一个, 让 params.variables
        # 跨 API/CASE step 共享 (任务级"全局变量"语义)。
        from croe.a_manager import VariableManager
        self._shared_vm = VariableManager()

    async def set_process(
        self,
        task_result: Any
    ) -> None:
        """
        写进度

        Args:
            task_result: 任务结果对象
        """
        self.progress += 1

        current_time = time.time()
        should_update = (
            current_time - self._last_progress_update >=
            self._progress_update_interval or
            self.progress >= task_result.totalNumber
        )

        if should_update:
            task_result.progress = round(
                (self.progress / task_result.total_num) * 100, 1
            )
            await self.result_writer.update_task_progress(task_result=task_result)
            self._last_progress_update = current_time

    async def execute_task(
        self,
        params: TaskParams
    ) -> Any:
        """
        执行任务

        Args:
            params: 任务参数

        Returns:
            任务结果
        """
        log.info(f"execute_task  params {params} ")
        if isinstance(params.task_id, int):
            self.task = await InterfaceTaskMapper.get_by_id(ident=params.task_id)
        elif isinstance(params.task_id, str):
            self.task = await InterfaceTaskMapper.get_by_uid(uid=params.task_id)
        else:
            raise ValueError("task id error")
        log.info(f"查询到任务 {self.task}")

        if not self.task:
            await self.starter.send(
                f"未通过{params.task_id} 找到 相关任务"
            )
            return await self.starter.over()

        if params.env_id:
            params.env = await EnvMapper.get_by_id(ident=params.env_id)

        await self.starter.send(
            f"✍️✍️ 任务 {self.task.interface_task_title} 执行开始。"
            f"执行人 {self.starter.username}"
        )
        await self.starter.send(
            f"查询到关联Step x {self.task.interface_task_total_apis_num} ..."
        )

        task_result = await self.result_writer.init_task_result(
            task=self.task,
            starter=self.starter,
            env=params.env
        )

        if params.variables:
            await self._init_task_variables(params.variables)

        try:
            # BUG-T1 修复: 把 _shared_vm 注入 InterfaceRunner, 任务级 variables
            # 跨 API step 共享
            interface_runner = InterfaceRunner(self.starter, variable_manager=self._shared_vm)

            if API in params.options:
                await self._execute_api_steps(
                    interface_runner, task_result, params
                )

            if CASE in params.options:
                await self._execute_case_steps(
                    interface_runner, task_result, params
                )

            await self._finalize_task_result(task_result)

            if params.notify_id:
                await self._send_notification(params.notify_id, task_result)

            return task_result

        except Exception as e:
            log.exception(f"执行任务异常: {e}")
            task_result.result = InterfaceAPIResultEnum.ERROR
            return task_result

        finally:
            await self.starter.over(task_result.id)

    async def _init_task_variables(self, variables: Any) -> None:
        """
        初始化任务变量 (BUG-T1 修复: 之前只 log.info 一行, params.variables 静默丢失)

        修法: 在 TaskRunner 自管一个 VariableManager, 把 params.variables 走
        trans 变量替换后 add_vars, 后续每个 InterfaceRunner 共享这个 vm,
        跨 API/CASE step 共享变量 (类似"任务级 variables 全局可见"语义)。

        Args:
            variables: 变量配置, dict 或 list[dict]
        """
        if variables is None:
            return
        try:
            # 走 trans 做变量替换 (variables 自身可能含 ${xxx} 引用)
            transed = await self._shared_vm.trans(variables)
            await self._shared_vm.add_vars(transed)
            await self.starter.send(
                f"🫳🫳 初始化任务变量 = {self._shared_vm.variables}"
            )
        except Exception as e:
            # BUG-F4 风格对齐: log.exception 保留 traceback + starter.send 通知
            log.exception(f"初始化任务变量失败: {e}")
            try:
                await self.starter.send(
                    f"⚠️ 初始化任务变量失败, 任务变量将不可用: {e}"
                )
            except Exception:
                pass

    async def _execute_api_steps(
        self,
        interface_runner: InterfaceRunner,
        task_result: InterfaceTaskResult,
        params: TaskParams
    ) -> None:
        """
        执行API步骤

        Args:
            interface_runner: 接口执行器
            task_result: 任务结果
            params: 任务参数
        """
        interfaces = await InterfaceTaskMapper.query_association_interfaces(
            task_id=self.task.id
        )
        log.info(f'_execute_api_steps {interfaces}')

        if not interfaces:
            return

        task_result.total_num += len(interfaces)

        for interface in interfaces:
            await self.starter.send(
                f"✍️✍️  Execute API: {interface}"
            )

            success = await interface_runner.run_interface_by_task(
                interface=interface,
                task_result_id=task_result.id,
                retry=params.retry,
                retry_interval=params.retry_interval,
                env=params.env
            )

            if success:
                task_result.success_num += 1
            else:
                task_result.fail_num += 1

            await self.set_process(task_result)

    async def _execute_case_steps(
        self,
        interface_runner: InterfaceRunner,
        task_result: InterfaceTaskResult,
        params: TaskParams
    ) -> None:
        """
        执行用例步骤

        Args:
            interface_runner: 接口执行器
            task_result: 任务结果
            params: 任务参数
        """
        cases = await InterfaceTaskMapper.query_association_interface_cases(task_id=self.task.id)

        if not cases:
            return

        task_result.total_num += len(cases)

        for case in cases:
            await self.starter.send(
                f"✍️✍️  Execute CASE: {case}"
            )

            success, _ = await interface_runner.run_interface_case(
                interface_case_id=case.id,
                env=params.env,
                error_stop=True,
                task_result=task_result
            )

            if success:
                task_result.success_num += 1
            else:
                task_result.fail_num += 1

            await self.set_process(task_result)

    async def _finalize_task_result(self, task_result: InterfaceTaskResult) -> None:
        """
        完成任务结果

        Args:
            task_result: 任务结果
        """
        if task_result.fail_num == 0:
            task_result.result = InterfaceAPIResultEnum.SUCCESS
        else:
            task_result.result = InterfaceAPIResultEnum.ERROR

        await self.result_writer.finalize_task_result(task_result)
        await self.starter.send(
            f"✍️✍️ 任务 {self.task.interface_task_title} 执行结束"
        )

    @staticmethod
    async def _send_notification(
        notify_id: int,
        task_result: Any
    ) -> None:
        """
        发送通知

        Args:
            notify_id: 通知配置ID
            task_result: 任务结果
        """
        try:
            notify_manager = NotifyManager(notify_id=notify_id)
            await notify_manager.push(
                flag="API",
                task_result=task_result
            )
        except Exception as e:
            log.error(f"发送通知失败: {e}")
