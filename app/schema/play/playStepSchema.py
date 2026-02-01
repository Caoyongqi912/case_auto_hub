#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/3
# @Author : cyq
# @File : playStepSchema
# @Software: PyCharm
# @Desc: play步骤相关的Schema定义
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


class InsertPlayStepSchema(BaseModel):
    name: str = Field(..., description="步骤名")
    description: Optional[str] = Field(None, description="描述")
    selector: Optional[str] = Field(None, description="步骤元素定位器")
    locator: Optional[str] = Field(None, description="元素定位方式")
    iframe_name: Optional[str] = Field(None, description="iframe名称")
    new_page: bool = Field(False, description="是否新页面")
    is_common: bool = Field(False, description="是否公共步骤")
    method: Optional[str] = Field(None, description="方法")
    key: Optional[str] = Field(None, description="键")
    value: Optional[str] = Field(None, description="值")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class InsertCasePlayStepSchema(InsertPlayStepSchema):
    case_id: int


class EditPlayStepSchema(BaseModel):
    id: int = Field(..., description="步骤ID")
    name: Optional[str] = Field(None, description="步骤名")
    description: Optional[str] = Field(None, description="描述")
    selector: Optional[str] = Field(None, description="步骤元素定位器")
    locator: Optional[str] = Field(None, description="元素定位方式")
    iframe_name: Optional[str] = Field(None, description="iframe名称")
    new_page: bool = Field(False, description="是否新页面")
    method: Optional[str] = Field(None, description="方法")
    key: Optional[str] = Field(None, description="键")
    value: Optional[str] = Field(None, description="值")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class RemovePlayStepByIdSchema(BaseModel):
    step_id: int = Field(..., description="用例ID")


class GetPlayStepSchema(BaseModel):
    """获取play步骤模型"""
    step_id: int = Field(..., description="步骤ID")


class CopyPlayStepSchema(BaseModel):
    """复制play步骤模型"""
    step_id: int = Field(..., description="步骤ID")
    is_common: Optional[bool] = Field(True, description="是否公共步骤")


class PageCommonPlayStepSchema(PageSchema):
    """获取play步骤分页模型"""
    id: Optional[int] = Field(None, description="用例ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    is_common: bool = Field(True, description="是否公共步骤")
    creatorName: Optional[str] = Field(None, description="创建者名称")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    method: Optional[str] = Field(None, description="方法")
    module_type: int = ModuleEnum.UI_STEP


class PlayStepConditionSchema(BaseModel):
    """play步骤条件模型"""
    key: str = Field(..., description="键")
    value: str = Field(..., description="值")
    operator: int = Field(..., description="操作符")


class PlayStepBasicField(BaseModel):
    """play步骤基础字段模型"""
    id: Optional[int] = Field(None, description="ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    name: Optional[str] = Field(None, description="名称")
    description: Optional[str] = Field(None, description="描述")
    method: Optional[str] = Field(None, description="方法")
    locator: Optional[str] = Field(None, description="定位器")
    fill_value: Optional[str] = Field(None, description="填充值")
    iframe_name: Optional[str] = Field(None, description="iframe名称")

    creator: Optional[int] = Field(None, description="创建者")
    creatorName: Optional[str] = Field(None, description="创建者名称")

    new_page: bool = Field(False, description="是否新页面")
    is_ignore: bool = Field(False, description="是否忽略")
    is_common_step: Optional[bool] = Field(False, description="是否公共步骤")

    db_id: Optional[int] = Field(None, description="数据库ID")
    sql_script: Optional[str] = Field(None, description="SQL脚本")
    db_a_or_b: Optional[int] = Field(None, description="数据库A或B")

    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")

    condition: Optional[PlayStepConditionSchema] = Field(None, description="条件")
    step_condition_id: Optional[int] = Field(None, description="步骤条件ID")
    step_condition_order: Optional[int] = Field(None, description="步骤条件顺序")


# class InsertPlayStepSchema(PlayStepBasicField):
#     """插入play步骤模型"""
#     name: str = Field(..., description="名称")
#     description: str = Field(..., description="描述")
#     caseId: Optional[int] = Field(None, description="用例ID")
#     module_id: int = Field(..., description="模块ID")
#     project_id: int = Field(..., description="项目ID")


class InsertPlayConditionStepSchema(PlayStepBasicField):
    """插入play条件步骤模型"""
    stepId: int = Field(..., description="步骤ID")
    name: str = Field(..., description="名称")
    description: str = Field(..., description="描述")


class ReorderPlayConditionStepsSchema(BaseModel):
    """重排序play条件步骤模型"""
    stepIds: List[int] = Field(..., description="步骤ID列表")


class UpdatePlayStepSchema(PlayStepBasicField):
    """更新play步骤模型"""
    id: int = Field(..., description="步骤ID")


class RemovePlayStepContentSchema(BaseModel):
    """删除play步骤模型"""
    content_id: int = Field(..., description="步骤ID")
    case_id: int = Field(..., description="用例ID")




class CopyPlayCaseStepContentSchema(BaseModel):
    """复制play用例步骤模型"""
    content_id: int = Field(..., description="步骤ID")
    case_id: int = Field(..., description="用例ID")


class PagePlayStepSchema(PageSchema):
    """play步骤分页查询模型"""
    uid: Optional[str] = Field(None, description="唯一标识")
    name: Optional[str] = Field(None, description="名称")
    method: Optional[str] = Field(None, description="方法")
    creatorName: Optional[str] = Field(None, description="创建者名称")
    is_common_step: Optional[Union[bool, int]] = Field(True, description="是否公共步骤")
    module_type: int = Field(ModuleEnum.UI_STEP, description="模块类型")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class AssociationStepApiSchema(BaseModel):
    """关联步骤API模型"""
    stepId: int = Field(..., description="步骤ID")
    apiId: int = Field(..., description="API ID")
    interface_a_or_b: int = Field(..., description="接口A或B")
    interface_fail_stop: int = Field(..., description="接口失败停止")
