#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : plan_module
# @Software: PyCharm
# @Desc: 计划内模块（树形结构）
from sqlalchemy import Column, Integer, String, ForeignKey, Index

from app.model.basic import BaseModel


class PlanModule(BaseModel):
    __tablename__ = "plan_module"

    plan_id = Column(Integer, ForeignKey('case_plan.id', ondelete='CASCADE'), nullable=False, comment="所属计划")
    parent_id = Column(Integer, nullable=True, comment="父级模块ID，根模块为NULL")
    title = Column(String(50), nullable=False, comment="模块名称")
    order = Column(Integer, default=0, comment="排序顺序")
    source_module_id = Column(
        Integer,
        ForeignKey('module.id', ondelete='SET NULL'),
        nullable=True,
        comment="来源用例库模块ID（从用例库复制/关联时记录）"
    )

    __table_args__ = (
        Index('idx_plan_id', 'plan_id'),
        Index('idx_parent_id', 'parent_id'),
        Index('idx_source_module_id', 'source_module_id'),
    )

    @property
    def map(self):
        return {
            "id": self.id,
            "title": self.title,
            "parent_id": self.parent_id,
            "plan_id": self.plan_id,
            "order": self.order
        }

    def __repr__(self):
        return (
            f"<PlanModule(id={self.id}, title={self.title}, parent_id={self.parent_id}, "
            f"plan_id={self.plan_id}, source_module_id={self.source_module_id})>"
        )