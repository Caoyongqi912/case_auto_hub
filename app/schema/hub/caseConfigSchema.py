#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : caseConfigSchema
# @Software: PyCharm
# @Desc: 用例枚举配置相关的 Schema 定义
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schema import PageSchema


class ICaseEnumConfig(BaseModel):
    """用例枚举配置基础字段模型（与前端 ICaseEnumConfig 类型对齐）"""
    config_key: str = Field(..., min_length=1, max_length=255, description="配置键（业务分组，如 CASE_STATUS）")
    label: str = Field(..., min_length=1, max_length=255, description="配置标签")
    value: str = Field(..., min_length=1, max_length=255, description="配置值（字符串形式存储，对应数据库字段）")
    color: Optional[str] = Field(None, max_length=50, description="配置颜色（前端徽章颜色）")
    description: Optional[str] = Field(None, max_length=500, description="配置描述")
    sort: Optional[int] = Field(0, ge=0, description="排序（同 config_key 组内排序）")
    enabled: Optional[bool] = Field(True, description="是否启用")

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value_to_str(cls, v) -> str:
        """
        接受数字 / 布尔值，统一转字符串后存储。

        前端 demo 中 value 通常是 0/1/2 等数字，这里做一次宽容转换。
        """
        if v is None:
            raise ValueError("value 不能为空")
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)


class AddCaseConfigSchema(ICaseEnumConfig):
    """新增用例枚举配置模型（强制要求业务必填字段）"""
    pass


class UpdateCaseConfigSchema(BaseModel):
    """更新用例枚举配置模型（必传 uid + 任意可修改字段）

    业务约束：``value`` 字段一旦创建不可修改。
    - 字段在 schema 中直接不定义，model_dump 不会再带出 value
    - 即便调用方手动塞入 value，mapper 层会做防御性剔除并记录日志
    - 这样既保证业务上 value 不可变，又避免对前端做破坏性改动
    """
    uid: str = Field(..., description="唯一标识")
    config_key: Optional[str] = Field(None, min_length=1, max_length=255, description="配置键")
    label: Optional[str] = Field(None, min_length=1, max_length=255, description="配置标签")
    color: Optional[str] = Field(None, max_length=50, description="配置颜色")
    description: Optional[str] = Field(None, max_length=500, description="配置描述")
    sort: Optional[int] = Field(None, ge=0, description="排序")
    enabled: Optional[bool] = Field(None, description="是否启用")


class RemoveCaseConfigSchema(BaseModel):
    """删除用例枚举配置模型"""
    uid: str = Field(..., description="唯一标识")


class PageCaseConfigSchema(PageSchema):
    """分页查询用例枚举配置模型"""
    config_key: Optional[str] = Field(None, description="按配置键过滤（精确匹配）")
    keyword: Optional[str] = Field(None, description="关键字（模糊匹配 label / description）")
