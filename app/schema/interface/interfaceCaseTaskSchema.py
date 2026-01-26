#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/26
# @Author : cyq
# @File : interfaceCaseTaskSchema
# @Software: PyCharm
# @Desc: 接口用例任务相关的Schema定义
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


class InterfaceCaseTaskFieldSchema(BaseModel):
    """接口用例任务基础字段模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    title: Optional[str] = Field(None, description="标题")
    desc: Optional[str] = Field(None, description="描述")
    cron: Optional[str] = Field(None, description="定时表达式")
    status: Optional[str] = Field("WAIT", description="状态")
    level: Optional[str] = Field(None, description="级别")
    total_cases_num: Optional[int] = Field(0, description="总用例数")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    is_auto: Optional[bool] = Field(None, description="是否自动")
    retry: Optional[int] = Field(0, description="重试次数")
    parallel: Optional[int] = Field(0, description="并行数")
    push_id: Optional[int] = Field(None, description="推送ID")


class PageInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema, PageSchema):
    """接口用例任务分页查询模型"""
    module_type: int = Field(ModuleEnum.API_TASK, description="模块类型")


class InsertInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema):
    """插入接口用例任务模型"""
    title: str = Field(..., description="标题")
    desc: str = Field(..., description="描述")
    level: str = Field(..., description="级别")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class OptionInterfaceCaseTaskSchema(InterfaceCaseTaskFieldSchema):
    """操作接口用例任务模型"""
    id: int = Field(..., description="ID")


class GetByTaskId(BaseModel):
    """根据任务ID获取模型"""
    taskId: int = Field(..., description="任务ID")


class SetTaskAuto(GetByTaskId):
    """设置任务自动模型"""
    is_auto: bool = Field(..., description="是否自动")


class ExecuteTask(BaseModel):
    """执行任务模型"""
    task_id: int = Field(..., description="任务ID")
    env_id: int = Field(..., description="环境ID")
    options: List[str] = Field(..., description="选项")


class AssocCasesSchema(BaseModel):
    """关联用例模型"""
    taskId: int = Field(..., description="任务ID")
    caseIds: List[int] = Field(..., description="用例ID列表")


class RemoveAssocCasesSchema(BaseModel):
    """移除关联用例模型"""
    taskId: int = Field(..., description="任务ID")
    caseId: int = Field(..., description="用例ID")


class AssocApisSchema(BaseModel):
    """关联API模型"""
    taskId: int = Field(..., description="任务ID")
    apiIds: List[int] = Field(..., description="API ID列表")


class RemoveAssocApisSchema(BaseModel):
    """移除关联API模型"""
    taskId: int = Field(..., description="任务ID")
    apiId: int = Field(..., description="API ID")


class InterfaceTaskResultSchema(BaseModel):
    """接口任务结果模型"""
    status: Optional[str] = Field(None, description="状态")
    result: Optional[str] = Field(None, description="结果")
    startBy: Optional[int] = Field(None, description="开始者")
    starterId: Optional[int] = Field(None, description="开始者ID")
    taskId: Optional[int] = Field(None, description="任务ID")
    runDay: Optional[Union[str, List[str]]] = Field(None, description="运行日期")
    interfaceProjectId: Optional[int] = Field(None, description="接口项目ID")
    interfaceModuleId: Optional[int] = Field(None, description="接口模块ID")


class InterfaceTaskResultDetailSchema(BaseModel):
    """接口任务结果详情模型"""
    resultId: int = Field(..., description="结果ID")


class RemoveInterfaceTaskResultDetailSchema(BaseModel):
    """移除接口任务结果详情模型"""
    resultId: int = Field(..., description="结果ID")


class PageInterfaceTaskResultSchema(InterfaceTaskResultSchema, PageSchema):
    """接口任务结果分页查询模型"""
    pass
