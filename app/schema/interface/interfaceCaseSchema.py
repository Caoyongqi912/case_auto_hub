#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/26
# @Author : cyq
# @File : interfaceCaseSchema
# @Software: PyCharm
# @Desc: 接口用例相关的Schema定义
import json
from typing import List, Union, Optional
from pydantic.v1 import root_validator
from pydantic import BaseModel, Field

from app.schema import PageSchema
from app.schema.interface.interfaceApiSchema import IBeforeSqlExtracts
from enums import ModuleEnum
from enums.CaseEnum import LoopTypeEnum


class InterfaceCaseSchema(BaseModel):
    """接口用例基础模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    title: Optional[str] = Field(None, description="标题")
    desc: Optional[str] = Field(None, description="描述")
    level: Optional[str] = Field(None, description="级别")
    status: Optional[str] = Field(None, description="状态")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class InsertInterfaceCaseBaseInfoSchema(InterfaceCaseSchema):
    """插入接口用例基础信息模型"""
    title: str = Field(..., description="标题")
    desc: str = Field(..., description="描述")
    level: str = Field(..., description="级别")
    status: str = Field(..., description="状态")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class OptionInterfaceCaseSchema(InterfaceCaseSchema):
    """操作接口用例模型"""
    id: int = Field(..., description="ID")


class ExecuteInterfaceCaseSchema(BaseModel):
    """执行接口用例模型"""
    case_id: int = Field(..., description="用例ID")
    env_id: int = Field(..., description="环境ID")
    error_stop: bool = Field(..., description="错误停止")


class PageInterfaceCaseSchema(InterfaceCaseSchema, PageSchema):
    """接口用例分页查询模型"""
    module_type: int = Field(ModuleEnum.API_CASE, description="模块类型")


class AssociationApisSchema(BaseModel):
    """关联接口模型"""
    interface_case_id: int = Field(..., description="接口用例ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")


class AssociationApiSchema(BaseModel):
    """关联单个接口模型"""
    case_id: int = Field(..., description="用例ID")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class UpdateCaseContentAssert(BaseModel):
    """更新用例内容断言模型"""
    assert_key: str = Field(..., description="断言键")
    assert_value: str = Field(..., description="断言值")
    assert_type: int = Field(..., description="断言类型")


class AddInterfaceCaseCommonGROUPSchema(BaseModel):
    """添加接口用例公共组模型"""
    interface_case_id: int = Field(..., description="接口用例ID")
    api_group_id_list: List[int] = Field(..., description="API组ID列表")


class AddInterfaceApi2Case(BaseModel):
    """添加接口到用例模型"""
    caseId: int = Field(..., description="用例ID")
    apiId: int = Field(..., description="API ID")


class RemoveCaseContentSchema(BaseModel):
    """删除用例内容模型"""
    case_id: int = Field(..., description="用例ID")
    content_step_id: int = Field(..., description="内容步骤ID")


class ReorderContentStepSchema(BaseModel):
    """重排序内容步骤模型"""
    case_id: int = Field(..., description="用例ID")
    content_step_order: List[int] = Field(..., description="内容步骤排序")


class AssociationConditionSchema(BaseModel):
    """关联条件模型"""
    interface_case_id: int = Field(..., description="接口用例ID")


class AssociationConditionAPISchema(BaseModel):
    """关联条件API模型"""
    condition_id: int = Field(..., description="条件ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")


class AssociationLoopAPISchema(BaseModel):
    """关联循环API模型"""
    loop_id: int = Field(..., description="循环ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")


class RemoveAssociationConditionAPISchema(BaseModel):
    """移除关联条件API模型"""
    condition_id: int = Field(..., description="条件ID")
    interface_id: int = Field(..., description="接口ID")


class RemoveAssociationLoopAPISchema(BaseModel):
    """移除关联循环API模型"""
    loop_id: int = Field(..., description="循环ID")
    interface_id: int = Field(..., description="接口ID")


class ConditionAddGroups(BaseModel):
    """条件添加组模型"""
    condition_api_id: int = Field(..., description="条件API ID")
    group_id_list: List[int] = Field(..., description="组ID列表")


class ConditionAddCommons(BaseModel):
    """条件添加公共API模型"""
    condition_api_id: int = Field(..., description="条件API ID")
    common_api_list: List[int] = Field(..., description="公共API列表")


class CopyContentStepSchema(BaseModel):
    """复制内容步骤模型"""
    case_id: int = Field(..., description="用例ID")
    content_id: int = Field(..., description="内容ID")


class UpdateConditionSchema(BaseModel):
    """更新条件模型"""
    id: int = Field(..., description="ID")
    condition_key: str = Field(..., description="条件键")
    condition_value: Optional[str] = Field(None, description="条件值")
    condition_operator: int = Field(..., description="条件操作符")


class UpdateDBSchema(BaseModel):
    """更新数据库模型"""
    id: int = Field(..., description="ID")
    sql_text: Optional[str] = Field(None, description="SQL文本")
    sql_extracts: Optional[List[IBeforeSqlExtracts]] = Field(None, description="SQL提取")
    db_id: Optional[int] = Field(None, description="数据库ID")


class LoopCondition(BaseModel):
    """循环条件模型"""
    key: str = Field(..., description="键")
    value: str = Field(..., description="值")
    operate: int = Field(..., description="操作")


class AssociationLoopSchema(BaseModel):
    """关联循环模型"""
    case_id: int = Field(..., description="用例ID")
    loop_type: int = Field(..., description="循环类型")
    loop_interval: Optional[int] = Field(None, description="循环间隔")
    loop_times: Optional[int] = Field(None, description="循环次数")
    loop_items: Optional[str] = Field(None, description="循环项")
    loop_item_key: Optional[str] = Field(None, description="循环项键")

    loop_condition: Optional[LoopCondition] = Field(None, description="循环条件")
    max_loop: Optional[int] = Field(None, description="最大循环次数")

    @root_validator(pre=True)
    def validate_loop_type(cls, values):
        """验证循环类型"""
        lt = values.get("loop_type")

        match lt:
            case LoopTypeEnum.LoopItems:
                loop_items = values.get("loop_items")
                loop_item_key = values.get("loop_item_key")
                if loop_items is None or (isinstance(loop_items, str) and not loop_items.strip()):
                    raise ValueError("loop_items 不能为空")
                if loop_item_key is None:
                    raise ValueError("loop_item_key 不能为空")
                # 尝试解析为JSON或逗号分隔的列表
                try:
                    # 先尝试解析为JSON
                    items = json.loads(loop_items)
                    if not items:  # 空列表或空对象
                        raise ValueError("loop_items 不能为空列表")
                except json.JSONDecodeError:
                    # 如果不是JSON，检查是否是逗号分隔的列表
                    items = [item.strip() for item in loop_items.split(',') if item.strip()]
                    if not items:
                        raise ValueError("loop_items 必须包含至少一个有效的项")
            case LoopTypeEnum.LoopTimes:
                loop_times = values.get("loop_times")
                if loop_times is None:
                    raise ValueError("loop_times 不能为空")
            case LoopTypeEnum.LoopCondition:
                # 当 loop_type 为 WhileCondition 时，验证 loop_condition
                loop_condition = values.get("loop_condition")
                max_loop = values.get("max_loop")

                if loop_condition is None:
                    raise ValueError("loop_condition 不能为空")

                if max_loop is None:
                    raise ValueError("max_loop 不能为空")
                # 如果提供的是字典，验证它
                if isinstance(loop_condition, dict):
                    try:
                        # 尝试创建 LoopCondition 实例来验证
                        LoopCondition(**loop_condition)
                    except Exception as e:
                        raise ValueError(f"无效的 loop_condition: {e}")

        return values


class UpdateLoopSchema(AssociationLoopSchema):
    """更新循环模型"""
    case_id: Optional[int] = Field(None, description="用例ID")
    id: int = Field(..., description="ID")
    loop_type: int = Field(..., description="循环类型")
    loop_interval: Optional[int] = Field(None, description="循环间隔")
    loop_times: Optional[int] = Field(None, description="循环次数")
    loop_items: Optional[str] = Field(None, description="循环项")
    loop_item_key: Optional[str] = Field(None, description="循环项键")


class UpdateCaseContentStepSchema(BaseModel):
    """更新用例内容步骤模型"""
    id: int = Field(..., description="ID")
    content_name: Optional[str] = Field(None, description="内容名称")
    enable: Optional[bool] = Field(None, description="是否启用")
    api_wait_time: Optional[int] = Field(None, description="API等待时间")
    api_script_text: Optional[str] = Field(None, description="API脚本文本")
    api_assert_list: Optional[List[UpdateCaseContentAssert]] = Field(None, description="API断言列表")


class AddCaseContentStepSchema(BaseModel):
    """添加用例内容步骤模型"""
    case_id: int = Field(..., description="用例ID")
    content_type: int = Field(..., description="内容类型")
    enable: Optional[bool] = Field(None, description="是否启用")
    api_wait_time: Optional[int] = Field(None, description="API等待时间")
    api_script_text: Optional[str] = Field(None, description="API脚本文本")
    api_assert_list: Optional[List[UpdateCaseContentAssert]] = Field(None, description="API断言列表")
