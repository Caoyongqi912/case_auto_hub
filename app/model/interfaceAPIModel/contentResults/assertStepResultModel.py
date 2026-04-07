#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : assertStepResultModel
# @Software: PyCharm
# @Desc: 断言步骤执行结果模型

from sqlalchemy import Column, JSON

from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class AssertStepResult(BaseStepResult):
    """
    断言步骤执行结果
    
    content_name: 固定为 "断言"
    content_desc: 断言数量描述
    """
    __tablename__ = "interface_case_content_result_assert"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_ASSERT}

    step_result_id = step_result_id_column()

    # 断言配置
    assert_config = Column(JSON, nullable=True, comment="断言配置")

    # 断言结果详情
    assert_results = Column(JSON, nullable=True, comment="断言结果列表")
    total_asserts = Column(JSON, nullable=True, comment="断言总数")
    passed_asserts = Column(JSON, nullable=True, comment="通过数量")
    failed_asserts = Column(JSON, nullable=True, comment="失败数量")

    # 断言失败的详情
    failed_details = Column(JSON, nullable=True, comment="失败断言详情")

    @property
    def content_name(self) -> str:
        return "断言"

    @property
    def content_desc(self) -> str:
        if self.assert_results:
            passed = len([r for r in self.assert_results if r.get('is_success')])
            total = len(self.assert_results)
            return f"通过 {passed}/{total}"
        return "共 0 条断言"

    def __repr__(self):
        return f"<AssertStepResult(id={self.id}, passed={self.passed_asserts}, failed={self.failed_asserts})>"
