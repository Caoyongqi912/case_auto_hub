#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/16
# @Author : cyq
# @File : interfaceResultSchema
# @Software: PyCharm
# @Desc: 接口结果字段模型

from pydantic import BaseModel, Field
from typing import Optional
from app.schema import PageSchema


class InterfaceResultFieldSchema(BaseModel):
    """接口结果字段模型"""
    uid: Optional[str] = Field(None, description="UID")
    interface_id: Optional[int] = Field(None, description="接口ID")
    interface_name: Optional[str] = Field(None, description="接口名称")
    interface_uid: Optional[str] = Field(None, description="接口唯一标识")

    project_id: Optional[int] = Field(None, description="接口项目ID")
    module_id: Optional[int] = Field(None, description="接口模块ID")
    interface_env_id: Optional[int] = Field(None, description="接口环境ID")
    starter_id: Optional[int] = Field(None, description="开始者ID")
    result: Optional[bool] = Field(None, description="结果")
    case_result_id: Optional[int] = Field(None, description="接口用例结果ID")
    task_result_id: Optional[int] = Field(None, description="接口任务结果ID")


class InterfaceCaseResultFieldSchema(BaseModel):
    """接口用例结果字段模型"""
    uid: Optional[str] = Field(None, description="UID")

    interface_case_id: Optional[int] = Field(None, description="接口用例ID")
    interface_case_name: Optional[str] = Field(None, description="接口用例名称")
    interface_case_uid: Optional[str] = Field(None, description="接口用例唯一标识")

    project_id: Optional[int] = Field(None, description="接口用例项目ID")

    module_id: Optional[int] = Field(None, description="接口用例部分ID")

    starter_id: Optional[int] = Field(None, description="开始者ID")
    status: Optional[str] = Field(None, description="状态")
    result: Optional[str] = Field(None, description="结果")
    interface_task_result_id: Optional[int] = Field(None, description="接口任务结果ID")


class InterfaceTaskResultField(BaseModel):
    """接口任务结果字段模型"""
    uid: Optional[str] = Field(None, description="UID")
    status: Optional[str] = Field(None, description="状态")
    result: Optional[str] = Field(None, description="结果")

    start_by: Optional[int] = Field(None, description="开始者")
    starter_id: Optional[int] = Field(None, description="开始者ID")

    task_id: Optional[int] = Field(None, description="任务ID")
    task_name: Optional[str] = Field(None, description="任务名称")

    run_day: Optional[str] = Field(None, description="运行日期")

    running_env_id: Optional[int] = Field(None, description="运行环境ID")

    project_id: Optional[int] = Field(None, description="接口项目ID")
    module_id: Optional[int] = Field(None, description="接口模块ID")


class PageInterfaceResultSchema(InterfaceResultFieldSchema, PageSchema):
    """接口结果分页查询模型"""
    ...


class PageInterfaceCaseResultSchema(InterfaceCaseResultFieldSchema, PageSchema):
    """接口用例结果分页查询模型"""
    ...


class PageInterfaceTaskResultSchema(InterfaceTaskResultField, PageSchema):
    """接口任务结果分页查询模型"""
    ...


class QueryCaseStepResultSchema(BaseModel):
    case_result_id: int = Field(..., description="用例结果ID")
