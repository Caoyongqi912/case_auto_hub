#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : testCaseSchema
# @Software: PyCharm
# @Desc: 测试用例相关的Schema定义
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum
from enums.CaseEnum import CaseLevel


class TestCaseStep(BaseModel):
    """测试用例步骤模型"""
    action: Optional[str] = Field(None, description="操作步骤")
    expected_result: Optional[str] = Field(None, description="预期结果")
    id: Optional[int] = Field(None, description="步骤ID")


class TestCaseField(BaseModel):
    """测试用例基础字段模型"""
    case_name: Optional[str] = Field(None, description="用例名称")
    case_level: Optional[str] = Field(CaseLevel.P2, description="用例级别")
    case_type: Optional[int] = Field(1, description="用例类型: 1'普通' | 2'冒烟' | 3 回归")
    case_tag: Optional[str] = Field(None, description="用例标签")
    case_setup: Optional[str] = Field(None, description="用例前置条件")
    case_status: Optional[int] = Field(0, description="用例状态")
    case_mark: Optional[str] = Field(None, description="用例备注")
    is_review: Optional[bool] = Field(False, description="是否审核")
    is_common: Optional[bool] = Field(False, description="是否公共用例")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")

    case_sub_steps: Optional[List[TestCaseStep]] = Field(None, description="用例子步骤")


class AddTestCaseSchema(TestCaseField):
    """添加测试用例模型"""
    requirement_id: Optional[int] = Field(None, description="需求ID")
    case_name: str = Field(..., description="用例名称")
    case_tag: str = Field(..., description="用例标签")
    case_mark: Optional[str] = Field(None, description="用例备注")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class InsertMindCaseSchema(BaseModel):
    """插入思维导图用例模型"""
    mind_node: dict = Field(..., description="思维导图节点")
    requirement_id: int = Field(..., description="需求ID")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class UpdateMindCaseSchema(BaseModel):
    """更新思维导图用例模型"""
    mind_node: Optional[dict] = Field(None, description="思维导图节点")
    id: int = Field(..., description="用例ID")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class UpdateTestCaseSchema(TestCaseField):
    """更新测试用例模型"""
    id: int = Field(..., description="用例ID")


class UpdateTestCaseStatusSchema(BaseModel):
    """更新测试用例状态模型"""
    id: int = Field(..., description="用例ID")
    case_status: int = Field(..., description="用例状态")


class PageTestCaseSchema(PageSchema, TestCaseField):
    """测试用例分页查询模型"""
    module_type: int = Field(ModuleEnum.CASE, description="模块类型")
    case_level: Optional[str] = Field(None, description="用例级别")
    case_type: Optional[int] = Field(None, description="用例类型")
    case_status: Optional[int] = Field(None, description="用例状态")
    is_review: Optional[bool] = Field(None, description="是否审核")


class QueryTestCaseSchemaByReq(BaseModel):
    """根据需求ID查询测试用例模型"""
    requirement_id: int = Field(..., description="需求ID")


class AddDefaultCaseSchema(QueryTestCaseSchemaByReq):
    """添加默认用例模型"""
    pass


class QueryTestCaseSchemaByField(BaseModel):
    """根据字段查询测试用例模型"""
    requirement_id: int = Field(..., description="需求ID")
    case_name: Optional[str] = Field(None, description="用例名称")
    case_level: Optional[str] = Field(None, description="用例级别")
    case_type: Optional[int] = Field(None, description="用例类型")
    case_tag: Optional[str] = Field(None, description="用例标签")
    case_status: Optional[int] = Field(None, description="用例状态")


class CopyCase(BaseModel):
    """复制用例模型"""
    case_id: int = Field(..., description="用例ID")
    requirement_id: Optional[int] = Field(None, description="需求ID")


class RemoveCaseSchema(BaseModel):
    """删除用例模型"""
    case_id: int = Field(..., description="用例ID")
    requirement_id: Optional[int] = Field(None, description="需求ID")


class CopyCaseStep(BaseModel):
    """复制用例步骤模型"""
    step_id: int = Field(..., description="步骤ID")


class ReorderCase(BaseModel):
    """重排序用例模型"""
    requirement_id: int = Field(..., description="需求ID")
    case_ids: List[int] = Field(..., description="用例ID列表")


class ReorderCaseStep(BaseModel):
    """重排序用例步骤模型"""
    step_ids: List[int] = Field(..., description="步骤ID列表")


class RemoveCaseStep(BaseModel):
    """删除用例步骤模型"""
    step_id: int = Field(..., description="步骤ID")


class AddDefaultCaseStep(BaseModel):
    """添加默认用例步骤模型"""
    case_id: int = Field(..., description="用例ID")


class UpdateTestCaseStep(BaseModel):
    """更新测试用例步骤模型"""
    id: int = Field(..., description="步骤ID")
    action: Optional[str] = Field(None, description="操作步骤")
    expected_result: Optional[str] = Field(None, description="预期结果")
    order: Optional[int] = Field(None, description="排序序号")


class SetCasesStatusSchema(BaseModel):
    """设置多个用例状态模型"""
    case_ids: List[int] = Field(..., description="用例ID列表")
    status: int = Field(..., description="状态值")


class SetCasesCommonSchema(BaseModel):
    """设置多个用例为公共用例模型"""
    case_ids: List[int] = Field(..., description="用例ID列表")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")
