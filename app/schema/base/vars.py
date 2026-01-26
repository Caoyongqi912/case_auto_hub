#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/1/23
# @Author : cyq
# @File : vars
# @Software: PyCharm
# @Desc: 变量相关的Schema定义
from typing import Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema


class AddVarsSchema(BaseModel):
    """添加变量模型"""
    case_id: int = Field(..., description="用例ID")
    key: str = Field(..., description="键")
    value: str = Field(..., description="值")


class UpdateVarsSchema(BaseModel):
    """更新变量模型"""
    uid: str = Field(..., description="唯一标识")
    key: Optional[str] = Field(None, description="键")
    value: Optional[str] = Field(None, description="值")


class DeleteVarsSchema(BaseModel):
    """删除变量模型"""
    uid: str = Field(..., description="唯一标识")


class PageVarsSchema(PageSchema):
    """变量分页查询模型"""
    case_id: int = Field(..., description="用例ID")


class QueryVarsSchema(BaseModel):
    """查询变量模型"""
    case_id: int = Field(..., description="用例ID")