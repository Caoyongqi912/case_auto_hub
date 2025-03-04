#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/7# @Author : cyq# @File : uiReport# @Software: PyCharm# @Desc:from typing import Listfrom pydantic import BaseModelfrom app.schema import PageSchemafrom enums import ModuleEnumclass UIReportField(BaseModel):    run_day: str | List = None    uid: str = None    id: int = None    status: str = None    result: str = None    start_by: int = None    starter_name: str = None    project_id: int = None    module_id: int = Noneclass PageTaskReportSchema(PageSchema, UIReportField):    task_name: str = None    task_id: int = Noneclass QueryCaseResultByBaseIdSchema(BaseModel):    baseId: int