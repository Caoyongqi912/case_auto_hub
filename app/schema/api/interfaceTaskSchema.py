#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : interfaceTaskSchema
# @Software: PyCharm
# @Desc:

from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum

__all__ = [
    "InsertInterfaceTaskSchema",
    "UpdateInterfaceTaskSchema",
    "PageInterfaceTaskSchema",
    "ExecuteTasSchema",
    "AssociationCasesSchema",
    "AssociationInterfacesSchema",
    "RemoveAssociationInterfacesSchema",
    "ExecuteTask",
]

class InsertInterfaceTaskSchema(BaseModel):
    """插入接口任务模型"""
    interface_task_title: str = Field(..., description="标题")
    interface_task_desc: str = Field(..., description="描述")
    interface_task_level: str = Field(..., description="级别")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class UpdateInterfaceTaskSchema(BaseModel):
    """更新接口任务模型"""
    interface_task_title: Optional[str] = Field(None, description="标题")
    interface_task_desc: Optional[str] = Field(None, description="描述")
    interface_task_level: Optional[str] = Field(None, description="级别")
    interface_task_status: Optional[str] = Field(None, description="状态")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    id:int = Field(..., description="ID")
    
class PageInterfaceTaskSchema(PageSchema):
    """接口任务分页查询模型"""
    module_type: int = Field(ModuleEnum.API_TASK, description="模块类型")
    interface_task_title: Optional[str] = Field(None, description="标题")
    interface_task_desc: Optional[str] = Field(None, description="描述")
    interface_task_level: Optional[str] = Field(None, description="级别")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")



class OptTaskSchema(BaseModel):
    task_id:int = Field(...,description="ID")

class ExecuteTasSchema(BaseModel):
    """执行任务模型"""
    task_id: int = Field(..., description="任务ID")
    env_id: int = Field(..., description="环境ID")
    options: List[str] = Field(..., description="选项")
    

class AssociationCasesSchema(BaseModel):
    """关联用例模型"""
    task_id: int = Field(..., description="任务ID")
    case_ids: List[int] = Field(..., description="用例ID列表")
    
class RemoveAssociationCasesSchema(BaseModel):
    """移除关联用例模型"""
    task_id: int = Field(..., description="任务ID")
    case_id: int = Field(..., description="用例ID")


class AssociationInterfacesSchema(BaseModel):
    """关联API模型"""
    task_id: int = Field(..., description="任务ID")
    interface_ids: List[int] = Field(..., description="API ID列表")

class RemoveAssociationInterfacesSchema(BaseModel):
    """移除关联API模型"""
    task_id: int = Field(..., description="任务ID")
    interface_id: int = Field(..., description="API ID")

class ExecuteTask(BaseModel):
    """执行任务模型"""
    task_id: int = Field(..., description="任务ID")
    env_id: int = Field(..., description="环境ID")
    options: List[str] = Field(..., description="选项")
