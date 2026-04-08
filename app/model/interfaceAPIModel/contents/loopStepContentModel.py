#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : loopStepContentModel
# @Software: PyCharm
# @Desc: 循环步骤内容模型

from sqlalchemy import Column, INTEGER, ForeignKey
from sqlalchemy.orm import relationship
from app.model.interfaceAPIModel.interfaceLoopModel import InterfaceLoop
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType, LoopTypeEnum


class LoopStepContent(InterfaceCaseContents):
    """
    循环步骤
    
    content_name: 根据循环类型生成
    content_desc: 从关联的 InterfaceLoop 获取
    """
    __tablename__ = "interface_case_step_loop"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_LOOP}

    step_content_id = step_content_id_column()
    target_id = Column(INTEGER, ForeignKey('interface_loop.id', ondelete='CASCADE'), nullable=True, comment="关联循环配置ID")

    interface_loop = relationship(InterfaceLoop, foreign_keys=[target_id], lazy="noload")

    @property
    def content_name(self) -> str:
        if self.interface_loop:
            loop_type = LoopTypeEnum(self.interface_loop.loop_type)
            type_names = {
                LoopTypeEnum.LoopTimes: "次数循环",
                LoopTypeEnum.LoopItems: "列表循环",
                LoopTypeEnum.LoopCondition: "条件循环",
            }
            return type_names.get(loop_type, "循环")
        return "循环"

    @property
    def content_desc(self) -> str:
        if self.interface_loop:
            return f"循环次数: {self.interface_loop.loop_count or 0}"
        return ""

    def __repr__(self):
        return f"<LoopStepContent(id={self.id}, target_id={self.target_id})>"
