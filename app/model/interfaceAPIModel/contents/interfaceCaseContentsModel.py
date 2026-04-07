#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : interfaceCaseContentsModel.py
# @Software: PyCharm
# @Desc: 用例步骤内容基类

from abc import abstractmethod
from typing import Optional

from app.model import BaseModel
from sqlalchemy import Column, INTEGER, ForeignKey


def step_content_id_column():
    """子表主键生成器"""
    return Column(
        INTEGER,
        ForeignKey('interface_case_step_content.id', ondelete='CASCADE'),
        primary_key=True
    )


class InterfaceCaseContents(BaseModel):
    """
    步骤内容基类 - Joined Table Inheritance
    
    设计说明：
    - 移除冗余字段 content_name, content_desc
    - 子类通过 @property 提供虚拟的 content_name, content_desc
    - 需要关联目标表的子类使用 relationship
    """
    __tablename__ = "interface_case_step_content"

    content_type = Column(INTEGER, nullable=False, index=True, comment="步骤类型")
    enable = Column(INTEGER, default=1, nullable=False, comment="是否启用")
    target_id: Optional[int] = None  # 类型注解，用于子类继承时不报类型警告

    __mapper_args__ = {
        'polymorphic_on': content_type,
        'polymorphic_identity': None,
        'with_polymorphic': '*',
    }

    @property
    @abstractmethod
    def content_name(self) -> str:
        """步骤名称 - 由子类实现"""
        pass

    @property
    @abstractmethod
    def content_desc(self) -> str:
        """步骤描述 - 由子类实现"""
        pass

    def __repr__(self):
        return f"<InterfaceCaseContents(id={self.id}, type={self.content_type}, enable={self.enable})>"
