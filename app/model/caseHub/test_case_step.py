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
    """ 
    用例步骤结果模型
    记录每个计划每个步骤的测试结果.
    
    case 可能被多个计划引用, 每个计划都有一个步骤结果.
    所以每个步骤结果都有一个 plan_id, 一个 step_id.  即每个步骤结果都有一个唯一的组合键.
    """
    __tablename__ = "case_sub_step_result"
    plan_id = Column(Integer, ForeignKey("case_plan.id", ondelete="cascade"), nullable=False,
                          comment="计划ID")
    step_id = Column(Integer, ForeignKey("case_sub_step.id", ondelete="cascade"), nullable=False,
                          comment="用例步骤id")
    actual_result = Column(String(500), nullable=True, comment="实际结果")
    first_status = Column(String(255),  comment="一轮测试状态")
    second_status = Column(String(255),  comment="二轮测试状态")   
    bug_url = Column(String(500), nullable=True, comment="bug链接")

    __table_args__ = (
        Index('idx_plan_step', 'plan_id', 'step_id'),
        UniqueConstraint('plan_id', 'step_id', name='uq_plan_step'),
    )

    def __repr__(self):
        return f"<TestCaseStepResult(plan_id={self.plan_id},step_id={self.step_id},actual_result={self.actual_result}, bug_url={self.bug_url},first_status={self.first_status},second_status={self.second_status}) >"
