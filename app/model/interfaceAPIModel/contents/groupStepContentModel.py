#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : groupStepContentModel
# @Software: PyCharm
# @Desc: API组步骤内容模型

from sqlalchemy import Column, INTEGER, ForeignKey
from sqlalchemy.orm import relationship
from app.model.interfaceAPIModel.interfaceGroupModel import InterfaceGroup
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType


class GroupStepContent(InterfaceCaseContents):
    """
    API组步骤
    
    content_name: 从关联的 InterfaceGroup 获取
    content_desc: 从关联的 InterfaceGroup 获取
    """
    __tablename__ = "interface_case_step_group"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_GROUP}

    step_content_id = step_content_id_column()
    target_id = Column(INTEGER, ForeignKey('interface_group.id', ondelete='CASCADE'), nullable=True, comment="关联接口组ID")

    interface_group = relationship(InterfaceGroup, foreign_keys=[target_id], lazy="noload")

    @property
    def content_name(self) -> str:
        if self.interface_group:
            return self.interface_group.interface_group_name
        return "未知接口组"

    @property
    def content_desc(self) -> str:
        if self.interface_group:
            return self.interface_group.interface_group_description or ""
        return ""

    def __repr__(self):
        return f"<GroupStepContent(id={self.id}, target_id={self.target_id})>"
