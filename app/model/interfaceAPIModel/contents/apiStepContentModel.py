#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : apiStepContentModel
# @Software: PyCharm
# @Desc: API步骤内容模型


from typing import Optional, Set

from sqlalchemy import Column, INTEGER, ForeignKey
from sqlalchemy.orm import relationship

from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from app.model.interfaceAPIModel.interfaceModel import Interface
from enums.CaseEnum import CaseStepContentType


class APIStepContent(InterfaceCaseContents):
    """
    API步骤

    content_name: 从关联的 Interface 获取
    content_desc: 从关联的 Interface 获取
    is_common_api: 从关联的 Interface 获取
    """
    __tablename__ = "interface_case_step_api"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API}

    step_content_id = step_content_id_column()
    target_id = Column(INTEGER, ForeignKey('interface.id', ondelete='CASCADE'), nullable=True, comment="关联接口ID")

    interface_api = relationship(Interface, foreign_keys=[target_id], lazy="selectin")

    def _get_default_name(self) -> str:
        if self.interface_api:
            return self.interface_api.interface_name
        return "未知接口"

    @property
    def content_desc(self) -> str:
        if self.interface_api:
            return self.interface_api.interface_method or ""
        return ""

    @property
    def is_common_api(self) -> int:
        if self.interface_api:
            return self.interface_api.is_common
        return 1

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        result = super().to_dict(exclude)
        if 'is_common_api' not in (exclude or set()):
            result['is_common_api'] = self.is_common_api
        return result

    def __repr__(self):
        return f"<APIStepContent(id={self.id}, target_id={self.target_id}>"

    @property
    def dynamic(self) -> str:
        return f"接口 {self.interface_api.interface_name}"