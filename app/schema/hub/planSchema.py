#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planSchema
# @Software: PyCharm
# @Desc: 测试计划相关的Schema定义
from typing import Optional, List

from pydantic import BaseModel, Field

from app.schema import PageSchema


class PlanField(BaseModel):
    """测试计划基础字段模型"""
    id: Optional[int] = Field(None, description="计划ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    plan_name: Optional[str] = Field(None, description="计划名称")
    plan_description: Optional[str] = Field(None, description="计划描述")
    plan_status: Optional[str] = Field(None, description="状态")
    plan_completion_rate: Optional[float] = Field(None, description="完成率")
    plan_mark: Optional[str] = Field(None, description="备注")
    charge_id: Optional[int] = Field(None, description="负责人ID")
    charge_name: Optional[str] = Field(None, description="负责人姓名")
    plan_start_time: Optional[str] = Field(None, description="开始时间")
    plan_end_time: Optional[str] = Field(None, description="结束时间")


class AddPlanSchema(BaseModel):
    """添加测试计划模型"""
    project_id: int = Field(..., description="项目ID")
    plan_name: str = Field(..., description="计划名称")
    plan_description: Optional[str] = Field(None, description="计划描述")
    plan_status: str = Field("RUNNING", description="状态 RUNNING/DONE")
    plan_mark: Optional[str] = Field(None, description="备注")
    charge_id: int = Field(..., description="负责人ID")
    charge_name: str = Field(..., description="负责人姓名")
    plan_start_time: str = Field(..., description="开始时间")
    plan_end_time: str = Field(..., description="结束时间")


class UpdatePlanSchema(BaseModel):
    """更新测试计划模型"""
    id: int = Field(..., description="计划ID")
    plan_name: Optional[str] = Field(None, description="计划名称")
    plan_description: Optional[str] = Field(None, description="计划描述")
    plan_status: Optional[str] = Field(None, description="状态")
    plan_completion_rate: Optional[float] = Field(None, description="完成率")
    plan_mark: Optional[str] = Field(None, description="备注")
    charge_id: Optional[int] = Field(None, description="负责人ID")
    charge_name: Optional[str] = Field(None, description="负责人姓名")
    plan_start_time: Optional[str] = Field(None, description="开始时间")
    plan_end_time: Optional[str] = Field(None, description="结束时间")


class RemovePlanSchema(BaseModel):
    """删除测试计划模型"""
    plan_id: int = Field(..., description="计划ID")


class GetPlanSchema(BaseModel):
    """获取测试计划模型"""
    plan_id: int = Field(..., description="计划ID")


class PagePlanSchema(PageSchema):
    """测试计划分页查询模型"""
    project_id: Optional[int] = Field(None, description="项目ID")
    plan_name: Optional[str] = Field(None, description="计划名称")
    plan_status: Optional[str] = Field(None, description="状态")
    charge_id: Optional[int] = Field(None, description="负责人ID")


class AssociateRequirementSchema(BaseModel):
    """计划关联需求模型"""
    plan_id: int = Field(..., description="计划ID")
    requirement_ids: List[int] = Field(..., description="需求ID列表")


class DisassociateRequirementSchema(BaseModel):
    """计划解除关联需求模型"""
    plan_id: int = Field(..., description="计划ID")
    requirement_ids: List[int] = Field(..., description="需求ID列表")


class QueryPlanRequirementsSchema(BaseModel):
    """根据需求字段查询关联需求模型"""
    plan_id: int = Field(..., description="计划ID")
    requirement_name: Optional[str] = Field(None, description="需求名称")
    requirement_level: Optional[str] = Field(None, description="需求等级")
    process: Optional[int] = Field(None, description="需求进度")


class AddPlanModuleSchema(BaseModel):
    """添加计划分组模型"""
    plan_id: int = Field(..., description="计划ID")
    parent_id: Optional[int] = Field(None, description="父级分组ID")
    title: str = Field(..., description="分组名称")
    order: Optional[int] = Field(0, description="排序顺序")


class UpdatePlanModuleSchema(BaseModel):
    """更新计划分组模型"""
    id: int = Field(..., description="分组ID")
    title: Optional[str] = Field(None, description="分组名称")
    parent_id: Optional[int] = Field(None, description="父级分组ID")
    order: Optional[int] = Field(None, description="排序顺序")


class RemovePlanModuleSchema(BaseModel):
    """删除计划分组模型"""
    module_id: int = Field(..., description="分组ID")


class MovePlanModuleSchema(BaseModel):
    """移动计划分组模型"""
    module_id: int = Field(..., description="分组ID")
    new_parent_id: Optional[int] = Field(None, description="新的父级分组ID，NULL表示移到根级")
    order: Optional[int] = Field(None, description="排序顺序")