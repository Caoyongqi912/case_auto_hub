#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/3/3
# @Author : cyq
# @File : task_runner
# @Software: PyCharm
# @Desc:
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from app.mapper.play.playTaskMapper import PlayTaskMapper
from app.model.playUI import PlayTaskResult, PlayCase
from common.notifyManager import NotifyManager
from croe.play.play_runner import PlayRunner
from croe.play.starter import UIStarter
from croe.play.writer import PlayCaseResultWriter, PlayTaskResultWriter
from utils import log

VARS = Optional[List[Dict[str, Any]]]


@dataclass
class PlayTaskExecuteParams:
    task_id: int | str
    retry: int = 0  # 重试次数
    retry_interval: int = 0  # 重试间隔
    notify_id: Optional[int] = None  # 推送
    variables: VARS = None  # 变量


class PlayTaskRunner:

    def __init__(self, starter: UIStarter):
        self.starter = starter

    async def execute_task(self, params: PlayTaskExecuteParams):
        """
        任务执行
        Args:
            params: 执行参数
        """

        if isinstance(params.task_id, int):
            task = await PlayTaskMapper.get_by_id(ident=params.task_id)
        else:
            task = await PlayTaskMapper.get_by_uid(uid=params.task_id)

        # 查询待执行用用例
        play_cases = await PlayTaskMapper.query_case(taskId=task.id)
        if not play_cases:
            log.warning(f"任务：{task.title} 没有可用用例")
            return

        await self.starter.send(f"开始执行任务：{task.title}: {task.desc} BY {self.starter.username}")
        # 查询待执行用用例
        play_cases = await PlayTaskMapper.query_case(taskId=task.id)
        if not play_cases:
            log.warning(f"任务：{task.title} 没有可用用例")
            return

        play_task_writer = PlayTaskResultWriter(starter=self.starter)

        # 初始化结果对象
        task_result = await play_task_writer.init_result(
            task=task, case_nums=len(play_cases),
        )
        try:
            await self.__execute_case(params=params,
                                      play_cases=play_cases,
                                      task_result=task_result)
        except Exception as e:
            log.exception(e)
        finally:
            await play_task_writer.write_final_result(task_result)
            if params.notify_id:
                await self.__notify_report(params.notify_id, task_result)

    async def __execute_case(self,
                             params: PlayTaskExecuteParams,
                             play_cases: List[PlayCase],
                             task_result: PlayTaskResult):
        """
        执行用例
        Args:
            params: 执行参数
            play_cases: 用例列表
            task_result: 任务结果对象
        """

        for play_case in play_cases:
            for r in range(params.retry + 1):
                play_runner = PlayRunner(starter=self.starter)
                if params.variables:
                    await self.starter.send(f"添加变量 {params.variables}")
                    await play_runner.variable_manager.add_vars(params.variables)

                await play_runner.init_case_variables(play_case=play_case)
                case_result_writer = PlayCaseResultWriter(starter=self.starter)
                await case_result_writer.init_result(play_case=play_case,
                                                     vars_info=play_runner.variable_manager.variables)

                is_last_attempt = (r == params.retry)

                case_success = await play_runner.execute_case(
                    play_case=play_case,
                    task_result=task_result,
                    error_stop=True,
                    case_result_writer=case_result_writer,
                    write_result_on_failure=is_last_attempt
                )

                if case_success:
                    task_result.success_number += 1
                    break
                if not is_last_attempt:
                    if params.retry_interval > 0:
                        await asyncio.sleep(params.retry_interval)
                    await self.starter.send(f"业务用例 {play_case} 失败  第 {r + 1} 次重试")
                    continue
                else:
                    task_result.fail_number += 1

    @staticmethod
    async def __notify_report(notify_id: int, task_result: PlayTaskResult):
        """
        推送报告
        """
        n = NotifyManager(notify_id)
        await n.push(flag="UI", task_result=task_result)
