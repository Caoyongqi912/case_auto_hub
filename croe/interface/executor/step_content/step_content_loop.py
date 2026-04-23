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
from typing import List, Optional, Any, Dict, Tuple

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
        log.info(f'loop info {loop}')
        if not loop:
            await step_context.starter.send(
                f"未找到循环配置: id={step_context.content.target_id}"
            )
            return False

        start_time = datetime.now()
        loop_content_result = await result_writer.write_step_result(
            content_type=CaseStepContentType.STEP_LOOP,
            case_result_id=step_context.case_result_id,
            task_result_id=step_context.task_result_id,
            content_id=step_context.content.id,
            content_name=step_context.content.resolved_content_name,
            content_desc=step_context.content.content_desc,
            content_step=step_context.index,
            success=True,
            start_time=start_time,
            use_time="",
            loop_count=0,
            loop_type=loop.loop_type,
            success_count=0,
            fail_count=0,
        )
        loop_steps = await InterfaceLoopMapper.query_interfaces_by_loop_id(
            loop_id=step_context.content.target_id
        )
        log.info(f'loop_steps info {loop_steps}')
        if not loop_steps:
            return True
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

    async def _execute_api_step(
        self,
        step_context: CaseStepContext,
        interface: Any,
        step_num: int,
        total_steps: int,
        prefix: str,
        content_result: Any,
    ) -> Tuple[bool, int, int]:
        """
        执行单个API步骤并记录结果

        Args:
            step_context: 步骤执行上下文
            interface: 接口对象
            step_num: 当前步骤序号
            total_steps: 总步骤数
            prefix: 日志前缀描述
            content_result: 循环步骤结果ID
            temp_var: 临时变量（用于数组循环）

        Returns:
            (是否成功, success_count, fail_count)
        """
        success_count = 0
        fail_count = 0
        all_success = True

        await step_context.starter.send(
            f"✍️✍️  {'-' * 20} {prefix} "
            f"{step_num}/{total_steps}: "
            f"{interface.interface_name} {'-' * 20}"
        )

        interface_result, success = await self.interface_executor.execute(
            interface=interface,
            env=step_context.execution_context.env
        )

        try:
            await result_writer.write_interface_result(
                interface_result=InterfaceResult(**interface_result),
                content_result_id=content_result.id
            )
        except Exception as e:
            log.error(f"写入接口结果失败: {e}")

        if success:
            success_count = 1
        else:
            fail_count = 1
            all_success = False

        return all_success, success_count, fail_count

    async def _execute_loop_times(
        self,
        step_context: CaseStepContext,
        loop: Any,
        api_steps: List[Any],
        content_result: Any
    ) -> bool:
        """
        次数循环 - 按照指定次数循环执行API步骤

        Args:
            step_context: 步骤执行上下文
            loop: 循环配置对象
            api_steps: API步骤列表
            content_result: 循环步骤结果

        Returns:
            是否全部执行成功
        """
        all_success = True
        case_result = step_context.execution_context.case_result
        loop_count = 0
        success_count = 0
        fail_count = 0


        for i in range(1, loop.loop_times+1):
            for index, interface in enumerate(api_steps, start=1):
                success, sc, fc = await self._execute_api_step(
                    step_context=step_context,
                    interface=interface,
                    step_num=index,
                    total_steps=len(api_steps),
                    prefix=f"次数循环步骤 次数{i}",
                    content_result=content_result
                )

                loop_count += 1
                success_count += sc
                fail_count += fc
                if not success:
                    all_success = False

                if loop.loop_interval > 0:
                    await asyncio.sleep(loop.loop_interval)

        await self._update_loop_result(
            content_result=content_result,
            all_success=all_success,
            loop_count=loop_count,
            success_count=success_count,
            fail_count=fail_count,
            case_result=case_result
        )

        return all_success

    async def _execute_loop_items(
        self,
        step_context: CaseStepContext,
        loop: Any,
        api_steps: List[Any],
        content_result: Any
    ) -> bool:
        """
        数组遍历循环 - 遍历数组元素执行API步骤

        Args:
            step_context: 步骤执行上下文
            loop: 循环配置对象
            api_steps: API步骤列表
            content_result: 循环步骤结果

        Returns:
            是否全部执行成功
        """
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
        log.info(f'_execute_loop_items {items}')
        if not items:
            await self._update_loop_result(
                content_result=content_result,
                all_success=True,
                loop_count=0,
                success_count=0,
                fail_count=0,
                case_result=case_result
            )
            return True

        item_key = loop.loop_item_key
        total_apis = len(api_steps)

        for item in items:
            for index, interface in enumerate(api_steps, start=1):
                temp_var = {
                    ExtractTargetVariablesEnum.KEY: item_key,
                    ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.LOOP,
                    ExtractTargetVariablesEnum.VALUE: item
                }

                success, sc, fc = await self._execute_api_step(
                    step_context=step_context,
                    interface=interface,
                    step_num=index,
                    total_steps=total_apis,
                    prefix=f"执行数组循环步骤 [{item_key}:{item}]",
                    content_result=content_result,
                )

                loop_count += 1
                success_count += sc
                fail_count += fc
                if not success:
                    all_success = False

                if loop.loop_interval > 0:
                    await asyncio.sleep(loop.loop_interval)

        await self._update_loop_result(
            content_result=content_result,
            all_success=all_success,
            loop_count=loop_count,
            success_count=success_count,
            fail_count=fail_count,
            case_result=case_result,
            loop_items=items
        )

        return all_success

    async def _execute_loop_condition(
        self,
        step_context: CaseStepContext,
        loop: Any,
        api_steps: List[Any],
        content_result: Any
    ) -> bool:
        """
        条件循环 - 根据条件判断是否继续循环

        Args:
            step_context: 步骤执行上下文
            loop: 循环配置对象
            api_steps: API步骤列表
            content_result: 循环步骤结果

        Returns:
            是否全部执行成功
        """
        all_success = True
        case_result = step_context.execution_context.case_result
        loop_count = 0
        success_count = 0
        fail_count = 0

        max_loop = min(loop.max_loop, MAX_LOOP_LIMIT)

        for _ in range(max_loop):
            for index, interface in enumerate(api_steps, start=1):
                success, sc, fc = await self._execute_api_step(
                    step_context=step_context,
                    interface=interface,
                    step_num=index,
                    total_steps=len(api_steps),
                    prefix=f"执行循环步骤 {loop_count + 1} times",
                    content_result=content_result
                )

                loop_count += 1
                success_count += sc
                fail_count += fc
                if not success:
                    all_success = False

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
                all_success = True
                break
            except AssertionError:
                await step_context.starter.send(
                    f"✍️✍️  执行循环步骤 {loop_count} times: 断言失败 "
                    f"key = {key} type = {type(key)}  "
                    f"value = {value} type = {type(value)}"
                )
                continue

        await self._update_loop_result(
            content_result=content_result,
            all_success=all_success,
            loop_count=loop_count,
            success_count=success_count,
            fail_count=fail_count,
            case_result=case_result
        )

        return all_success

    async def _update_loop_result(
        self,
        content_result: Any,
        all_success: bool,
        loop_count: int,
        success_count: int,
        fail_count: int,
        case_result: Any,
        loop_items: Optional[List] = None
    ) -> None:
        """
        更新循环步骤结果并更新用例执行结果

        Args:
            content_result: 循环步骤结果对象
            all_success: 是否全部成功
            loop_count: 循环总次数
            success_count: 成功次数
            fail_count: 失败次数
            case_result: 用例执行结果
            loop_items: 数组循环的items列表（可选）
        """
        await result_writer.update_step_result(
            result_id=content_result.id,
            result=all_success,
            status="SUCCESS" if all_success else "FAIL",
            loop_count=loop_count,
            success_count=success_count,
            fail_count=fail_count,
            loop_items=loop_items
        )

        if all_success:
            case_result.success_num += 1
        else:
            case_result.fail_num += 1
            case_result.result = InterfaceAPIResultEnum.ERROR

        await result_writer.update_case_progress(case_result)