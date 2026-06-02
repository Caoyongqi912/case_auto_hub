#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : case_config
# @Software: PyCharm
# @Desc: 用例配置（枚举）数据模型
from sqlalchemy import Boolean, Column, Integer, String

from app.model.basic import BaseModel


class CaseConfig(BaseModel):
    """
    用例枚举配置模型

    用于存储用例业务相关的枚举配置项（如用例状态、轮次等）。
    通过 config_key 进行业务分组（如 CASE_STATUS、CASE_LEVEL），
    每组下的 value + label 构成一个可选项。
    """
    __tablename__ = "case_config"

    config_key = Column(String(255), nullable=False, index=True, comment="配置键（业务分组，如 CASE_STATUS）")
    label = Column(String(255), nullable=False, comment="配置标签（前端展示名称）")
    value = Column(String(255), nullable=False, comment="配置值（业务取值，转字符串存储）")

    color = Column(String(50), nullable=True, comment="配置颜色（前端徽章颜色，如 success/warning/default）")
    description = Column(String(500), nullable=True, comment="配置描述")
    sort = Column(Integer, nullable=True, default=0, comment="排序（同 config_key 组内排序）")
    enabled = Column(Boolean, nullable=True, default=True, comment="是否启用")

    def __repr__(self) -> str:
        return (
            f"<CaseConfig(id={self.id}, config_key={self.config_key}, "
            f"label={self.label}, value={self.value}, sort={self.sort}, enabled={self.enabled})>"
        )
