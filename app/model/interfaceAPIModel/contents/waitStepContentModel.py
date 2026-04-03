#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : waitStepContentModel
# @Software: PyCharm
# @Desc: 等待步骤内容模型

from sqlalchemy import Column, FLOAT
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType


class WaitStepContent(InterfaceCaseContents):
    """
    等待步骤（自包含数据，无需关联其他表）
    
    content_name: 固定为 "等待"
    content_desc: 根据等待时间生成
    """
    __tablename__ = "interface_case_step_wait"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_WAIT}

    step_content_id = step_content_id_column()
    wait_time = Column(FLOAT, nullable=False, comment="等待时间(秒)")

    @property
    def content_name(self) -> str:
        return "等待"

    @property
    def content_desc(self) -> str:
        return f"等待 {self.wait_time} 秒"

    def __repr__(self):
        return f"<WaitStepContent(id={self.id}, wait_time={self.wait_time})>"
