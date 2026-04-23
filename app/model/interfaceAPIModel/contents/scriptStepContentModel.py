#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : scriptStepContentModel
# @Software: PyCharm
# @Desc: 脚本步骤内容模型
from typing import Optional, Set

from sqlalchemy import Column, TEXT
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType


class ScriptStepContent(InterfaceCaseContents):
    """
    脚本步骤（自包含数据，无需关联其他表）
    
    content_name: 固定为 "执行脚本"
    content_desc: 脚本内容预览
    """
    __tablename__ = "interface_case_step_script"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_SCRIPT}

    step_content_id = step_content_id_column()
    script_text = Column(TEXT, nullable=False, comment="脚本文本")

    def _get_default_name(self) -> str:
        return "执行脚本"

    @property
    def content_desc(self) -> str:
        if self.script_text:
            preview = self.script_text[:50]
            return preview + "..." if len(self.script_text) > 50 else preview
        return ""

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        result = super().to_dict(exclude)
        if 'script_text' not in (exclude or set()):
            result['script_text'] = self.script_text
        return result

    def __repr__(self):
        return f"<ScriptStepContent(id={self.id}, script_len={len(self.script_text) if self.script_text else 0})>"

    @property
    def dynamic(self):
        return f"脚本步骤 {self.script_text[:10] if self.script_text else ''}"
