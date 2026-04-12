#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : group
# @Software: PyCharm
# @Desc: API组步骤执行策略

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.mapper.interfaceApi.interfaceGroupMapper import InterfaceGroupMapper
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.interface.executor.context import CaseStepContext
from croe.interface.writer import write_interface_result
from enums import InterfaceAPIResultEnum
from enums.CaseEnum import CaseStepContentType
from utils import GenerateTools

if TYPE_CHECKING:
    from croe.interface.executor.interface_executor import InterfaceExecutor


class APIGroupContentStrategy(StepBaseStrategy):
    """API组步骤执行策略"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行API组步骤

        设计说明：
        1. 先创建 GroupStepContentResult（获取 ID）
        2. 循环执行每个接口，创建 interface_result 并关联到 GroupStepContentResult
        3. 最后更新 GroupStepContentResult 的统计信息

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
        all_success = True
        interface_list = await InterfaceGroupMapper.query_association_interfaces(
            group_id=step_context.content.target_id
        )

        if not interface_list:
            return True

        start_time = datetime.now()
        total_api_num = len(interface_list)
        success_api_num = 0
        fail_api_num = 0

        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        group_content_result = await write_case_step_content_group_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.execution_context.case_result.id,
            step_content=step_context.content,
            total_api_num=total_api_num,
            start_time=start_time,
            interface_task_result_id=task_result_id,
        )

        case_result = step_context.execution_context.case_result

        for index, interface in enumerate(interface_list, start=1):
            await step_context.starter.send(
                f"✍️✍️  EXECUTE GROUP STEP {index} : {interface}"
            )

            interface_result, success = await self.interface_executor.execute(
                interface=interface,
                env=step_context.execution_context.env,
                case_result=case_result
            )

            await write_interface_result(
                content_result_id=group_content_result.id,
                **interface_result
            )

            if success:
                success_api_num += 1
            else:
                fail_api_num += 1
                all_success = False
                break

        await update_group_content_result(
            result_id=group_content_result.id,
            success=all_success,
            success_api_num=success_api_num,
            fail_api_num=fail_api_num,
            use_time=GenerateTools.calculate_time_difference(start_time),
        )

        if all_success:
            case_result.success_num += 1
        else:
            case_result.result = InterfaceAPIResultEnum.ERROR
            case_result.fail_num += 1

        return all_success


async def write_case_step_content_group_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    total_api_num: int,
    start_time: datetime,
    interface_task_result_id: Optional[int] = None,
):
    """
    写入 Group 步骤内容结果（初始状态）

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        total_api_num: 总接口数量
        start_time: 开始时间
        interface_task_result_id: 任务执行结果ID（可选）

    Returns:
        GroupStepContentResult: 创建的 Group 步骤内容结果实例
    """
    return await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_API_GROUP,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=None,
        status="RUNNING",
        start_time=start_time,
        total_api_num=total_api_num,
        success_api_num=0,
        fail_api_num=0,
    )


async def update_group_content_result(
    result_id: int,
    success: bool,
    success_api_num: int,
    fail_api_num: int,
    use_time: str,
) -> None:
    """
    更新 Group 步骤内容结果

    Args:
        result_id: 步骤内容结果ID
        success: 是否成功
        success_api_num: 成功接口数量
        fail_api_num: 失败接口数量
        use_time: 执行用时
    """
    await InterfaceContentStepResultMapper.update_result(
        result_id=result_id,
        result=success,
        status="SUCCESS" if success else "FAIL",
        success_api_num=success_api_num,
        fail_api_num=fail_api_num,
        use_time=use_time,
    )
