#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/3
# @Author : cyq
# @File : playCaseSchema
# @Software: PyCharm
# @Desc: play用例相关的Schema定义
from typing import List, Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.schema import PageSchema
from enums import ModuleEnum


class EditPlayStepContentSchema(BaseModel):
    """删除play步骤模型"""
    id: int = Field(..., description="步骤ID")
    content_name: Optional[str] = Field(None, description="步骤名称")
    enable: Optional[bool] = Field(None, description="是否启用")
    script_text: Optional[str] = Field(None, description="API脚本文本")


class AssociationPlayStepSchema(BaseModel):
    """case 关联 公共 step"""
    quote: bool = Field(..., description="是否引用")
    case_id: int = Field(..., description="用例ID")
    play_step_id_list: List[int] = Field(..., description="步骤Id")


class AssociationPlayGroupSchema(BaseModel):
    """case 关联 公共 step"""
    case_id: int = Field(..., description="用例ID")
    group_id_list: List[int] = Field(..., description="步骤组Id")


class GetPlayCaseByCaseId(BaseModel):
    """根据用例ID获取play用例模型"""
    caseId: Union[int, str] = Field(..., description="用例ID")


class ExecutePlayCase(BaseModel):
    """执行play用例模型"""
    case_id: Union[int, str] = Field(..., description="用例ID")
    error_stop: bool = Field(..., description="错误停止")


class PlayCaseBasicSchema(BaseModel):
    """play用例基础信息模型"""
    title: str = Field(..., description="标题")
    description: str = Field(..., description="描述")
    level: str = Field(..., title="用例等级", description="用例等级")
    status: str = Field(..., title="用例状态", description="用例状态")
    step_num: int = Field(0, description="步骤数量")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class EditPlayCaseBasicSchema(BaseModel):
    """编辑play用例基础信息模型"""
    id: int = Field(..., description="用例ID")
    title: Optional[str] = Field(None, description="标题")
    description: Optional[str] = Field(None, description="描述")
    level: Optional[str] = Field(None, title="用例等级", description="用例等级")
    status: Optional[str] = Field(None, title="用例状态", description="用例状态")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class ReOrderPlayStepSchema(BaseModel):
    """重排序play步骤模型"""
    content_id_list: List[int] = Field(..., description="步骤ID列表")
    case_id: int = Field(..., description="用例ID")


class PagePlayCaseSchema(PageSchema):
    """play用例分页查询模型"""
    id: Optional[int] = Field(None, description="用例ID")
    uid: Optional[str] = Field(None, description="唯一标识")
    title: Optional[str] = Field(None, description="标题")
    description: Optional[str] = Field(None, description="描述")
    level: Optional[str] = Field(None, title="用例等级", description="用例等级")
    status: Optional[str] = Field(None, title="用例状态", description="用例状态")
    step_num: Optional[int] = Field(None, description="步骤数量")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    module_type: int = Field(ModuleEnum.UI_CASE, title="模块类型", description="模块类型")


class PlayCaseChoiceStepSchema(BaseModel):
    """选择play用例步骤模型"""
    caseId: int = Field(..., description="用例ID")
    choice_steps: List[int] = Field(..., description="选择的步骤ID列表")
    quote: bool = Field(True, title="是否引用", description="是否引用")


class PlayCaseChoiceGroupStepSchema(BaseModel):
    """选择play用例组步骤模型"""
    caseId: int = Field(..., description="用例ID")
    choice_steps: List[int] = Field(..., description="选择的步骤ID列表")


class PagePlayCaseResultSchema(PageSchema):
    """play用例结果分页查询模型"""
    ui_case_Id: Optional[int] = Field(None, description="UI用例ID")
    ui_case_name: Optional[str] = Field(None, description="UI用例名称")
    starter_id: Optional[int] = Field(None, description="开始者ID")
    starter_name: Optional[str] = Field(None, description="开始者名称")
    result: Optional[str] = Field(None, description="结果")
    status: Optional[str] = Field(None, description="状态")


class PagePlayCaseVariableSchema(PageSchema):
    """play用例变量分页查询模型"""
    key: Optional[str] = Field(None, description="键")
    value: Optional[Any] = Field(None, description="值")
    play_case_id: int = Field(..., description="play用例ID")


class GetPlayCaseVariableSchema(BaseModel):
    """获取play用例变量模型"""
    uid: str = Field(..., description="唯一标识")


class InsertPlayCaseVariableSchema(BaseModel):
    """插入play用例变量模型"""
    key: str = Field(..., description="键")
    value: Any = Field(..., description="值")
    play_case_id: int = Field(..., description="play用例ID")


class EditPlayCaseVariableSchema(BaseModel):
    """编辑play用例变量模型"""
    id: int = Field(..., description="变量ID")
    play_case_id: int = Field(..., description="play用例ID")
    key: Optional[str] = Field(None, description="键")
    value: Optional[Any] = Field(None, description="值")
