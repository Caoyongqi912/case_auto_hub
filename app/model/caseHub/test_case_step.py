#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : test_case_step
# @Software: PyCharm
from sqlalchemy import Column, ForeignKey, String, Integer
from sqlalchemy.orm import relationship

from app.model.basic import BaseModel


class TestCaseStep(BaseModel):
    __tablename__ = "case_sub_step"

    test_case_id = Column(Integer, ForeignKey("test_case.id", ondelete="cascade"), nullable=False,
                          comment="用例步骤id")
    action = Column(String(500), nullable=True, comment="执行")
    expected_result = Column(String(500), nullable=True, comment="预期")
    order = Column(Integer, nullable=False, comment="排序")

    case = relationship("TestCase", back_populates="case_sub_steps")

    def __repr__(self):
        return f"<TestCaseStep(id={self.id},do={self.action}) >"