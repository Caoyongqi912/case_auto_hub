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

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.mapper.interfaceApi.interfaceLoopMapper import InterfaceLoopMapper
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.a_manager import ConditionManager
from croe.interface.writer import write_interface_result
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

        设计说明：
        1. 创建 LoopStepContentResult（初始状态）
        2. 根据循环类型执行不同的循环逻辑
        3. 更新 LoopStepContentResult 统计信息

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

        loop_content_result = await write_case_step_content_loop_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.execution_context.case_result.id,
            step_content=step_context.content,
            loop_type=loop.loop_type,
            start_time=start_time,
            interface_task_result_id=task_result_id,
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
        """
        次数循环

        全部执行完，不论对错
        全对 content result = true
        case success +1

        Args:
            step_context: 步骤执行上下文
            loop: 循环配置
            api_steps: API步骤列表
            content_result: 内容结果

        Returns:
            是否全部成功
        """
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

                await write_interface_result(
                    content_result_id=content_result.id,
                    **interface_result
                )

                loop_count += 1
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    all_success = False

                if loop.loop_interval > 0:
                    await asyncio.sleep(loop.loop_interval)

        await update_loop_content_result(
            result_id=content_result.id,
            success=all_success,
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
        """
        数组遍历循环

        Args:
            step_context: 步骤执行上下文
            loop: 循环配置
            api_steps: API步骤列表
            content_result: 内容结果

        Returns:
            是否全部成功
        """
        try:
            items = json.loads(loop.loop_items)
        except json.JSONDecodeError:
            items = [
                item.strip()
                for item in loop.loop_items.split(',')
                if item.strip()
            ]

        all_success = True
        case_result = step_context.execution_context.case_result
        loop_count = 0
        success_count = 0
        fail_count = 0

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

                    await write_interface_result(
                        content_result_id=content_result.id,
                        **interface_result
                    )

                    loop_count += 1
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        all_success = False

                    if loop.loop_interval > 0:
                        await asyncio.sleep(loop.loop_interval)

        await update_loop_content_result(
            result_id=content_result.id,
            success=all_success,
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
        """
        条件循环

        Args:
            step_context: 步骤执行上下文
            loop: 循环配置
            api_steps: API步骤列表
            content_result: 内容结果

        Returns:
            是否成功
        """
        exec_condition = ConditionManager(
            step_context.variable_manager.vars
        )
        n = 0
        loop_success = True
        case_result = step_context.execution_context.case_result
        loop_count = 0
        success_count = 0
        fail_count = 0
        break_reason = None

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

                await write_interface_result(
                    content_result_id=content_result.id,
                    **interface_result
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
                break_reason = "条件满足，退出循环"
                loop_success = True
                break
            except AssertionError:
                await step_context.starter.send(
                    f"✍️✍️  执行循环步骤  {n} times: 断言失败 "
                    f"key = {key} type = {type(key)}  "
                    f"value = {value} type = {type(value)}"
                )
                continue

        if n >= max_loop:
            break_reason = f"循环次数达到最大限制 {max_loop}"
            await step_context.starter.send(
                f"✍️✍️  执行循环步骤  {n} times: {break_reason}"
            )

        await update_loop_content_result(
            result_id=content_result.id,
            success=loop_success,
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


async def write_case_step_content_loop_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    loop_type: int,
    start_time: datetime,
    interface_task_result_id: Optional[int] = None,
):
    """
    写入循环步骤内容结果（初始状态）

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        loop_type: 循环类型
        start_time: 开始时间
        interface_task_result_id: 任务执行结果ID（可选）

    Returns:
        LoopStepContentResult: 创建的循环步骤内容结果实例
    """
    return await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_LOOP,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=None,
        status="RUNNING",
        start_time=start_time,
        loop_count=0,
        loop_type=loop_type,
        success_count=0,
        fail_count=0,
    )


async def update_loop_content_result(
    result_id: int,
    success: bool,
    loop_count: int,
    success_count: int,
    fail_count: int,
    loop_items: Optional[list] = None,
) -> None:
    """
    更新循环步骤内容结果

    Args:
        result_id: 步骤内容结果ID
        success: 是否成功
        loop_count: 循环次数
        success_count: 成功次数
        fail_count: 失败次数
        loop_items: 循环数据项（可选）
    """
    update_data = {
        "result": success,
        "status": "SUCCESS" if success else "FAIL",
        "loop_count": loop_count,
        "success_count": success_count,
        "fail_count": fail_count,
    }

    if loop_items is not None:
        update_data["loop_items"] = loop_items

    await InterfaceContentStepResultMapper.update_result(
        result_id=result_id,
        **update_data
    )
