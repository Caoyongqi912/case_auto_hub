#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/2/17
# @Author : cyq
# @File : dbConfigSchema
# @Software: PyCharm
# @Desc: 数据库配置相关的Schema定义
from typing import Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema


class DBConfigField(BaseModel):
    """数据库配置基础字段模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    db_name: Optional[str] = Field(None, description="数据库名称")
    db_type: Optional[int] = Field(None, description="数据库类型")
    db_host: Optional[str] = Field(None, description="数据库主机")
    db_port: Optional[int] = Field(None, description="数据库端口")
    db_username: Optional[str] = Field(None, description="数据库用户名")
    db_password: Optional[str] = Field(None, description="数据库密码")
    db_database: Optional[str] = Field(None, description="数据库名称")
    project_id: Optional[int] = Field(None, description="项目ID")


class InsertDBConfigSchema(DBConfigField):
    """插入数据库配置模型"""
    db_name: str = Field(..., description="数据库名称")
    db_type: int = Field(..., description="数据库类型")
    db_host: str = Field(..., description="数据库主机")
    db_port: int = Field(..., description="数据库端口")
    db_username: str = Field(..., description="数据库用户名")
    db_database: str = Field(..., description="数据库名称")
    project_id: int = Field(..., description="项目ID")


class TestDBConfigSchema(DBConfigField):
    """测试数据库配置模型"""
    db_name: str = Field(..., description="数据库名称")
    db_type: int = Field(..., description="数据库类型")
    db_host: str = Field(..., description="数据库主机")
    db_port: int = Field(..., description="数据库端口")
    db_username: str = Field(..., description="数据库用户名")
    db_database: str = Field(..., description="数据库名称")


class TryDBConfigSchema(BaseModel):
    """尝试数据库配置模型"""
    db_id: int = Field(..., description="数据库ID")
    script: str = Field(..., description="脚本")


class PageDBConfigSchema(DBConfigField, PageSchema):
    """数据库配置分页查询模型"""
    pass


class SetByDBConfigIdSchema(DBConfigField):
    """根据数据库配置ID设置模型"""
    uid: str = Field(..., description="唯一标识")