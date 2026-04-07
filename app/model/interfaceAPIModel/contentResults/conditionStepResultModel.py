#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : conditionStepResultModel
# @Software: PyCharm
# @Desc: 条件步骤执行结果模型

from sqlalchemy import Column, INTEGER, ForeignKey, JSON, String, relationship

from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class ConditionStepResult(BaseStepResult):
    """
    条件步骤执行结果
    
    content_name: 固定为 "条件判断"
    content_desc: 从关联的 InterfaceCondition 获取
    """
    __tablename__ = "interface_case_content_result_condition"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_CONDITION}

    step_result_id = step_result_id_column()

    condition_id = Column(
        INTEGER,
        ForeignKey('interface_condition.id', ondelete='SET NULL'),
        nullable=True,
        comment="关联条件ID"
    )

    # 条件键值（冗余便于查询）
    condition_key = Column(String(40), nullable=True, comment="条件Key")
    condition_value = Column(String(40), nullable=True, comment="条件Value")
    condition_operator = Column(INTEGER, nullable=True, comment="条件运算符")

    # 条件判断结果
    evaluate_result = Column(INTEGER, nullable=True, comment="条件判断结果 1通过 0不通过")
    condition_expression = Column(JSON, nullable=True, comment="条件表达式")
    actual_values = Column(JSON, nullable=True, comment="实际值")

    # relationship
    condition = relationship("InterfaceCondition", foreign_keys=[condition_id], lazy="noload")

    @property
    def content_name(self) -> str:
        return "条件判断"

    @property
    def content_desc(self) -> str:
        if self.condition:
            return self.condition.condition_desc or ""
        return ""

    def __repr__(self):
        return f"<ConditionStepResult(id={self.id}, condition_id={self.condition_id}, evaluate={self.evaluate_result})>"
