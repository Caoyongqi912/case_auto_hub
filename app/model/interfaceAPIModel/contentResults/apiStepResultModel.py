#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : apiStepResultModel
# @Software: PyCharm
# @Desc: API步骤执行结果模型

from sqlalchemy import Column, INTEGER, ForeignKey, JSON, TEXT, String
from sqlalchemy.orm import relationship
from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class APIStepResult(BaseStepResult):
    """
    API步骤执行结果
    
    content_name: 从关联的 Interface 获取
    content_desc: 从关联的 Interface 获取
    """
    __tablename__ = "interface_case_content_result_api"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API}

    step_result_id = step_result_id_column()

    # 关联的接口ID
    interface_id = Column(
        INTEGER,
        ForeignKey('interface.id', ondelete='SET NULL'),
        nullable=True,
        comment="关联接口ID"
    )

    # 接口名称（冗余但便于查询）
    interface_name = Column(String(100), nullable=True, comment="接口名称")

    # 请求信息
    request_info = Column(JSON, nullable=True, comment="实际请求记录")
    request_url = Column(String(500), nullable=True, comment="请求URL")
    request_method = Column(String(10), nullable=True, comment="请求方法")
    request_headers = Column(JSON, nullable=True, comment="请求头")
    request_body = Column(JSON, nullable=True, comment="请求体")

    # 响应信息
    response_status = Column(INTEGER, nullable=True, comment="响应状态码")
    response_headers = Column(JSON, nullable=True, comment="响应头")
    response_body = Column(TEXT, nullable=True, comment="响应体")

    # 提取变量
    extracts = Column(JSON, nullable=True, comment="提取的变量")

    # 断言结果
    asserts = Column(JSON, nullable=True, comment="断言结果")

    # relationship
    interface = relationship("Interface", foreign_keys=[interface_id], lazy="noload")

    @property
    def content_name(self) -> str:
        if self.interface:
            return self.interface.interface_name
        return self.interface_name or "未知接口"

    @property
    def content_desc(self) -> str:
        if self.interface:
            return self.interface.interface_method or ""
        return ""

    def __repr__(self):
        return f"<APIStepResult(id={self.id}, interface_id={self.interface_id}, url={self.request_url}, success={self.is_success})>"
