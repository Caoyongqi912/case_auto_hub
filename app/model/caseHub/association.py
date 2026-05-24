#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : association
# @Software: PyCharm
# @Desc: 关联表定义
from sqlalchemy import Column, Integer, ForeignKey, Index, Boolean, String

from app.model.basic import base


class RequirementCaseAssociation(base):
    __tablename__ = "requirement_case_association"

    requirement_id = Column(Integer, ForeignKey('requirement.id', ondelete="CASCADE"), primary_key=True)
    case_id = Column(Integer, ForeignKey('test_case.id', ondelete="CASCADE"), primary_key=True)
    is_review = Column(Boolean, default=False, comment="是否审核")
    case_type = Column(Integer, default=1, index=True, comment="用例步骤类型 1'普通' | 2'冒烟' | 3 回归")
    case_level = Column(String(5), nullable=False, index=True, default="P2", comment="用例步骤等级 P1 P2 P0")
    case_status = Column(Integer, default=0, index=True, comment="用例步骤状态  0 | 1 | 2; // 0:未开始 1:通过 2:失败")

    order = Column(Integer)

    __table_args__ = (
        Index('idx_req_case_order', 'requirement_id', 'order'),
        Index('idx_case_id', 'case_id'),
    )


class PlanRequirementAssociation(base):
    __tablename__ = "plan_requirement_association"

    plan_id = Column(Integer, ForeignKey('case_plan.id', ondelete='CASCADE'), primary_key=True, comment="所属计划")
    requirement_id = Column(Integer, ForeignKey('requirement.id', ondelete='CASCADE'), primary_key=True, comment="需求ID")

    __table_args__ = (
        Index('idx_plan_req', 'plan_id', 'requirement_id'),
    )

    def __repr__(self):
        return f"<PlanRequirementAssociation(plan_id={self.plan_id}, requirement_id={self.requirement_id})>"


class PlanCaseAssociation(base):
    __tablename__ = "plan_case_association"

    plan_id = Column(Integer, ForeignKey('case_plan.id', ondelete='CASCADE'), nullable=False, primary_key=True, comment="所属计划")
    plan_module_id = Column(Integer, ForeignKey('plan_module.id', ondelete='CASCADE'), primary_key=True, nullable=False, comment="所属计划分组（创建计划时自动初始化根模块）")
    case_id = Column(Integer, ForeignKey('test_case.id', ondelete='CASCADE'), nullable=False, primary_key=True, comment="用例ID")

    is_review = Column(Boolean, default=False, comment="是否审核")
    case_status = Column(Integer, default=0, comment="用例状态 0:未开始 1:通过 2:失败 3:阻塞 4:跳过")
    bug_url = Column(String(500), nullable=True, comment="缺陷链接")
    order = Column(Integer, default=0, comment="排序顺序")

    __table_args__ = (
        Index('idx_plan_case', 'plan_id'),
        Index('idx_plan_module', 'plan_module_id'),
        Index('idx_case_id', 'case_id'),
        Index('idx_plan_order', 'plan_id', 'order'),
    )

    def __repr__(self):
        return f"<PlanCaseAssociation(plan_id={self.plan_id}, case_id={self.case_id}, case_status={self.case_status})>"


__all__ = [
    "RequirementCaseAssociation",
    "PlanRequirementAssociation",
    "PlanCaseAssociation",
]
