#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/3
# @Author : cyq
# @File : playConfigSchema
# @Software: PyCharm
# @Desc: play配置相关的Schema定义
from typing import Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema


class AddPlayMethodSchema(BaseModel):
    """添加play方法模型"""
    label: str = Field(..., description="标签")
    value: str = Field(..., description="值")
    description: Optional[str] = Field(None, description="描述")
    need_locator: int = Field(..., description="是否需要定位器")
    need_value: int = Field(..., description="是否需要值")


class GetPlayMethodSchema(BaseModel):
    """获取play方法模型"""
    uid: str = Field(..., description="唯一标识")


class EditPlayMethodSchema(BaseModel):
    """编辑play方法模型"""
    uid: str = Field(..., description="唯一标识")
    label: Optional[str] = Field(None, description="标签")
    value: Optional[str] = Field(None, description="值")
    description: Optional[str] = Field(None, description="描述")
    need_locator: Optional[int] = Field(None, description="是否需要定位器")
    need_value: Optional[int] = Field(None, description="是否需要值")


class PagePlayMethodSchema(PageSchema):
    """play方法分页查询模型"""
    label: Optional[str] = Field(None, description="标签")
    value: Optional[str] = Field(None, description="值")
    need_locator: Optional[int] = Field(None, description="是否需要定位器")
    need_value: Optional[int] = Field(None, description="是否需要值")
