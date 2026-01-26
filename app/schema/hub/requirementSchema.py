#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : requirementSchema
# @Software: PyCharm
# @Desc: 需求相关的Schema定义
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


class RequirementsField(BaseModel):
    """需求基础字段模型"""
    id: Optional[int] = Field(None, description="需求ID")
    uid: Optional[str] = Field(None, description="需求唯一标识")
    requirement_url: Optional[str] = Field(None, description="需求链接")
    requirement_name: Optional[str] = Field(None, description="需求名称")
    requirement_level: Optional[str] = Field(None, description="需求级别")
    process: Optional[int] = Field(None, description="需求进度")
    develops: Optional[List[int]] = Field(None, description="开发人员ID列表")
    maintainer: Optional[int] = Field(None, description="维护人员ID")
    case_number: Optional[int] = Field(0, description="用例数量")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class AddRequirementsSchema(BaseModel):
    """添加需求模型"""
    requirement_name: str = Field(..., description="需求名称")
    requirement_level: str = Field(..., description="需求级别")
    process: int = Field(5, description="需求进度")
    develops: Optional[List[int]] = Field(None, description="开发人员ID列表")
    maintainer: Optional[int] = Field(None, description="维护人员ID")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class UpdateRequirementsSchema(BaseModel):
    """更新需求模型"""
    id: int = Field(..., description="需求ID")
    requirement_name: Optional[str] = Field(None, description="需求名称")
    requirement_level: Optional[str] = Field(None, description="需求级别")
    process: Optional[int] = Field(None, description="需求进度")
    develops: Optional[List[int]] = Field(None, description="开发人员ID列表")
    maintainer: Optional[int] = Field(None, description="维护人员ID")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class RemoveRequirementsSchema(BaseModel):
    """删除需求模型"""
    requirement_id: int = Field(..., description="需求ID")


class GetRequirementsSchema(BaseModel):
    """获取需求模型"""
    requirement_id: int = Field(..., description="需求ID")


class PageRequirementsSchema(PageSchema):
    """需求分页查询模型"""
    module_type: int = Field(ModuleEnum.CASE, description="模块类型")
    requirement_name: Optional[str] = Field(None, description="需求名称")
    requirement_level: Optional[str] = Field(None, description="需求级别")
    process: Optional[int] = Field(None, description="需求进度")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")