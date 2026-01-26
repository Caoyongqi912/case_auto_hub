#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/23
# @Author : cyq
# @File : playTaskSchema
# @Software: PyCharm
# @Desc: play任务相关的Schema定义
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


class PlayTaskField(BaseModel):
    """play任务基础字段模型"""
    title: Optional[str] = Field(None, description="标题")
    description: Optional[str] = Field(None, description="描述")
    is_auto: Optional[bool] = Field(None, description="是否自动")
    cron: Optional[str] = Field(None, description="定时表达式")
    switch: Optional[bool] = Field(None, description="开关")
    status: Optional[str] = Field(None, description="状态")
    level: Optional[str] = Field(None, description="级别")
    play_case_num: Optional[int] = Field(None, description="play用例数量")
    retry: Optional[int] = Field(None, description="重试次数")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    push_id: Optional[int] = Field(None, description="推送ID")


class PagePlayTaskSchema(PlayTaskField, PageSchema):
    """play任务分页查询模型"""
    module_type: int = Field(ModuleEnum.UI_TASK, description="模块类型")


class InsertPlayTaskSchema(PlayTaskField):
    """插入play任务模型"""
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")
    description: str = Field(..., description="描述")
    is_auto: bool = Field(False, description="是否自动")
    switch: bool = Field(False, description="开关")
    status: Optional[str] = Field("WAIT", description="状态")
    title: str = Field(..., description="标题")


class UpdatePlayTaskSchema(PlayTaskField):
    """更新play任务模型"""
    id: int = Field(..., description="任务ID")


class GetPlayTaskByIDSchema(BaseModel):
    """根据ID获取play任务模型"""
    taskId: int = Field(..., description="任务ID")


class PlayAssociationCase(BaseModel):
    """关联play用例模型"""
    taskId: int = Field(..., description="任务ID")
    caseIdList: List[int] = Field(..., description="用例ID列表")


class PlayRemoveAssociationCase(BaseModel):
    """移除关联play用例模型"""
    taskId: int = Field(..., description="任务ID")
    caseId: int = Field(..., description="用例ID")


class PlayTaskReportField(BaseModel):
    """play任务报告字段模型"""
    run_day: Optional[Union[str, List]] = Field(None, description="运行日期")
    uid: Optional[str] = Field(None, description="唯一标识")
    id: Optional[int] = Field(None, description="ID")
    status: Optional[str] = Field(None, description="状态")
    result: Optional[str] = Field(None, description="结果")
    start_by: Optional[int] = Field(None, description="开始者")
    starter_name: Optional[str] = Field(None, description="开始者名称")
    project_id: Optional[int] = Field(None, description="项目ID")
    module_id: Optional[int] = Field(None, description="模块ID")


class PlayPageTaskReportSchema(PageSchema, PlayTaskReportField):
    """play任务报告分页查询模型"""
    task_name: Optional[str] = Field(None, description="任务名称")
    task_id: Optional[int] = Field(None, description="任务ID")


class PlaySwitchPlayTaskSchema(BaseModel):
    """切换play任务开关模型"""
    taskId: str = Field(..., description="任务ID")
    switch: bool = Field(..., description="开关状态")


__all__ = [
    "PagePlayTaskSchema",
    "InsertPlayTaskSchema",
    "UpdatePlayTaskSchema",
    "GetPlayTaskByIDSchema",
    "PlayAssociationCase",
    "PlayRemoveAssociationCase",
    "PlayPageTaskReportSchema",
    "PlaySwitchPlayTaskSchema"
]
