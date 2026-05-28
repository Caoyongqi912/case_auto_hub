#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : case_step_dynamic
# @Software: PyCharm
from sqlalchemy import Column, ForeignKey, String, Integer, Index

from app.model.basic import BaseModel


class CaseStepDynamic(BaseModel):
    __tablename__ = "case_dynamic"

    test_case_id = Column(Integer, ForeignKey("test_case.id", ondelete='cascade'), nullable=False,
                          comment="用例ID")
    plan_id = Column(Integer, ForeignKey("case_plan.id", ondelete='cascade'), nullable=True,
                     comment="计划ID（为空表示用例自身变更，非空表示计划关联变更）")
    description = Column(String(500), nullable=False, comment="动态描述")

    __table_args__ = (
        Index('idx_case_dynamic_case_id', 'test_case_id'),
        Index('idx_case_dynamic_plan_id', 'plan_id'),
    )

    def __repr__(self):
        return f"<CaseStepDynamic(id={self.id}, test_case_id={self.test_case_id}, plan_id={self.plan_id}, description={self.description})>"
