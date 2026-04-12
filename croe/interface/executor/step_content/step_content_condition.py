#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : condition
# @Software: PyCharm
# @Desc: 条件步骤执行策略

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.mapper.interfaceApi.interfaceConditionMapper import (
    InterfaceConditionMapper
)
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.a_manager import ConditionManager
from croe.interface.writer import write_interface_result
from enums import InterfaceAPIResultEnum
from enums.CaseEnum import CaseStepContentType
from utils import GenerateTools

if TYPE_CHECKING:
    from croe.interface.executor.interface_executor import InterfaceExecutor


class APIConditionContentStrategy(StepBaseStrategy):
    """条件步骤执行器"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行条件步骤

        设计说明：
        1. 执行条件判断
        2. 创建 ConditionStepContentResult
        3. 如果条件通过，执行关联的API列表
        4. 如果条件未通过，跳过子步骤

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
        start_time = datetime.now()
        condition = await InterfaceConditionMapper.get_by_id(
            ident=step_context.content.target_id
        )

        if not condition:
            await step_context.starter.send(
                f"未找到条件配置: id={step_context.content.target_id}"
            )
            return False

        condition_manager = ConditionManager(
            variable=step_context.variable_manager
        )

        condition_passed, content_condition = await condition_manager.invoke(
            condition, step_context.starter
        )

        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        condition_content_result = await write_case_step_content_condition_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.execution_context.case_result.id,
            step_content=step_context.content,
            content_condition=content_condition,
            condition_result=condition_passed,
            start_time=start_time,
            interface_task_result_id=task_result_id,
        )

        case_result = step_context.execution_context.case_result

        if condition_passed:
            await step_context.starter.send(
                "✍️✍️  执行条件判断通过 🎉🎉"
            )

            condition_api_list = await InterfaceConditionMapper.query_interfaces_by_condition_id(
                condition.id
            )

            if not condition_api_list:
                await update_condition_content_result(
                    result_id=condition_content_result.id,
                    success=True,
                )
                case_result.success_num += 1
                return True

            total_apis = len(condition_api_list)
            for index, interface in enumerate(condition_api_list, start=1):
                await step_context.starter.send(
                    f"✍️✍️  {'-' * 20} 执行条件步骤 "
                    f"{index}/{total_apis}: {interface.name} {'-' * 20}"
                )

                interface_result, success = await self.interface_executor.execute(
                    interface=interface,
                    env=step_context.execution_context.env,
                    case_result=case_result
                )

                await write_interface_result(
                    content_result_id=condition_content_result.id,
                    **interface_result
                )

                if not success:
                    await step_context.starter.send(
                        f"✍️✍️  步骤 {index}/{total_apis} 执行失败，停止后续执行"
                    )
                    case_result.result = InterfaceAPIResultEnum.ERROR
                    case_result.fail_num += 1

                    await update_condition_content_result(
                        result_id=condition_content_result.id,
                        success=False,
                    )
                    return False

            await update_condition_content_result(
                result_id=condition_content_result.id,
                success=True,
            )
            return True
        else:
            await step_context.starter.send(
                "✍️✍️  执行条件判断未通过 ❌❌  跳过子步骤"
            )
            case_result.success_num += 1

            await update_condition_content_result(
                result_id=condition_content_result.id,
                success=True,
            )
            return True


async def write_case_step_content_condition_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    content_condition: dict,
    condition_result: bool,
    start_time: datetime,
    interface_task_result_id: Optional[int] = None,
):
    """
    写入条件步骤内容结果（初始状态）

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        content_condition: 条件内容
        condition_result: 条件判断结果
        start_time: 开始时间
        interface_task_result_id: 任务执行结果ID（可选）

    Returns:
        ConditionStepContentResult: 创建的条件步骤内容结果实例
    """
    return await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_API_CONDITION,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=None,
        status="RUNNING",
        start_time=start_time,
        condition_result=condition_result,
        condition_key=content_condition.get("key"),
        condition_value=content_condition.get("value"),
        condition_operator=content_condition.get("operator"),
    )


async def update_condition_content_result(
    result_id: int,
    success: bool,
) -> None:
    """
    更新条件步骤内容结果

    Args:
        result_id: 步骤内容结果ID
        success: 是否成功
    """
    await InterfaceContentStepResultMapper.update_result(
        result_id=result_id,
        result=success,
        status="SUCCESS" if success else "FAIL",
    )
