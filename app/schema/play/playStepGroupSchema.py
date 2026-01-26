#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/8
# @Author : cyq
# @File : playStepGroupSchema
# @Software: PyCharm
# @Desc: play步骤组相关的Schema定义
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum


class InsertPlayStepGroupSchema(BaseModel):
    """插入play步骤组模型"""
    name: str = Field(..., description="名称")
    description: str = Field(..., description="描述")
    is_group: bool = Field(True, description="是否为组")
    step_num: int = Field(0, description="步骤数量")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class RemovePlayStepGroupSchema(BaseModel):
    """删除play步骤组模型"""
    groupId: int = Field(..., description="组ID")


class UpdatePlayStepGroupSchema(BaseModel):
    """更新play步骤组模型"""
    id: int = Field(..., description="ID")
    name: Optional[str] = Field(None, description="名称")
    description: Optional[str] = Field(None, description="描述")


class GetPlaySubStepByIdSchema(BaseModel):
    """根据ID获取play子步骤模型"""
    stepId: int = Field(..., description="步骤ID")


class PagePlayStepGroupSchema(PageSchema):
    """play步骤组分页查询模型"""
    uid: Optional[str] = Field(None, title="步骤组id", description="步骤组ID")
    name: Optional[str] = Field(None, title="步骤组名称", description="步骤组名称")
    is_group: bool = Field(True, description="是否为组")
    module_id: Optional[int] = Field(None, title="模块id", description="模块ID")
    project_id: Optional[int] = Field(None, title="项目id", description="项目ID")
    module_type: int = Field(ModuleEnum.UI_STEP, title="模块类型", description="模块类型")


class ReOrderPlaySubStepsSchema(BaseModel):
    """重排序play子步骤模型"""
    groupId: int = Field(..., description="组ID")
    stepIdList: List[int] = Field(..., description="步骤ID列表")


class InsertPlaySubStepSchema(BaseModel):
    """插入play子步骤模型"""
    name: str = Field(..., description="名称")
    description: str = Field(..., description="描述")
    method: str = Field(..., description="方法")
    locator: Optional[str] = Field(None, description="定位器")
    fill_value: Optional[str] = Field(None, description="填充值")
    iframe_name: Optional[str] = Field(None, description="iframe名称")
    new_page: bool = Field(False, description="是否新页面")
    is_ignore: bool = Field(False, description="是否忽略")
    is_common_step: Optional[bool] = Field(False, description="是否公共步骤")

    group_id: int = Field(..., description="组ID")
    is_group: bool = Field(False, description="是否为组")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")
