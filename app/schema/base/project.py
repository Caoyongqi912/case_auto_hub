#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/26
# @Author : cyq
# @File : project
# @Software: PyCharm
# @Desc: 项目相关的Schema定义
from typing import Optional
from pydantic import BaseModel, Field

from app.schema import PageSchema


class ProjectField(BaseModel):
    """项目基础字段模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    title: Optional[str] = Field(None, description="标题")
    desc: Optional[str] = Field(None, description="描述")
    chargeId: Optional[int] = Field(None, description="负责人ID")
    chargeName: Optional[str] = Field(None, description="负责人名称")


class InsertProjectSchema(BaseModel):
    """插入项目模型"""
    title: str = Field(..., description="标题")
    desc: str = Field(..., description="描述")
    chargeId: int = Field(..., description="负责人ID")


class UpdateProjectSchema(ProjectField):
    """更新项目模型"""
    pass


class DeleteProjectSchema(BaseModel):
    """删除项目模型"""
    projectId: int = Field(..., description="项目ID")


class PageProjectSchema(ProjectField, PageSchema):
    """项目分页查询模型"""
    pass
