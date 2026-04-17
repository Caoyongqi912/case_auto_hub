#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : loop
# @Software: PyCharm
# @Desc: 循环步骤执行策略

import asyncio
import json
from datetime import datetime
from typing import List, Optional, Any, TYPE_CHECKING

from app.mapper.interfaceApi.interfaceLoopMapper import InterfaceLoopMapper
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.a_manager import ConditionManager
from croe.interface.writer import result_writer
from enums import (
    InterfaceAPIResultEnum,
    ExtractTargetVariablesEnum
)
from enums.CaseEnum import LoopTypeEnum, CaseStepContentType
from utils import log
from utils.assertsUtil import MyAsserts

if TYPE_CHECKING:
    from croe.interface.executor.interface_executor import InterfaceExecutor

MAX_LOOP_LIMIT = 20


class APILoopContentStrategy(StepBaseStrategy):
    """循环步骤执行策略"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        循环执行步骤

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
        loop = await InterfaceLoopMapper.get_by_id(
            ident=step_context.content.target_id
        )

        if not loop:
            await step_context.starter.send(
                f"未找到循环配置: id={step_context.content.target_id}"
            )
            return False

        loop_steps = await InterfaceLoopMapper.query_interfaces_by_loop_id(
            loop_id=step_context.content.target_id
        )

        if not loop_steps:
            return True

        start_time = datetime.now()

        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        loop_content_result = await result_writer.write_step_result(
            content_type=CaseStepContentType.STEP_LOOP,
            case_result_id=step_context.execution_context.case_result.id,
            task_result_id=task_result_id,
            content_id=step_context.content.id,
            content_name=step_context.content.resolved_content_name,
            content_desc=step_context.content.content_desc,
            content_step=step_context.index,
            success=False,
            start_time=start_time,
            use_time="",
            loop_count=0,
            loop_type=loop.loop_type,
            success_count=0,
            fail_count=0,
        )

        match loop.loop_type:
            case LoopTypeEnum.LoopTimes:
                return await self._execute_loop_times(
                    step_context=step_context,
                    loop=loop,
                    api_steps=loop_steps,
                    content_result=loop_content_result
                )
            case LoopTypeEnum.LoopItems:
                return await self._execute_loop_items(
                    step_context=step_context,
                    loop=loop,
                    api_steps=loop_steps,
                    content_result=loop_content_result
                )
            case LoopTypeEnum.LoopCondition:
                return await self._execute_loop_condition(
                    step_context=step_context,
                    loop=loop,
                    api_steps=loop_steps,
                    content_result=loop_content_result
                )
            case _:
                log.warning(f"未知的循环类型: {loop.loop_type}")
                return False

    async def _execute_loop_times(
        self,
        step_context: CaseStepContext,
        loop: Any,
        api_steps: List[Any],
        content_result: Any
    ) -> bool:
        """次数循环"""
        all_success = True
        case_result = step_context.execution_context.case_result
        loop_count = 0
        success_count = 0
        fail_count = 0

        loop_times = min(loop.loop_times, MAX_LOOP_LIMIT)

        for i in range(1, loop_times + 1):
            for index, interface in enumerate(api_steps, start=1):
                await step_context.starter.send(
                    f"✍️✍️  {'-' * 20} 次数循环步骤 次数{i}   "
                    f"{interface.name} {'-' * 20}"
                )

                interface_result, success = await self.interface_executor.execute(
                    interface=interface,
                    env=step_context.execution_context.env,
                    case_result=case_result
                )

                await result_writer.write_interface_result(
                    interface_result=InterfaceResult(**interface_result),
                    content_result_id=content_result.id
                )

                loop_count += 1
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    all_success = False

                if loop.loop_interval > 0:
                    await asyncio.sleep(loop.loop_interval)

        await result_writer.update_step_result(
            result_id=content_result.id,
            result=all_success,
            status="SUCCESS" if all_success else "FAIL",
            loop_count=loop_count,
            success_count=success_count,
            fail_count=fail_count,
        )

        if all_success:
            case_result.success_num += 1
        else:
            case_result.fail_num += 1
            case_result.result = InterfaceAPIResultEnum.ERROR

        return all_success

    async def _execute_loop_items(
        self,
        step_context: CaseStepContext,
        loop: Any,
        api_steps: List[Any],
        content_result: Any
    ) -> bool:
        """数组遍历循环"""
        all_success = True
        case_result = step_context.execution_context.case_result
        loop_count = 0
        success_count = 0
        fail_count = 0

        try:
            items = json.loads(loop.loop_items)
        except json.JSONDecodeError:
            items = [
                item.strip()
                for item in loop.loop_items.split(',')
                if item.strip()
            ]

        if items:
            total_apis = len(api_steps)
            for item in items:
                item_key = loop.loop_item_key
                for index, interface in enumerate(api_steps, start=1):
                    await step_context.starter.send(
                        f"✍️✍️  {'-' * 20} 执行数组循环步骤 "
                        f"[{item_key}:{item}] {index}/{total_apis}: "
                        f"{interface.name} {'-' * 20}"
                    )

                    interface_result, success = await self.interface_executor.execute(
                        interface=interface,
                        env=step_context.execution_context.env,
                        case_result=case_result,
                        temp_var={
                            ExtractTargetVariablesEnum.KEY: item_key,
                            ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.LOOP,
                            ExtractTargetVariablesEnum.VALUE: item
                        }
                    )

                    await result_writer.write_interface_result(
                        interface_result=InterfaceResult(**interface_result),
                        content_result_id=content_result.id
                    )

                    loop_count += 1
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        all_success = False

                    if loop.loop_interval > 0:
                        await asyncio.sleep(loop.loop_interval)

        await result_writer.update_step_result(
            result_id=content_result.id,
            result=all_success,
            status="SUCCESS" if all_success else "FAIL",
            loop_count=loop_count,
            success_count=success_count,
            fail_count=fail_count,
            loop_items=items,
        )

        if all_success:
            case_result.success_num += 1
        else:
            case_result.fail_num += 1
            case_result.result = InterfaceAPIResultEnum.ERROR

        return all_success

    async def _execute_loop_condition(
        self,
        step_context: CaseStepContext,
        loop: Any,
        api_steps: List[Any],
        content_result: Any
    ) -> bool:
        """条件循环"""
        exec_condition = ConditionManager(
            step_context.variable_manager.vars
        )
        n = 0
        loop_success = True
        case_result = step_context.execution_context.case_result
        loop_count = 0
        success_count = 0
        fail_count = 0

        max_loop = min(loop.max_loop, MAX_LOOP_LIMIT)

        while n < max_loop:
            n += 1

            for index, interface in enumerate(api_steps, start=1):
                await step_context.starter.send(
                    f"✍️✍️  {'-' * 20} 执行循环步骤  {n} times: "
                    f"{interface.name} {'-' * 20}"
                )

                interface_result, success = await self.interface_executor.execute(
                    interface=interface,
                    env=step_context.execution_context.env,
                    case_result=case_result
                )

                await result_writer.write_interface_result(
                    interface_result=InterfaceResult(**interface_result),
                    content_result_id=content_result.id
                )

                loop_count += 1
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    loop_success = False

                if loop.loop_interval > 0:
                    await asyncio.sleep(loop.loop_interval)

            key = await step_context.variable_manager.trans(loop.key)
            value = await step_context.variable_manager.trans(loop.value)
            log.info(f"__loop_condition  key = {key}")
            log.info(f"__loop_condition  value = {value}")
            log.info(f"__loop_condition  operate = {loop.operate}")

            try:
                MyAsserts.option(
                    assertOpt=loop.operate,
                    expect=key,
                    actual=value
                )
                loop_success = True
                break
            except AssertionError:
                await step_context.starter.send(
                    f"✍️✍️  执行循环步骤  {n} times: 断言失败 "
                    f"key = {key} type = {type(key)}  "
                    f"value = {value} type = {type(value)}"
                )
                continue

        await result_writer.update_step_result(
            result_id=content_result.id,
            result=loop_success,
            status="SUCCESS" if loop_success else "FAIL",
            loop_count=loop_count,
            success_count=success_count,
            fail_count=fail_count,
        )

        if loop_success:
            case_result.success_num += 1
        else:
            case_result.fail_num += 1
            case_result.result = InterfaceAPIResultEnum.ERROR

        return loop_success
