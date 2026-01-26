#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/26
# @Author : cyq
# @File : interfaceGroupSchema
# @Software: PyCharm
# @Desc: 接口组相关的Schema定义
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


class InterfaceApiGroupFieldSchema(BaseModel):
    """接口组基础字段模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    name: Optional[str] = Field(None, description="名称")
    description: Optional[str] = Field(None, description="描述")
    api_num: int = Field(0, description="API数量")
    project_id: Optional[int] = Field(None, description="项目ID")
    module_id: Optional[int] = Field(None, description="模块ID")


class InsertInterfaceGroupSchema(InterfaceApiGroupFieldSchema):
    """插入接口组模型"""
    name: str = Field(..., description="名称")
    description: str = Field(..., description="描述")
    project_id: int = Field(..., description="项目ID")
    module_id: int = Field(..., description="模块ID")


class UpdateInterfaceGroupSchema(InterfaceApiGroupFieldSchema):
    """更新接口组模型"""
    id: int = Field(..., description="ID")


class RemoveInterfaceGroupSchema(InterfaceApiGroupFieldSchema):
    """删除接口组模型"""
    id: int = Field(..., description="ID")


class PageInterfaceGroupSchema(InterfaceApiGroupFieldSchema, PageSchema):
    """接口组分页查询模型"""
    module_type: int = Field(ModuleEnum.API, description="模块类型")


class AssociationAPIS2GroupSchema(BaseModel):
    """关联多个API到组模型"""
    apiIds: List[int] = Field(..., description="API ID列表")
    groupId: int = Field(..., description="组ID")


class AssociationAPI2GroupSchema(BaseModel):
    """关联单个API到组模型"""
    apiId: int = Field(..., description="API ID")
    groupId: int = Field(..., description="组ID")


class InterfaceGroupDetailSchema(BaseModel):
    """接口组详情模型"""
    groupId: int = Field(..., description="组ID")
