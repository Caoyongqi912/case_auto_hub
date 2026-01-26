#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/26
# @Author : cyq
# @File : interfaceResultSchema
# @Software: PyCharm
# @Desc: 接口结果相关的Schema定义
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema


class BaseSchema(BaseModel):
    """基础模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")


class RemoveAllCaseResult(BaseModel):
    """删除所有用例结果模型"""
    interfaceCaseID: int = Field(..., description="接口用例ID")


class InterfaceCaseResultFieldSchema(BaseSchema):
    """接口用例结果字段模型"""
    interfaceCaseID: Optional[int] = Field(None, description="接口用例ID")
    interfaceCaseName: Optional[str] = Field(None, description="接口用例名称")
    interfaceCaseUid: Optional[str] = Field(None, description="接口用例唯一标识")
    interfaceCaseProjectId: Optional[int] = Field(None, description="接口用例项目ID")
    interfaceCasePartId: Optional[int] = Field(None, description="接口用例部分ID")
    starterId: Optional[int] = Field(None, description="开始者ID")
    status: Optional[str] = Field(None, description="状态")
    result: Optional[str] = Field(None, description="结果")
    interface_task_result_Id: Optional[int] = Field(None, description="接口任务结果ID")


class InterfaceResultFieldSchema(BaseSchema):
    """接口结果字段模型"""
    interfaceID: Optional[int] = Field(None, description="接口ID")
    interfaceName: Optional[str] = Field(None, description="接口名称")
    interfaceUid: Optional[str] = Field(None, description="接口唯一标识")
    interfaceProjectId: Optional[int] = Field(None, description="接口项目ID")
    interfaceModuleId: Optional[int] = Field(None, description="接口模块ID")
    interfaceEnvId: Optional[int] = Field(None, description="接口环境ID")
    starterId: Optional[int] = Field(None, description="开始者ID")
    result: Optional[str] = Field(None, description="结果")
    interface_case_result_Id: Optional[int] = Field(None, description="接口用例结果ID")
    interface_task_result_Id: Optional[int] = Field(None, description="接口任务结果ID")


class PageInterfaceCaseResultFieldSchema(InterfaceCaseResultFieldSchema, PageSchema):
    """接口用例结果分页查询模型"""
    pass


class PageInterfaceApiResultFieldSchema(InterfaceResultFieldSchema, PageSchema):
    """接口API结果分页查询模型"""
    pass