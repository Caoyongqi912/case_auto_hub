#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : group
# @Software: PyCharm
# @Desc: API组步骤执行策略

from datetime import datetime
from typing import TYPE_CHECKING

from app.mapper.interfaceApi.interfaceGroupMapper import InterfaceGroupMapper
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.interface.writer import result_writer
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

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """
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

        content_result = await result_writer.write_step_result(
            content_type=CaseStepContentType.STEP_API_GROUP,
            case_result_id=step_context.execution_context.case_result.id,
            task_result_id=task_result_id,
            content_id=step_context.content.id,
            content_name=step_context.content.resolved_content_name,
            content_desc=step_context.content.content_desc,
            content_step=step_context.index,
            success=False,
            start_time=start_time,
            use_time="",
            total_api_num=total_api_num,
            success_api_num=0,
            fail_api_num=0,
        )

        case_result = step_context.execution_context.case_result
        all_success = True

        for index, interface in enumerate(interface_list, start=1):
            await step_context.starter.send(
                f"✍️✍️  EXECUTE GROUP STEP {index} : {interface}"
            )

            interface_result, success = await self.interface_executor.execute(
                interface=interface,
                env=step_context.execution_context.env,
            )

            await result_writer.write_interface_result(
                interface_result=InterfaceResult(**interface_result),
                content_result_id=content_result.id,
            )

            if success:
                success_api_num += 1
            else:
                fail_api_num += 1
                all_success = False
                break

        await result_writer.update_step_result(
            result_id=content_result.id,
            result=all_success,
            status="SUCCESS" if all_success else "FAIL",
            success_api_num=success_api_num,
            fail_api_num=fail_api_num,
            use_time=GenerateTools.calculate_time_difference(start_time.strftime("%Y-%m-%d %H:%M:%S")),
            total_api_num=total_api_num,
        )

        if all_success:
            case_result.success_num += 1
        else:
            case_result.result = InterfaceAPIResultEnum.ERROR
            case_result.fail_num += 1

        await result_writer.update_case_progress(case_result)

        return all_success
