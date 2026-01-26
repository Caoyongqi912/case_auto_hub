#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/4
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: hub模块导出
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


class CaseStepInfoSchema(BaseModel):
    """用例步骤信息模型"""
    id: Optional[int] = Field(None, description="步骤ID")
    step: int = Field(..., description="步骤序号")
    todo: str = Field(..., description="操作步骤")
    exp: str = Field(..., description="预期结果")


class CaseHubFields(BaseModel):
    """用例中心基础字段模型"""
    case_title: Optional[str] = Field(None, description="用例标题")
    case_level: Optional[str] = Field(None, description="用例级别")
    case_desc: Optional[str] = Field(None, description="用例描述")
    case_mark: Optional[str] = Field(None, description="用例备注")
    case_setup: Optional[str] = Field(None, description="用例前置条件")
    case_type: Optional[int] = Field(None, description="用例类型")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    case_creator: Optional[int] = Field(None, description="用例创建者")
    case_info: Optional[List[CaseStepInfoSchema]] = Field(None, description="用例步骤信息")


class InsertCaseSchema(CaseHubFields):
    """插入用例模型"""
    case_title: str = Field(..., description="用例标题")
    case_level: str = Field(..., description="用例级别")
    case_setup: str = Field(..., description="用例前置条件")
    case_type: int = Field(..., description="用例类型")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")
    case_info: List[CaseStepInfoSchema] = Field(..., description="用例步骤信息")


class UpdateCaseSchema(CaseHubFields):
    """更新用例模型"""
    id: int = Field(..., description="用例ID")


class PageCaseSchema(CaseHubFields, PageSchema):
    """用例分页查询模型"""
    module_type: int = Field(ModuleEnum.CASE, description="模块类型")


class GetCaseSchema(BaseModel):
    """获取用例模型"""
    caseId: int = Field(..., description="用例ID")


__all__ = [
    "InsertCaseSchema",
    "UpdateCaseSchema",
    "PageCaseSchema",
    "GetCaseSchema"
]