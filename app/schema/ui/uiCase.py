#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/21# @Author : cyq# @File : uiCase# @Software: PyCharm# @Desc:import enumfrom typing import List, Mapping, Anyfrom pydantic import BaseModel, Field, validatorfrom app.schema import PageSchemafrom enums.CaseEnum import CaseStatus, CaseLevelfrom utils import GenerateToolsclass AddUICaseBaseSchema(BaseModel):    title: str    description: str    level: str = Field(..., title="用例等级")    status: str = Field(..., title="用例状态")    env_id: str    step_num: int = 0    part_id: int    project_id: int    @validator('level')    def level_must_be_valid(cls, v):        if v is not None:            try:                return CaseLevel[v].value            except KeyError:                raise ValueError(f"Invalid level: {v}")        return v    @validator('status')    def status_must_be_valid(cls, v):        if v is not None:            try:                return CaseStatus[v].value            except KeyError:                raise ValueError(f"Invalid status: {v}")        return vclass EditUICaseBaseSchema(BaseModel):    id: int    title: str | None    description: str | None    level: str | None    status: str | None    env_id: str | None    part_id: int | None    project_id: int | Noneclass OPTUICaseBaseSchema(BaseModel):    caseId: int | strclass ChoiceUICaseBaseSchema(BaseModel):    caseId: int    choices: List[int]class UICaseField(BaseModel):    id: int | None    title: str | None    uid: str | None    part_id: int | None    project_id: int | None    creator: int | None    creatorName: str | None    status: CaseStatus | None    level: CaseLevel | None    env_id: str | None    env_name: str | Noneclass UISearchByDate(BaseModel):    projectId: int    st: str | None = GenerateTools.getMonthFirst(),    et: str | None = GenerateTools.getTime(2)class GetOrDeleteUICaeVariable(BaseModel):    uid: strclass InsertUICaseVariable(BaseModel):    key: str    value: str    caseId: int    creator: intclass UpdateUICaseVariable(BaseModel):    uid: str    key: str | None    value: str | None    updater: int | Noneclass UICasePage(PageSchema, UICaseField):    sort: dict | Noneclass UIVariablesPage(PageSchema):    caseId: intclass RunUITaskByJK(BaseModel):    taskIds: List[int]    userId: int    jobName: str | None = Noneclass AddUICaseStepWithGroup(BaseModel):    caseId: int    groupIds: List[int]class ExecuteUICaseSchema(BaseModel):    caseId: int