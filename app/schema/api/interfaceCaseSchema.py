#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
InterfaceCase Schema 定义

与 app/model/interfaceAPIModel/interfaceCaseModel.py 中的 InterfaceCase 模型对应
使用 Pydantic v2 注解,提供数据验证和序列化
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schema import PageSchema
from enums import ModuleEnum


class InterfaceCaseSchema(BaseModel):
    """
    接口用例 Schema - 完整字段定义
    对应 InterfaceCase 模型的完整字段结构
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(None, description="用例ID")
    uid: Optional[str] = Field(None, description="唯一标识")

    case_title: Optional[str] = Field(None, description="用例标题")
    case_desc: Optional[str] = Field(None, description="用例描述")
    case_level: Optional[str] = Field(None, description="用例等级")
    case_status: Optional[str] = Field(None, description="用例状态")
    case_api_num: Optional[int] = Field(None, description="接口数量")
    error_stop: Optional[int] = Field(None, description="错误停止: 0否 1是")

    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")

    creator: Optional[int] = Field(None, description="创建人ID")
    creatorName: Optional[str] = Field(None, description="创建人姓名")
    updater: Optional[int] = Field(None, description="更新人ID")
    updaterName: Optional[str] = Field(None, description="更新人姓名")
    create_time: Optional[datetime] = Field(None, description="创建时间")
    update_time: Optional[datetime] = Field(None, description="更新时间")


class InterfaceCaseBriefSchema(BaseModel):
    """
    接口用例简要 Schema - 用于列表展示
    只包含关键字段,减小数据传输量
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用例ID")
    uid: str = Field(..., description="唯一标识")
    case_title: str = Field(..., description="用例标题")
    case_desc: Optional[str] = Field(None, description="用例描述")
    case_level: str = Field(..., description="用例等级")
    case_status: str = Field(..., description="用例状态")
    case_api_num: int = Field(..., description="接口数量")
    project_id: int = Field(..., description="项目ID")
    module_id: int = Field(..., description="模块ID")

    @property
    def desc_brief(self) -> str:
        """
        获取简短的描述
        """
        if not self.case_desc:
            return ""
        return self.case_desc[:20] + "..." if len(self.case_desc) > 20 else self.case_desc


class AddInterfaceCaseSchema(BaseModel):
    """
    添加接口用例 Schema - 创建新用例时使用
    """
    case_title: str = Field(..., min_length=1, max_length=40, description="用例标题")
    case_desc: Optional[str] = Field(None, max_length=200, description="用例描述")
    case_level: str = Field(default="P0", description="用例等级")
    case_status: str = Field(default="1", description="用例状态")

    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class UpdateInterfaceCaseSchema(BaseModel):
    """
    更新接口用例 Schema - 更新现有用例时使用
    """
    case_id: int = Field(..., description="ID", validation_alias="id")
    case_title: Optional[str] = Field(None, min_length=1, max_length=40, description="用例标题")
    case_desc: Optional[str] = Field(None, max_length=200, description="用例描述")
    case_level: Optional[str] = Field(None, description="用例等级")
    case_status: Optional[str] = Field(None, description="用例状态")
    error_stop: Optional[int] = Field(None, description="错误停止: 0否 1是")
    module_id: Optional[int] = Field(None, description="模块ID")


class OptInterfaceCaseSchema(BaseModel):
    """
    获取/删除/复制接口用例 Schema
    """
    case_id: int = Field(..., description="用例ID")


class ExecuteInterfaceCaseSchema(BaseModel):
    """
    执行接口用例 Schema
    """
    case_id: int = Field(..., description="用例ID")
    env_id: int = Field(..., description="环境ID")
    error_stop: bool = Field(..., description="错误是否停止")


class PageInterfaceCaseSchema(InterfaceCaseSchema, PageSchema):
    """
    接口用例分页查询 Schema
    """
    module_type: int = Field(ModuleEnum.API_CASE, description="模块类型")


class AssociationApiSchema(BaseModel):
    """
    关联单个 Schema
    """
    case_id: int = Field(..., description="用例ID")


class AssociationGroupSchema(BaseModel):
    """
    关联单个 Schema
    """
    case_id: int = Field(..., description="用例ID")
    group_id_list: List[int] = Field(..., description="接口组")






class AssociationApisSchema(BaseModel):
    """
    关联接口列表 Schema
    用于将多个接口关联到用例
    """
    case_id: int = Field(..., description="用例ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")
    is_copy: bool = Field(..., description="复制添加")


class AddInterfaceApi2CaseSchema(BaseModel):
    """
    添加单个接口到用例 Schema
    """
    case_id: int = Field(..., description="用例ID")
    interface_id: int = Field(..., description="接口ID")


class RemoveCaseContentSchema(BaseModel):
    """
    删除用例内容 Schema
    """
    case_id: int = Field(..., description="用例ID")
    content_id: int = Field(..., description="内容步骤ID")


class ReorderContentStepSchema(BaseModel):
    """
    重排序用例内容步骤 Schema
    """
    case_id: int = Field(..., description="用例ID")
    content_step_order: List[int] = Field(..., description="内容步骤ID列表")


class InterfaceCaseListSchema(BaseModel):
    """
    接口用例列表 Schema - 用于分页查询结果
    """
    items: List[InterfaceCaseBriefSchema] = Field(default_factory=list, description="用例列表")
    page_info: "PageInfoSchema" = Field(..., description="分页信息")


class InterfaceCaseQuerySchema(BaseModel):
    """
    接口用例查询 Schema - 用于条件查询和分页
    """
    case_title: Optional[str] = Field(None, description="用例标题(模糊匹配)")
    case_level: Optional[str] = Field(None, description="用例等级")
    case_status: Optional[str] = Field(None, description="用例状态")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")

    page: int = Field(default=1, ge=1, description="页码")
    limit: int = Field(default=20, ge=1, le=100, description="每页记录数")
    sort: Optional[str] = Field(None, description="排序字段")


class UpdateCaseContentAssert(BaseModel):
    """
    更新用例内容断言 Schema
    """
    assert_key: str = Field(..., description="断言键")
    assert_value: str = Field(..., description="断言值")
    assert_type: int = Field(..., description="断言类型")


class UpdateCaseContentStepSchema(BaseModel):
    """
    更新用例内容步骤 Schema
    """
    content_id: int = Field(..., description="步骤ID")
    enable: Optional[bool] = Field(None, description="是否启用")
    content_name:Optional[str] = Field(None,description="contentName")
    wait_time: Optional[int] = Field(None, description="API等待时间")
    script_text: Optional[str] = Field(None, description="API脚本文本")
    assert_list: Optional[List[UpdateCaseContentAssert]] = Field(None, description="API断言列表")


class AddCaseContentStepSchema(BaseModel):
    """
    添加用例内容步骤 Schema
    """
    case_id: int = Field(..., description="用例ID")
    content_type: int = Field(..., description="内容类型")
    enable: Optional[bool] = Field(None, description="是否启用")
    api_wait_time: Optional[int] = Field(None, description="API等待时间")
    script_text: Optional[str] = Field(None, description="API脚本文本")
    assert_list: Optional[List[UpdateCaseContentAssert]] = Field(None, description="API断言列表")


class AssociationConditionSchema(BaseModel):
    """
    关联条件 Schema
    """
    case_id: int = Field(..., description="用例ID")

class AssociationDBSchema(BaseModel):
    """
    关联条件 Schema
    """
    case_id: int = Field(..., description="用例ID")
class UpdateAssociationDBSchema(BaseModel):
    """
    关联条件 Schema
    """
    content_id: int = Field(..., description="用例ID")
    db_id:Optional[int] = Field(...,description="目标DB")
    sql_text:Optional[str] = Field(...,description="SQL")
    sql_extracts:Optional[List[Any]] = Field(...,description="SQL提取")




class AssociationConditionAPISchema(BaseModel):
    """
    关联条件 API Schema
    """
    condition_id: int = Field(..., description="条件ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")
    is_copy: bool = Field(..., description="是否复制")


class CreateConditionAPISchema(BaseModel):
    """
    关联条件 API Schema
    """
    condition_id: int = Field(..., description="条件ID")
    case_id: int = Field(..., description="CaseId")


class ReorderAssociationConditionAPISchema(BaseModel):
    """
    关联条件 API Schema
    """
    condition_id: int = Field(..., description="条件ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")


class UpdateConditionSchema(BaseModel):
    """
    更新条件 Schema
    """
    id: int = Field(..., description="条件ID")
    condition_key: str = Field(..., description="条件键")
    condition_value: Optional[str] = Field(None, description="条件值")
    condition_operator: int = Field(..., description="条件操作符")


class LoopCondition(BaseModel):
    """
    循环条件 Schema
    """
    key: str = Field(..., description="键")
    value: str = Field(..., description="值")
    operate: int = Field(..., description="操作")


class AssociationLoopSchema(BaseModel):
    """
    关联循环 Schema
    """
    case_id: int = Field(..., description="用例ID")
    loop_type: int = Field(..., description="循环类型")
    loop_interval: Optional[int] = Field(None, description="循环间隔")
    loop_times: Optional[int] = Field(None, description="循环次数")
    loop_items: Optional[str] = Field(None, description="循环项")
    loop_item_key: Optional[str] = Field(None, description="循环项键")
    loop_condition: Optional[LoopCondition] = Field(None, description="循环条件")
    max_loop: Optional[int] = Field(None, description="最大循环次数")


class UpdateLoopSchema(AssociationLoopSchema):
    """
    更新循环 Schema
    """
    id: int = Field(..., description="循环ID")
    case_id: Optional[int] = Field(None, description="用例ID")


class AssociationLoopAPISchema(BaseModel):
    """
    关联循环 API Schema
    """
    loop_id: int = Field(..., description="循环ID")
    interface_id_list: List[int] = Field(..., description="接口ID列表")
    is_copy:bool = Field(...,description="复制添加？")

class CopyContentStepSchema(BaseModel):
    """
    复制内容步骤 Schema
    """
    case_id: int = Field(..., description="用例ID")
    content_id: int = Field(..., description="内容ID")

class InsertCaseContentStepSchema(BaseModel):
    case_id: int = Field(...,description="用例ID")
    content_type:int = Field(...,description="类型")


__all__ = [
    "InsertCaseContentStepSchema",
    'InterfaceCaseSchema',
    'InterfaceCaseBriefSchema',
    'AddInterfaceCaseSchema',
    'UpdateInterfaceCaseSchema',
    'OptInterfaceCaseSchema',
    'ExecuteInterfaceCaseSchema',
    'PageInterfaceCaseSchema',
    'AssociationApisSchema',
    'AddInterfaceApi2CaseSchema',
    'RemoveCaseContentSchema',
    'ReorderContentStepSchema',
    'InterfaceCaseListSchema',
    'InterfaceCaseQuerySchema',
    'UpdateCaseContentAssert',
    'UpdateCaseContentStepSchema',
    'AddCaseContentStepSchema',
    'AssociationConditionSchema',
    'AssociationConditionAPISchema',
    'UpdateConditionSchema',
    'LoopCondition',
    'AssociationLoopSchema',
    'UpdateLoopSchema',
    'AssociationLoopAPISchema',
    'CopyContentStepSchema',
    "AssociationApiSchema",
    'ReorderAssociationConditionAPISchema',
    "CreateConditionAPISchema",
    "AssociationGroupSchema",
    "AssociationDBSchema",
    "UpdateAssociationDBSchema"
]
