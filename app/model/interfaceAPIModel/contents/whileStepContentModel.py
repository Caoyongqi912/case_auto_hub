#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : whileStepContentModel
# @Software: PyCharm
# @Desc: While循环步骤内容模型

from sqlalchemy import Column, INTEGER, ForeignKey, relationship
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType


class WhileStepContent(InterfaceCaseContents):
    """
    While循环步骤
    
    content_name: 固定为 "While循环"
    content_desc: 从关联的 InterfaceCondition 获取
    """
    __tablename__ = "interface_case_step_while"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_WHILE}

    step_content_id = step_content_id_column()
    target_id = Column(INTEGER, ForeignKey('interface_condition.id', ondelete='CASCADE'), nullable=True, comment="关联条件ID")

    interface_condition = relationship("InterfaceCondition", foreign_keys=[target_id], lazy="noload")

    @property
    def content_name(self) -> str:
        return "While循环"

    @property
    def content_desc(self) -> str:
        if self.interface_condition:
            return self.interface_condition.condition_desc or ""
        return ""

    def __repr__(self):
        return f"<WhileStepContent(id={self.id}, target_id={self.target_id})>"
