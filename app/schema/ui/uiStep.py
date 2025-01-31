#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/10/15# @Author : cyq# @File : uiStep# @Software: PyCharm# @Desc:from typing import List, Mapping, Anyfrom pydantic import BaseModelfrom app.schema import PageSchemaclass UIStepField(BaseModel):    id: int | None    uid: str | None    name: str | None    description: str | None    method: str | None    locator: str | None    value: str | None    iframe_name: str | None    new_page: bool = None    is_ignore: bool = None    creator: int | None    creatorName: str | None    is_common_step: bool | Noneclass AddUICaseStep(UIStepField):    case_id: int | None    name: str    description: str    new_page: bool = False    is_ignore: bool = False    creator: int | None    creatorName: str | None    is_common_step: bool = Falseclass PutUICaseStep(UIStepField):    id: intclass PageUICaseStep(UIStepField, PageSchema):    ...class RemoveUIStepSchema(BaseModel):    stepId: int    caseId: int = Noneclass ReOrderUIStepSchema(BaseModel):    stepIds: List[int]    caseId: intclass CopyUIStepSchema(BaseModel):    stepId: int    caseId: intclass AddUICaseStepApiSchema(BaseModel):    b_or_a: int    name: str    description: str | None    url: str    method: str    stepId: int    go_on: int = 1    extracts: List[Mapping[str, Any] | None] | None    params: List[Mapping[str, Any] | None] | None    asserts: List[Mapping[str, Any] | None] | None    body: Mapping[str, Any] | None    body_type: int = 0class UpdateUICaseStepApiSchema(BaseModel):    uid: str    b_or_a: int | None    go_on: int | None    name: str | None    description: str | None    url: str | None    method: str | None    stepId: int | None    extracts: List[Mapping[str, Any] | None] | None    params: List[Mapping[str, Any] | None] | None    asserts: List[Mapping[str, Any] | None] | None    body: Mapping[str, Any] | None    body_type: int | Noneclass DeleteUICaseStepApiSchema(BaseModel):    uid: strclass AddUICaseStepSqlSchema(BaseModel):    sql_str: str    stepId: int    b_or_a: int    env_id: int    description: str | Noneclass UpdateUICaseStepSqlSchema(BaseModel):    uid: str    sql_str: str | None    b_or_a: int | None    env_id: int | None    description: str | Noneclass RemoveUICaseStepSqlSchema(BaseModel):    uid: strclass AddSubStepConditionSchema(BaseModel):    stepId: int    key: str    value: str    operator: intclass AddStepSchema(BaseModel):    stepId: int    name: str    description: str | None    method: str    locator: str | None    value: str | None    iframe_name: str | None    new_page: bool | None    is_ignore: bool | Noneclass UpdateStepSchema(BaseModel):    id: int    name: str | None    description: str | None    method: str | None    locator: str | None    value: str | None    iframe_name: str | None    new_page: bool | None    is_ignore: bool | Noneclass RemoveStepSchema(BaseModel):    id: intclass DetailStepSchema(BaseModel):    id: intclass ReorderSubStepSchema(BaseModel):    stepId: int    subIds: List[int]