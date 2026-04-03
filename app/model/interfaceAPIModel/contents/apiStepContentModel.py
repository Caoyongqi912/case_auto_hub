#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : apiStepContentModel
# @Software: PyCharm
# @Desc: API步骤内容模型

from sqlalchemy import Column, INTEGER, ForeignKey, relationship
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType


class APIStepContent(InterfaceCaseContents):
    """
    API步骤
    
    content_name: 从关联的 Interface 获取
    content_desc: 从关联的 Interface 获取
    """
    __tablename__ = "interface_case_step_api"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API}

    step_content_id = step_content_id_column()
    target_id = Column(INTEGER, ForeignKey('interface.id', ondelete='CASCADE'), nullable=True, comment="关联接口ID")
    is_common_api = Column(INTEGER, default=1, nullable=False, comment="是否公共API")

    interface_api = relationship("InterfaceModel", foreign_keys=[target_id], lazy="noload")

    @property
    def content_name(self) -> str:
        if self.interface_api:
            return self.interface_api.name
        return "未知接口"

    @property
    def content_desc(self) -> str:
        if self.interface_api:
            return self.interface_api.method or ""
        return ""

    def __repr__(self):
        return f"<APIStepContent(id={self.id}, target_id={self.target_id}, is_common={self.is_common_api})>"
