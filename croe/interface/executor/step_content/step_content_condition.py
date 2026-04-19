#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : condition
# @Software: PyCharm
# @Desc: 条件步骤执行策略

from datetime import datetime
from app.mapper.interfaceApi.interfaceConditionMapper import InterfaceConditionMapper
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.a_manager import ConditionManager
from croe.interface.writer import result_writer
from enums import InterfaceAPIResultEnum
from enums.CaseEnum import CaseStepContentType



class APIConditionContentStrategy(StepBaseStrategy):
    """条件步骤执行器"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行条件步骤

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

        condition_content_result = await result_writer.write_step_result(
            content_type=CaseStepContentType.STEP_API_CONDITION,
            case_result_id=step_context.execution_context.case_result.id,
            task_result_id=task_result_id,
            content_id=step_context.content.id,
            content_name=step_context.content.resolved_content_name,
            content_desc=step_context.content.content_desc,
            content_step=step_context.index,
            success=False,
            start_time=start_time,
            use_time="",
            condition_result=condition_passed,
            condition_key=content_condition.get("key"),
            condition_value=content_condition.get("value"),
            condition_operator=content_condition.get("operator"),
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
                await result_writer.update_step_result(
                    result_id=condition_content_result.id,
                    result=True,
                    status="SUCCESS",
                )
                case_result.success_num += 1
                await result_writer.update_case_progress(case_result)
                return True

            total_apis = len(condition_api_list)
            for index, interface in enumerate(condition_api_list, start=1):
                await step_context.starter.send(
                    f"✍️✍️  {'-' * 20} 执行条件步骤 "
                    f"{index}/{total_apis}: {interface.interface_name} {'-' * 20}"
                )

                interface_result, success = await self.interface_executor.execute(
                    interface=interface,
                    env=step_context.execution_context.env,
                )

                await result_writer.write_interface_result(
                    interface_result=InterfaceResult(**interface_result),
                    content_result_id=condition_content_result.id
                )

                if not success:
                    await step_context.starter.send(
                        f"✍️✍️  步骤 {index}/{total_apis} 执行失败，停止后续执行"
                    )
                    case_result.result = InterfaceAPIResultEnum.ERROR
                    case_result.fail_num += 1

                    await result_writer.update_step_result(
                        result_id=condition_content_result.id,
                        result=False,
                        status="FAIL",
                    )
                    await result_writer.update_case_progress(case_result)
                    return False

            await result_writer.update_step_result(
                result_id=condition_content_result.id,
                result=True,
                status="SUCCESS",
            )
            case_result.success_num += 1
            await result_writer.update_case_progress(case_result)
            return True
        else:
            await step_context.starter.send(
                "✍️✍️  执行条件判断未通过 ❌❌  跳过子步骤"
            )
            case_result.success_num += 1

            await result_writer.update_step_result(
                result_id=condition_content_result.id,
                result=True,
                status="SUCCESS",
            )
            await result_writer.update_case_progress(case_result)
            return True
