#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : loopStepResultModel
# @Software: PyCharm
# @Desc: 循环步骤执行结果模型

from sqlalchemy import Column, INTEGER, ForeignKey
from sqlalchemy.orm import relationship
from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class LoopStepResult(BaseStepResult):
    """
    循环步骤执行结果
    
    content_name: 根据循环类型生成
    content_desc: 从关联的 InterfaceLoopModal 获取
    """
    __tablename__ = "interface_case_content_result_loop"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_LOOP}

    step_result_id = step_result_id_column()

    loop_id = Column(
        INTEGER,
        ForeignKey('interface_loop.id', ondelete='SET NULL'),
        nullable=True,
        comment="关联循环配置ID"
    )

    # 循环类型
    loop_type = Column(INTEGER, nullable=True, comment="循环类型")
    loop_type_name = Column(INTEGER, nullable=True, comment="循环类型名称")

    # 循环执行信息
    current_loop = Column(INTEGER, default=0, comment="当前循环次数")
    total_loops = Column(INTEGER, default=0, comment="总循环次数")
    loop_items_count = Column(INTEGER, nullable=True, comment="列表项数量")

    # relationship
    loop = relationship("InterfaceLoopModal", foreign_keys=[loop_id], lazy="noload")

    @property
    def content_name(self) -> str:
        from enums.CaseEnum import LoopTypeEnum
        if self.loop_type:
            loop_type_enum = LoopTypeEnum(self.loop_type)
            type_names = {
                LoopTypeEnum.LoopTimes: "次数循环",
                LoopTypeEnum.LoopItems: "列表循环",
                LoopTypeEnum.LoopCondition: "条件循环",
            }
            return type_names.get(loop_type_enum, "循环")
        return "循环"

    @property
    def content_desc(self) -> str:
        return f"循环次数: {self.total_loops or 0}"

    def __repr__(self):
        return f"<LoopStepResult(id={self.id}, loop_id={self.loop_id}, current={self.current_loop}, total={self.total_loops})>"
