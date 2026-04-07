#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : waitStepResultModel
# @Software: PyCharm
# @Desc: 等待步骤执行结果模型

from sqlalchemy import Column, FLOAT

from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class WaitStepResult(BaseStepResult):
    """
    等待步骤执行结果
    
    content_name: 固定为 "等待"
    content_desc: 根据等待时间生成
    """
    __tablename__ = "interface_case_content_result_wait"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_WAIT}

    step_result_id = step_result_id_column()

    # 等待配置
    wait_time = Column(FLOAT, nullable=True, comment="等待时间(秒)")
    actual_wait_time = Column(FLOAT, nullable=True, comment="实际等待时间(秒)")

    @property
    def content_name(self) -> str:
        return "等待"

    @property
    def content_desc(self) -> str:
        return f"等待 {self.wait_time or 0} 秒"

    def __repr__(self):
        return f"<WaitStepResult(id={self.id}, wait_time={self.wait_time})>"
