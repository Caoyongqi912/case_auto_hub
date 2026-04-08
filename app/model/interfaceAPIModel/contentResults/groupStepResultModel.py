#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : groupStepResultModel
# @Software: PyCharm
# @Desc: API组步骤执行结果模型

from sqlalchemy import Column, INTEGER, ForeignKey, String
from sqlalchemy.orm import relationship

from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class GroupStepResult(BaseStepResult):
    """
    API组步骤执行结果
    
    content_name: 从关联的 InterfaceGroup 获取
    content_desc: 从关联的 InterfaceGroup 获取
    """
    __tablename__ = "interface_case_content_result_group"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_GROUP}

    step_result_id = step_result_id_column()

    group_id = Column(
        INTEGER,
        ForeignKey('interface_group.id', ondelete='SET NULL'),
        nullable=True,
        comment="关联接口组ID"
    )

    # 组名称（冗余便于查询）
    group_name = Column(String(40), nullable=True, comment="组名称")

    # 组执行统计
    total_apis = Column(INTEGER, default=0, comment="组内接口总数")
    success_apis = Column(INTEGER, default=0, comment="成功数量")
    fail_apis = Column(INTEGER, default=0, comment="失败数量")

    # relationship
    group = relationship("InterfaceGroup", foreign_keys=[group_id], lazy="noload")

    @property
    def content_name(self) -> str:
        if self.group:
            return self.group.interface_group_name
        return self.group_name or "未知接口组"

    @property
    def content_desc(self) -> str:
        if self.group:
            return self.group.interface_group_description or ""
        return ""

    def __repr__(self):
        return f"<GroupStepResult(id={self.id}, group_id={self.group_id}, success={self.success_apis}, fail={self.fail_apis})>"
