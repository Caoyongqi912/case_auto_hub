#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/26
# @Author : cyq
# @File : interfaceGlobalSchema
# @Software: PyCharm
# @Desc: 接口全局变量相关的Schema定义
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema


class GlobalSchemaField(BaseModel):
    """全局变量基础字段模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    key: Optional[str] = Field(None, description="键")
    value: Optional[str] = Field(None, description="值")
    description: Optional[str] = Field(None, description="描述")
    project_id: Optional[int] = Field(None, description="项目ID")


class AddGlobalSchema(BaseModel):
    """添加全局变量模型"""
    key: str = Field(..., description="键")
    value: str = Field(..., description="值")
    project_id: int = Field(..., description="项目ID")


class UpdateGlobalSchema(BaseModel):
    """更新全局变量模型"""
    uid: str = Field(..., description="唯一标识")
    key: str = Field(..., description="键")
    value: str = Field(..., description="值")
    project_id: int = Field(..., description="项目ID")


class SetGlobalSchema(BaseModel):
    """设置全局变量模型"""
    uid: str = Field(..., description="唯一标识")


class PageGlobalSchema(PageSchema):
    """全局变量分页查询模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    key: Optional[str] = Field(None, description="键")
    value: Optional[str] = Field(None, description="值")
    description: Optional[str] = Field(None, description="描述")
    project_id: Optional[int] = Field(None, description="项目ID")
