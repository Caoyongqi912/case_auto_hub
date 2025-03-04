#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/10/9# @Author : cyq# @File : uiTask# @Software: PyCharm# @Desc:from pydantic import BaseModel, validatorfrom app.schema import BaseSchema, PageSchemafrom app.schema.ui.uiCase import UICaseFieldfrom enums import ModuleEnumclass UITaskField(BaseModel):    project_id: int | None    module_id: int | None    uid: str | None    title: str | None    level: str | None    status: str | None    creatorName: str | Noneclass PageTaskSchema(UITaskField, PageSchema):    module_type = ModuleEnum.UI_TASKclass PageTaskCaseSchema(UICaseField, PageSchema):    taskId: strclass AddTaskCaseSchema(BaseModel):    taskId: int    caseIdList: list[int]class ReorderTaskCaseSchema(BaseModel):    taskId: int    caseIdList: list[int]class RemoveTaskCaseSchema(BaseModel):    taskId: int    caseId: intclass RemoveTaskSchema(BaseModel):    taskId: strclass QueryTaskCasesSchema(BaseModel):    taskId: strclass ExecuteTaskCasesSchema(BaseModel):    taskId: intclass UpdateTaskSchema(BaseModel):    id: str    module_id: int | None = None    project_id: int | None = None    description: str | None = None    is_auto: bool | None = None    is_send: bool | None = None    cron: str | None = None    level: str | None = None    status: str | None = None    retry: int | None = None    switch: bool | None = None    title: str | None = None    send_type: str | None = None    send_key: str | None = Noneclass NewTaskSchema(BaseModel):    module_id: int    project_id: int    description: str    is_auto: bool = False    is_send: bool = False    switch: bool = False    send_type: str | None = None    send_key: str | None = None    cron: str | None = None    level: str = "P1"    status: str = "WAIT"    retry: int = 0    title: str    ui_case_num: int = 0class SetTaskSwitch(BaseModel):    jobId: str    switch: bool