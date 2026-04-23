#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : assertStepContentModel
# @Software: PyCharm
# @Desc: 断言步骤内容模型
from typing import Optional, Set

from sqlalchemy import Column, JSON
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType


class AssertStepContent(InterfaceCaseContents):
    """
    断言步骤（自包含数据，无需关联其他表）
    
    content_name: 固定为 "断言"
    content_desc: 断言数量描述
    """
    __tablename__ = "interface_case_step_assert"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_ASSERT}

    step_content_id = step_content_id_column()
    assert_list = Column(JSON, nullable=True, comment="断言配置列表")

    def _get_default_name(self) -> str:
        return "断言"

    @property
    def content_desc(self) -> str:
        count = len(self.assert_list) if self.assert_list else 0
        return f"共 {count} 条断言"

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        result = super().to_dict(exclude)
        if 'assert_list' not in (exclude or set()):
            result['assert_list'] = self.assert_list
        return result

    def __repr__(self):
        return f"<AssertStepContent(id={self.id}, assert_count={len(self.assert_list) if self.assert_list else 0})>"

    @property
    def dynamic(self) -> str:
        return f"{self._get_default_name()}"