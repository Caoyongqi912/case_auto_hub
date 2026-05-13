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

    __table_args__ = (
        Index('idx_plan_id', 'plan_id'),
        Index('idx_parent_id', 'parent_id'),
    )

    @property
    def map(self):
        return {
            "key": self.id,
            "title": self.title,
            "parent_id": self.parent_id,
            "plan_id": self.plan_id,
            "order": self.order
        }

    def __repr__(self):
        return f"<PlanModule(id={self.id}, title={self.title}, parent_id={self.parent_id}, plan_id={self.plan_id})>"