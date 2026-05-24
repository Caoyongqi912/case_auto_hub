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
    description = Column(String(500), nullable=False, comment="动态描述")

    __table_args__ = (
        Index('idx_case_dynamic_case_id', 'test_case_id'),
    )

    def __repr__(self):
        return f"<CaseStepDynamic(id={self.id}, test_case_id={self.test_case_id}, description={self.description})>"
