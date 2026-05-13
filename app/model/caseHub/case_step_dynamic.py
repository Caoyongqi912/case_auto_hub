#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : case_step_dynamic
# @Software: PyCharm
from sqlalchemy import Column, ForeignKey, String, Integer

from app.model.basic import BaseModel


class CaseStepDynamic(BaseModel):
    __tablename__ = "case_dynamic"

    test_case_id = Column(Integer, ForeignKey("test_case.id", ondelete='cascade'), nullable=False, primary_key=True,
                          comment="用例步骤id")
    description = Column(String(500), nullable=False, comment="动态描述")

    def __repr__(self):
        return f"<CaseStepDynamic(id={self.id},description={self.description}) >"