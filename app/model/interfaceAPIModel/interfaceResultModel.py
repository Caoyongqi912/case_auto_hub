#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/10
# @Author : cyq
# @File : interfaceResultModel
# @Software: PyCharm
# @Desc: 接口执行结果模型 - 存储 API 真正的请求/响应详情

from datetime import datetime

from sqlalchemy import Column, INTEGER, String, TEXT, JSON, Float, DATETIME, ForeignKey
from sqlalchemy.orm import relationship

from app.model import BaseModel


class InterfaceResult(BaseModel):
    """
    API 执行结果

    存储 API 请求/响应的完整详情
    由 APIStepResult.target_result_id 关联
    """
    __tablename__ = "interface_result"

    api_id = Column(
        INTEGER,
        ForeignKey('interface.id', ondelete='SET NULL'),
        nullable=True,
        comment="关联的API ID"
    )

    api_name = Column(String(100), nullable=True, comment="API名称")
    api_uid = Column(String(20), nullable=True, comment="API UID")
    api_desc = Column(String(250), nullable=True, comment="API描述")

    request_method = Column(String(10), nullable=True, comment="请求方法 GET/POST/PUT/DELETE")
    request_url = Column(String(500), nullable=True, comment="请求地址")
    request_headers = Column(JSON, nullable=True, comment="请求头")
    request_params = Column(JSON, nullable=True, comment="URL参数")
    request_body = Column(TEXT, nullable=True, comment="请求体")
    request_content_type = Column(String(50), nullable=True, comment="Content-Type")

    response_status = Column(INTEGER, nullable=True, comment="响应状态码")
    response_headers = Column(JSON, nullable=True, comment="响应头")
    response_body = Column(TEXT, nullable=True, comment="响应体")
    response_time = Column(Float, nullable=True, comment="响应时间(ms)")

    extracts = Column(JSON, nullable=True, comment="变量提取")
    asserts = Column(JSON, nullable=True, comment="断言结果")

    starter_id = Column(INTEGER, nullable=True, comment="运行人ID")
    starter_name = Column(String(20), nullable=True, comment="运行人姓名")

    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    use_time = Column(String(50), nullable=True, comment="耗时")

    result = Column(String(10), nullable=True, comment="执行结果 SUCCESS/FAIL")
    error_message = Column(TEXT, nullable=True, comment="错误信息")

    env_id = Column(INTEGER, nullable=True, comment="运行环境ID")
    env_name = Column(String(250), nullable=True, comment="运行环境名称")

    case_result_id = Column(
        INTEGER,
        ForeignKey('interface_case_result.id', ondelete='CASCADE'),
        nullable=True,
        comment="关联的用例结果ID"
    )

    case_result = relationship(
        "CaseStepResult",
        foreign_keys=[case_result_id],
        lazy="noload"
    )

    @property
    def base_info(self) -> dict:
        """基本信息"""
        return {
            "id": self.id,
            "api_id": self.api_id,
            "api_name": self.api_name,
            "api_uid": self.api_uid,
            "request_method": self.request_method,
            "request_url": self.request_url,
            "response_status": self.response_status,
            "response_time": self.response_time,
            "result": self.result,
            "use_time": self.use_time,
        }

    def __repr__(self):
        return f"<InterfaceResult(id={self.id}, api_id={self.api_id}, api_name={self.api_name}, status={self.response_status}, result={self.result})>"
