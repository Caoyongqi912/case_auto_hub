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
from app.model.interfaceAPIModel.interfaceTaskModel import InterfaceTask
from common.notifyManager import NotifyManager
from enums import InterfaceAPIResultEnum
from croe.interface.runner import InterfaceRunner
from croe.interface.starter import APIStarter, log
from croe.interface.writer import result_writer


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
                (self.progress / task_result.totalNumber) * 100, 1
            )
            await result_writer.write_task_process(task_result=task_result)
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
        self.task = await InterfaceTaskMapper.get_by_id(ident=params.task_id)
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

        task_result = await result_writer.init_interface_task_result(
            interfaceTask=self.task,
            starter=self.starter,
            env=params.env
        )

        if params.variables:
            await self._init_task_variables(params.variables)

        try:
            interface_runner = InterfaceRunner(self.starter)

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
        初始化任务变量

        Args:
            variables: 变量配置
        """
        try:
            await self.starter.send(
                f"🫳🫳 初始化任务变量 = {variables}"
            )
        except Exception as e:
            log.error(f"初始化任务变量失败: {e}")

    async def _execute_api_steps(
        self,
        interface_runner: InterfaceRunner,
        task_result: Any,
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

        if not interfaces:
            return

        task_result.totalNumber += len(interfaces)

        for interface in interfaces:
            await self.starter.send(
                f"✍️✍️  Execute API: {interface}"
            )

            success = await interface_runner.run_interface_by_task(
                interface=interface,
                task_result=task_result,
                retry=params.retry,
                retry_interval=params.retry_interval,
                env=params.env
            )

            if success:
                task_result.successNum += 1
            else:
                task_result.failNum += 1

            await self.set_process(task_result)

    async def _execute_case_steps(
        self,
        interface_runner: InterfaceRunner,
        task_result: Any,
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

        task_result.totalNumber += len(cases)

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
                task_result.successNum += 1
            else:
                task_result.failNum += 1

            await self.set_process(task_result)

    async def _finalize_task_result(self, task_result: Any) -> None:
        """
        完成任务结果

        Args:
            task_result: 任务结果
        """
        if task_result.failNum == 0:
            task_result.result = InterfaceAPIResultEnum.SUCCESS
        else:
            task_result.result = InterfaceAPIResultEnum.ERROR

        await result_writer.write_interface_task_result(task_result)
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
