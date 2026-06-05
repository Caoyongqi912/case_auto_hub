#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planSchema
# @Software: PyCharm
# @Desc: 测试计划相关的Schema定义
from datetime import datetime, date
from typing import Optional, List, Literal

from pydantic import BaseModel, Field

from app.schema import PageSchema


class PlanField(BaseModel):
    """测试计划基础字段模型"""
    id: Optional[int] = Field(None, description="计划ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    plan_name: Optional[str] = Field(None, description="计划名称")
    plan_description: Optional[str] = Field(None, description="计划描述")
    plan_status: Optional[int] = Field(None, description="计划状态 0:进行中 1:已完成")
    plan_mark: Optional[str] = Field(None, description="备注")
    charge_id: Optional[int] = Field(None, description="负责人ID")
    charge_name: Optional[str] = Field(None, description="负责人姓名")
    plan_start_time: Optional[date] = Field(None, description="开始时间")
    plan_end_time: Optional[date] = Field(None, description="结束时间")


class AddPlanSchema(BaseModel):
    """添加测试计划模型"""
    project_id: int = Field(..., description="项目ID")
    plan_name: str = Field(..., description="计划名称")
    plan_description: Optional[str] = Field(None, description="计划描述")
    plan_status: Optional[int] = Field(0, description="计划状态 0:进行中 1:已完成")
    plan_mark: Optional[str] = Field(None, description="备注")
    charge_id: int = Field(..., description="负责人ID")
    charge_name: str = Field(..., description="负责人姓名")
    plan_start_time: Optional[date] = Field(None, description="开始时间")
    plan_end_time: Optional[date] = Field(None, description="结束时间")


class UpdatePlanSchema(BaseModel):
    """更新测试计划模型"""
    id: int = Field(..., description="计划ID")
    plan_name: Optional[str] = Field(None, description="计划名称")
    plan_description: Optional[str] = Field(None, description="计划描述")
    plan_status: Optional[int] = Field(None, description="计划状态 0:进行中 1:已完成")
    plan_mark: Optional[str] = Field(None, description="备注")
    charge_id: Optional[int] = Field(None, description="负责人ID")
    charge_name: Optional[str] = Field(None, description="负责人姓名")
    plan_start_time: Optional[date] = Field(None, description="开始时间")
    plan_end_time: Optional[date] = Field(None, description="结束时间")


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
    plan_status: Optional[int] = Field(None, description="计划状态 0:进行中 1:已完成")
    charge_id: Optional[int] = Field(None, description="负责人ID")


class AssociateRequirementSchema(BaseModel):
    """计划关联需求模型"""
    plan_id: int = Field(..., description="计划ID")
    requirement_ids: List[int] = Field(..., description="需求ID列表")

class AssociatePlanCaseSchema(BaseModel):
    """关联计划用例模型"""
    plan_id: int = Field(..., description="计划ID")
    case_ids: List[int] = Field(..., description="用例ID列表")
    plan_module_id: Optional[int] = Field(None, description="计划分组ID（兜底目标分组）")
    # 新增：源项目目录 ID 列表；提供时按"按源目录复制/匹配计划目录"逻辑处理
    # 行为：每个 source module 会沿 parent_id 走到根，沿途在 plan 里逐层 find-or-create
    # 同名计划目录已存在时：merge_same_group=True 时复用，否则也复用（同名=合并语义）
    module_ids: Optional[List[int]] = Field(None, description="源项目模块ID列表（用于按源目录结构复制/匹配计划分组）")
    merge_same_group: bool = Field(False, description="是否合并相同用例分组（与同名计划目录合并；目前保留字段，行为同 find-or-create）")


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


class UpdatePlanCaseStepResultSchema(BaseModel):
    """更新计划用例步骤结果模型"""
    plan_id: int = Field(..., description="计划ID")
    step_id: Optional[int] = Field(None, description="用例步骤ID")
    actual_result: Optional[str] = Field(None, description="实际结果")
    bug_url: Optional[str] = Field(None, description="缺陷链接")
    first_status: Optional[str] = Field(None, description="一轮测试状态 ")
    second_status: Optional[str] = Field(None, description="二轮测试状态 ")

class CopyCaseToCasePlan(BaseModel):
    """复制计划用例到新的分组模型"""
    case_id_list: List[int] = Field(..., description="用例ID列表")
    plan_id: int = Field(..., description="计划ID")
    plan_case_module_id: int = Field(..., description="计划分组ID")
    is_review: int = Field(None, description="是否审核 0:未审核 1:已审核")


class CopyOneCaseToCasePlan(BaseModel):
    """复制单个计划用例到新的分组模型"""
    case_id: int = Field(..., description="用例ID")
    plan_id: int = Field(..., description="计划ID")
    plan_module_id: int = Field(..., description="计划分组ID")


class ReorderPlanCaseSchema(BaseModel):
    """重排序计划用例（单 case 移动语义）

    设计原则
    --------
    - 前端只传"被移动 case + 锚点"两个关键 ID，传输量与列表规模无关
    - 服务端基于锚点重新计算目标 module 的整组顺序，
      用单条 ``UPDATE ... CASE`` 表达式一次回写，避免 N 次 roundtrip
    - 天然支持跨 module 移动（``target_module_id`` 指定新分组即可）

    锚点语义
    --------
    - ``before_id`` 优先：被移动 case 放在此 case 之前
    - ``after_id`` 次之：被移动 case 放在此 case 之后
    - 都为空：被移动 case 移到目标 module 末尾
    """

    plan_id: int = Field(..., description="计划ID")
    case_id: int = Field(..., description="被移动的用例ID")
    target_module_id: Optional[int] = Field(
        None, description="目标分组ID；None 表示在原 module 内移动"
    )
    before_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之前"
    )
    after_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之后"
    )


class ReorderPlanCaseItem(BaseModel):
    """单条重排序意图（用于批量接口）

    字段语义同 ``ReorderPlanCaseSchema``，但不含 ``plan_id``
    （批量接口在父级统一指定）。
    """

    case_id: int = Field(..., description="被移动的用例ID")
    target_module_id: Optional[int] = Field(
        None, description="目标分组ID；None 表示在原 module 内移动"
    )
    before_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之前"
    )
    after_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之后"
    )


class BulkReorderPlanCaseSchema(BaseModel):
    """批量重排序计划用例

    典型场景
    --------
    - **多选拖拽**：一次拖动 N 个连续用例到新位置，每条 item 用同一锚点
    - **跨 module 批量调整**：把若干 case 从 A 组移到 B 组指定位置
    - **混合操作**：items 内允许跨 module，顺序应用

    行为
    ----
    - 所有 items 在 **同一事务** 内顺序应用；任一失败整体回滚
    - 越权前置：聚合所有 case_id + 锚点去重后一次性校验，省去 N 次 SELECT
    - 单条应用的执行逻辑与 ``reorder_plan_case`` 完全一致（共用 _apply_single_reorder）

    Returns:
        接口返回每条 item 的 affected 行数列表，便于前端精确定位失败项
    """

    plan_id: int = Field(..., description="计划ID")
    items: List[ReorderPlanCaseItem] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="批量重排序条目（1~500）；同一事务内顺序应用",
    )


class UpdateCaseToCasePlan(BaseModel):
    """更新计划用例模型

    字段约束
    --------
    - ``case_id_list``：单批最多 2000 条，传入时会按 Pydantic 校验拦截
    - 状态字段使用 ``Literal`` 限定可选值，避免错别字静默写入
    """

    # 状态枚举（与 CaseConfig 表 CASE_STATUS / IS_REVIEW 保持一致）
    _REVIEW_VALUES = ("0", "1")
    _STATUS_VALUES = ("0", "1", "2", "3", "4")

    case_id_list: List[int] = Field(
        ...,
        max_length=2000,
        description="用例ID列表（去重后单批最多 2000 条；超出请分批调用）",
    )
    plan_id: int = Field(..., description="计划ID")
    is_review: Optional[Literal["0", "1"]] = Field(
        None, description="审核状态 0:未审核 1:已审核"
    )
    first_status: Optional[Literal["0", "1", "2", "3", "4"]] = Field(
        None,
        description="一轮测试状态 0:未开始 1:通过 2:失败 3:阻塞 4:跳过",
    )
    second_status: Optional[Literal["0", "1", "2", "3", "4"]] = Field(
        None,
        description="二轮测试状态 0:未开始 1:通过 2:失败 3:阻塞 4:跳过",
    )

class UploadCommitSchema(BaseModel):
    """确认并入库用例模型"""
    file_md5: str = Field(..., description="文件唯一标识")
    plan_id: int = Field(..., description="计划ID")
    plan_module_id: Optional[int] = Field(None, description="计划分组ID")
    is_review: Optional[str] = Field(None, description="审核状态")
    first_status: Optional[str] = Field(None, description="一轮测试状态 ")
    second_status: Optional[str] = Field(None, description="二轮测试状态 ")




class MoveCaseToCasePlan(BaseModel):
    """移动计划用例到新的分组模型"""
    case_id_list: List[int] = Field(..., description="用例ID列表")
    plan_id: int = Field(..., description="计划ID")
    plan_case_module_id: int = Field(..., description="计划分组ID")

class RemovePlanCaseSchema(BaseModel):
    """移除计划用例关联模型"""
    case_ids: List[int] = Field(..., description="用例ID列表")
    plan_id: int = Field(..., description="计划ID")

class PagePlanCaseSchema(PageSchema):
    """计划用例分页查询模型"""
    plan_id: int = Field(..., description="计划ID")
    plan_module_id: Optional[int] = Field(None, description="计划分组ID")
    case_level: Optional[str] = Field(None, description="用例等级")
    is_review: Optional[str] = Field(None, description="审核状态")


class UpdatePlanPhaseSchema(BaseModel):
    """更新计划阶段模型"""
    plan_id: int = Field(..., description="计划ID")
    plan_phase: str = Field(..., description="执行阶段 准备/一轮/二轮/回归/验收")


class PlanOverviewSchema(BaseModel):
    """计划概览统计模型"""
    plan_id: int = Field(..., description="计划ID")

    case_total: int = Field(0, description="用例总数")
    first_round: Optional[dict] = Field(None, description="一轮测试统计 {passed, failed, not_executed, completion_rate}")
    second_round: Optional[dict] = Field(None, description="二轮测试统计 {passed, failed, not_executed, completion_rate}")

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
    case_by_first_status: dict = Field(default_factory=dict, description="一轮测试状态分布")
    case_by_second_status: dict = Field(default_factory=dict, description="二轮测试状态分布")
    daily_trend: List[DailyTrendSchema] = Field(default_factory=list, description="每日趋势")
