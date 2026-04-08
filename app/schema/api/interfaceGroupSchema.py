#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : interfaceGroupSchema
# @Software: PyCharm
# @Desc:
from typing import Optional, List

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


__all__ = [
    "InsertInterfaceGroupSchema",
    "UpdateInterfaceGroupSchema",
    "GetInterfaceGroupSchema",
    "PageInterfaceGroupSchema",
    "AssociationInterfacesToGroupSchema",
    "OptInterfaceGroupSchema"
]

class InsertInterfaceGroupSchema(BaseModel):
    """插入接口组模型"""
    interface_group_name: str = Field(..., description="名称")
    interface_group_desc: str = Field(..., description="描述")

    project_id: int = Field(..., description="项目ID")
    module_id: int = Field(..., description="模块ID")


class UpdateInterfaceGroupSchema(BaseModel):
    """更新接口组模型"""
    id: int = Field(..., description="ID")
    interface_group_name: Optional[str] = Field(None, description="名称")
    interface_group_desc: Optional[str] = Field(None, description="描述")
    project_id: Optional[int] = Field(None, description="项目ID")
    module_id: Optional[int] = Field(None, description="模块ID")


class GetInterfaceGroupSchema(BaseModel):
    """查询接口组模型"""
    id: int = Field(..., description="ID")


class PageInterfaceGroupSchema( PageSchema):
    """接口组分页查询模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    interface_group_name: Optional[str] = Field(None, description="名称")
    module_type: int = Field(ModuleEnum.API, description="模块类型")


class AssociationInterfacesToGroupSchema(BaseModel):
    """关联多个接口到组模型"""
    interface_ids: List[int] = Field(..., description="API ID列表")
    group_id: int = Field(..., description="组ID")


class OptInterfaceGroupSchema(BaseModel):
    """复制 关联 排序接口组模型"""
    interface_id: int = Field(..., description="接口 ID")
    group_id: int = Field(..., description="组ID")
