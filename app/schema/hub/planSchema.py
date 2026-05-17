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
    plan_start_time: Optional[str] = Field(None, description="开始时间")
    plan_end_time: Optional[str] = Field(None, description="结束时间")


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


class AddPlanCaseSchema(BaseModel):
    """添加用例到计划模型"""
    plan_id: int = Field(..., description="计划ID")
    plan_module_id: Optional[int] = Field(None, description="计划分组ID，NULL表示未分组")
    case_ids: List[int] = Field(..., description="用例ID列表")


class UpdatePlanCaseStatusSchema(BaseModel):
    """更新计划用例状态模型"""
    plan_case_id: int = Field(..., description="计划用例关联ID")
    is_review: Optional[bool] = Field(None, description="是否审核")
    case_status: Optional[int] = Field(None, description="用例状态 0:未开始 1:通过 2:失败")
    bug_url: Optional[str] = Field(None, description="缺陷链接")


class RemovePlanCaseSchema(BaseModel):
    """移除计划用例关联模型"""
    plan_case_id: int = Field(..., description="计划用例关联ID")


class PagePlanCaseSchema(PageSchema):
    """计划用例分页查询模型"""
    plan_id: int = Field(..., description="计划ID")
    plan_module_id: Optional[int] = Field(None, description="计划分组ID")
    case_level: Optional[str] = Field(None, description="用例等级")
    case_status: Optional[int] = Field(None, description="用例状态")
    is_review: Optional[bool] = Field(None, description="是否审核")


class UpdatePlanPhaseSchema(BaseModel):
    """更新计划阶段模型"""
    plan_id: int = Field(..., description="计划ID")
    plan_phase: str = Field(..., description="执行阶段 准备/一轮/二轮/回归/验收")


class PlanOverviewSchema(BaseModel):
    """计划概览统计模型"""
    plan_id: int = Field(..., description="计划ID")

    case_total: int = Field(0, description="用例总数")
    case_passed: int = Field(0, description="通过用例数")
    case_failed: int = Field(0, description="失败用例数")
    case_not_executed: int = Field(0, description="未执行用例数")
    case_completion_rate: float = Field(0.0, description="用例完成率")

    bug_total: int = Field(0, description="缺陷总数")
    bug_urls: List[str] = Field(default_factory=list, description="缺陷链接列表")

    requirement_total: int = Field(0, description="需求总数")
    requirement_completed: int = Field(0, description="已完成需求数")
    requirement_completion_rate: float = Field(0.0, description="需求完成率")


class DailyTrendSchema(BaseModel):
    """每日趋势模型"""
    date: str = Field(..., description="日期")
    executed: int = Field(0, description="执行用例数")
    passed: int = Field(0, description="通过用例数")
    failed: int = Field(0, description="失败用例数")


class PlanStatisticsSchema(BaseModel):
    """计划详细统计模型"""
    plan_id: int = Field(..., description="计划ID")

    case_by_level: dict = Field(default_factory=dict, description="用例等级分布")
    case_by_status: dict = Field(default_factory=dict, description="用例状态分布")
    daily_trend: List[DailyTrendSchema] = Field(default_factory=list, description="每日趋势")