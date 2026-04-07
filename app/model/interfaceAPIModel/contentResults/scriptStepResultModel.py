#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : scriptStepResultModel
# @Software: PyCharm
# @Desc: 脚本步骤执行结果模型

from sqlalchemy import Column, JSON, TEXT, String

from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class ScriptStepResult(BaseStepResult):
    """
    脚本步骤执行结果
    
    content_name: 固定为 "执行脚本"
    content_desc: 脚本内容预览
    """
    __tablename__ = "interface_case_content_result_script"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_SCRIPT}

    step_result_id = step_result_id_column()

    # 脚本内容
    script_text = Column(TEXT, nullable=True, comment="脚本内容")

    # 脚本提取结果
    script_extracts = Column(JSON, nullable=True, comment="脚本提取变量")

    # 脚本执行日志
    script_log = Column(TEXT, nullable=True, comment="脚本执行日志")
    script_error = Column(TEXT, nullable=True, comment="脚本错误信息")

    @property
    def content_name(self) -> str:
        return "执行脚本"

    @property
    def content_desc(self) -> str:
        if self.script_text:
            preview = self.script_text[:50]
            return preview + "..." if len(self.script_text) > 50 else preview
        return ""

    def __repr__(self):
        return f"<ScriptStepResult(id={self.id}, success={self.is_success}, error={self.script_error})>"
