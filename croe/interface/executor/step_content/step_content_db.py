#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : step_content_db
# @Software: PyCharm
# @Desc: 数据库步骤执行策略

from datetime import datetime
from typing import Optional, Dict, Any, List

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceContentStepResultMapper
)
from app.mapper.project.dbConfigMapper import DbConfigMapper, DBExecuteMapper
from app.model.interfaceAPIModel.contents import InterfaceCaseContents
from croe.interface.executor.context import CaseStepContext
from croe.interface.executor.step_content.base import StepBaseStrategy
from croe.interface.writer import result_writer
from enums import ExtractTargetVariablesEnum
from enums.CaseEnum import CaseStepContentType
from utils import log
from utils.execDBScript import ExecDBScript


class APIDBContentStrategy(StepBaseStrategy):
    """数据库步骤执行策略"""

    async def execute(self, step_context: CaseStepContext) -> bool:
        """
        执行数据库脚本 & 变量提取

        设计说明：
        1. 执行数据库脚本
        2. 提取变量
        3. 写入数据库结果到 DBStepContentResult

        Args:
            step_context: 步骤执行上下文

        Returns:
            是否执行成功
        """

        db_query_result = []
        success = True
        content_sql = await DBExecuteMapper.get_by_id(
            ident=step_context.content.target_id
        )
        if not content_sql:
            return True

        db_config = await DbConfigMapper.get_by_id(ident=content_sql.db_id)
        if not db_config:
            await step_context.starter.send(
                f"数据库配置不存在，db_id = {content_sql.db_id}"
            )
            return False

        db_script_text = await step_context.variable_manager.trans(
            content_sql.sql_text.strip()
        )
        log.info(f"执行前sql处理: {db_script_text}")

        db_script = ExecDBScript(
            io=step_context.starter,
            script_str=db_script_text,
            extracts=content_sql.sql_extracts
        )


        result = await db_script.invoke(
            db_config.db_type, **db_config.config
        )
        await step_context.starter.send(
            f"🫳🫳    数据库读取 = {result}"
        )



        if result:
            await step_context.variable_manager.add_vars(result)
            db_query_result = [
                {
                    ExtractTargetVariablesEnum.KEY:k,
                    ExtractTargetVariablesEnum.VALUE:v,
                    ExtractTargetVariablesEnum.Target:ExtractTargetVariablesEnum.ContentSQL
                }
                for k,v in result.items()
            ]


        task_result_id = None
        if step_context.execution_context.task_result:
            task_result_id = step_context.execution_context.task_result.id

        await write_case_step_content_db_result(
            step_index=step_context.index,
            interface_case_result_id=step_context.execution_context.case_result.id,
            step_content=step_context.content,
            db_query_result=db_query_result,
            success=success,
            interface_task_result_id=task_result_id,
        )

        case_result = step_context.execution_context.case_result
        case_result.success_num += 1
        await result_writer.update_case_progress(case_result)

        return True


async def write_case_step_content_db_result(
    step_index: int,
    interface_case_result_id: int,
    step_content: InterfaceCaseContents,
    db_query_result:List[Dict[str, Any]],
    success: bool,
    interface_task_result_id: Optional[int] = None,
) -> None:
    """
    写入数据库步骤内容结果

    使用 InterfaceContentStepResultMapper.insert_result 方法，
    根据 content_type 自动创建对应的子类实例

    Args:
        step_index: 步骤索引
        interface_case_result_id: 用例执行结果ID
        step_content: 步骤内容实例
        db_query_result: 查询结果
        db_affected_rows: 影响行数
        db_error: 数据库错误
        success: 是否成功
        interface_task_result_id: 任务执行结果ID（可选）
    """
    await InterfaceContentStepResultMapper.insert_result(
        content_type=CaseStepContentType.STEP_API_DB,
        case_result_id=interface_case_result_id,
        task_result_id=interface_task_result_id,
        content_id=step_content.id,
        content_name=step_content.resolved_content_name,
        content_desc=step_content.content_desc,
        content_step=step_index,
        result=success,
        status="SUCCESS" if success else "FAIL",
        start_time=datetime.now(),
        db_query_result=db_query_result,
    )
