#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : interfaceCaseContentsModel.py
# @Software: PyCharm
# @Desc: 用例步骤内容基类

from datetime import datetime
from typing import ClassVar, Optional, Set

from sqlalchemy import Column, INTEGER

from app.model import BaseModel


def step_content_id_column():
    """子表主键生成器"""
    from sqlalchemy import ForeignKey
    return Column(
        INTEGER,
        ForeignKey('interface_case_step_content.id', ondelete='CASCADE'),
        primary_key=True
    )


class InterfaceCaseContents(BaseModel):
    """
    步骤内容基类 - Joined Table Inheritance

    设计说明：
    - 使用 SQLAlchemy Joined Table Inheritance 实现多态
    - 基类表存储公共字段，子类表存储特有字段
    - 通过 polymorphic_on (content_type) 区分类型
    """
    __tablename__ = "interface_case_step_content"
    __allow_unmapped__ = True

    content_type = Column(INTEGER, nullable=False, index=True, comment="步骤类型")
    enable = Column(INTEGER, default=1, nullable=False, comment="是否启用")

    target_id: ClassVar[int | None] = None

    __mapper_args__ = {
        'polymorphic_on': content_type,
        'polymorphic_identity': None,
        'with_polymorphic': '*',
    }

    @property
    def content_name(self) -> str:
        """步骤名称 - 由子类实现"""
        return ""

    @property
    def content_desc(self) -> str:
        """步骤描述 - 由子类实现"""
        return ""

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """
        转换为字典 - 包含基类字段 + 子类字段 + 计算属性

        Args:
            exclude: 要排除的字段集合

        Returns:
            包含完整内容的字典
        """
        result = {
            'content_type': self.content_type,
            'target_id': self.target_id,
            'content_name': self.content_name,
            'content_desc': self.content_desc,
            "enable": self.enable,
            "id": self.id,
            "uid": self.uid,
            "creator": self.creator,
            "creatorName": self.creatorName,
            "create_time": self.create_time,
            "update_time": self.update_time,
        }

        for mapper in self.__class__.__mapper__.self_and_descendants:
            if mapper.local_table.name != self.__tablename__:
                for col in mapper.local_table.columns:
                    if hasattr(self, col.name):
                        value = getattr(self, col.name)
                        if isinstance(value, datetime):
                            result[col.name] = value.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            result[col.name] = value

        if exclude:
            for key in exclude:
                result.pop(key, None)

        return result

    def __repr__(self):
        return f"<InterfaceCaseContents(id={self.id}, type={self.content_type}, enable={self.enable})>"
