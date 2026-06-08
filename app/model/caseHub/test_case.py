#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : test_case
# @Software: PyCharm
from sqlalchemy import Column, ForeignKey, String, Boolean, Integer

from sqlalchemy.orm import relationship
from app.model.base import User
from app.model.basic import BaseModel


class TestCase(BaseModel):
    __tablename__ = "test_case"

    case_name = Column(String(500), nullable=False, comment="用例步骤名称")
    case_tag = Column(String(100), nullable=True, comment="用例步骤标签")
    case_setup = Column(String(500), nullable=True, comment="用例步骤前置条件")
    case_mark = Column(String(500), nullable=True, comment="用例步骤备注")

    case_level = Column(String(255), default="P2", index=True, comment="用例等级")
    case_type = Column(String(255), nullable=True, comment="用例类型 1 冒烟 2功能 3回归")

    is_common = Column(Boolean, default=False, index=True, comment="用例库")
    module_id = Column(Integer, ForeignKey('module.id', ondelete='set null'), nullable=True, comment="所属模块")
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False, comment="所属项目")

    
    from app.model.caseHub.test_case_step import TestCaseStep
    case_sub_steps = relationship(TestCaseStep, back_populates="case", lazy="select", order_by=TestCaseStep.order)

    @classmethod
    def new_default(cls, user: User) -> "TestCase":
        obj = cls()
        obj.case_name = "测试用例"
        obj.creator = user.id
        obj.creatorName = user.username
        return obj

    def __repr__(self):
        return f"<TestCase(id={self.id},case_name={self.case_name}) >"
