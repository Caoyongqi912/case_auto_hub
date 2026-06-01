#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : test_case_step
# @Software: PyCharm
from sqlalchemy import Column, ForeignKey, String, Integer, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.model.basic import BaseModel


class TestCaseStep(BaseModel):
    __tablename__ = "case_sub_step"

    test_case_id = Column(Integer, ForeignKey("test_case.id", ondelete="cascade"), nullable=False,
                          index=True, comment="用例步骤id")
    action = Column(String(500), nullable=True, comment="执行")
    expected_result = Column(String(500), nullable=True, comment="预期")
    order = Column(Integer, nullable=False, comment="排序")

    case = relationship("TestCase", back_populates="case_sub_steps")

    def __repr__(self):
        return f"<TestCaseStep(id={self.id},do={self.action}) >"
    


class TestCaseStepResult(BaseModel):
    """用例步骤结果模型"""
    __tablename__ = "case_sub_step_result"
    plan_id = Column(Integer, ForeignKey("case_plan.id", ondelete="cascade"), nullable=False,
                          comment="计划ID")
    step_id = Column(Integer, ForeignKey("case_sub_step.id", ondelete="cascade"), nullable=False,
                          comment="用例步骤id")
    actual_result = Column(String(500), nullable=True, comment="实际结果")
    status = Column(Integer, default=0, nullable=True, comment="0 未填写 1 通过 2 阻塞 3 跳过 4 其他")
    bug_url = Column(String(500), nullable=True, comment="bug链接")

    __table_args__ = (
        Index('idx_plan_step', 'plan_id', 'step_id'),
        UniqueConstraint('plan_id', 'step_id', name='uq_plan_step'),
    )

    def __repr__(self):
        return f"<TestCaseStepResult(plan_id={self.plan_id},step_id={self.step_id},actual_result={self.actual_result},status={self.status},bug_url={self.bug_url}) >"
