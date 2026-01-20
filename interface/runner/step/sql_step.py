#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @Software: PyCharm
# @Desc: SQL步骤执行器

from app.mapper.project.dbConfigMapper import DbConfigMapper
from app.mapper.interface.interfaceCaseMapper import InterfaceCaseContentDBExecuteMapper
from enums import InterfaceExtractTargetVariablesEnum
from utils import log
from utils.execDBScript import ExecDBScript
from .base import StepStrategy
from interface.writer import InterfaceAPIWriter


class SqlStepStrategy(StepStrategy):
    """SQL步骤执行器"""
    
    async def execute(self, step_context) -> bool:
        """执行SQL步骤"""
        content_sql = await InterfaceCaseContentDBExecuteMapper.get_by_id(ident=step_context.step.target_id)
        
        if not content_sql:
            return True
        
        _db = await DbConfigMapper.get_by_id(ident=content_sql.db_id)
        if not _db:
            log.warning(f"未找到数据库配置 ID: {content_sql.db_id}")
            return True
        
        script = await step_context.variable_manager.trans(content_sql.sql_text.strip())
        db_script = ExecDBScript(step_context.starter, script, content_sql.sql_extracts)
        res = await db_script.invoke(_db.db_type, **_db.config)
        await step_context.variable_manager.add_vars(res)
        
        await step_context.starter.send(f"🫳🫳    数据库读取 = {res}")
        
        vars_list = []
        if res:
            vars_list = [
                {
                    InterfaceExtractTargetVariablesEnum.KEY: k,
                    InterfaceExtractTargetVariablesEnum.VALUE: v,
                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.ContentSQL
                }
                for k, v in res.items()
            ]
        
        await InterfaceAPIWriter.set_case_step_content_api_db_result(
            step_index=step_context.step_index,
            interface_case_result_id=step_context.interface_case_result_id,
            step_content=step_context.step,
            starter=step_context.starter,
            interface_task_result_id=step_context.interface_task_result_id,
            script_vars=vars_list
        )
        return True
