#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : dbStepContentModel
# @Software: PyCharm
# @Desc: 数据库步骤内容模型
from typing import Optional, Set

from app.model.base.db_config import DBExecuteModel
from sqlalchemy import Column, INTEGER, ForeignKey
from sqlalchemy.orm import relationship
from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
    step_content_id_column
)
from enums.CaseEnum import CaseStepContentType


class DBStepContent(InterfaceCaseContents):
    """
    数据库步骤
    
    content_name: 固定为 "数据库操作"
    content_desc: 从关联的 CaseContentDBExecute 获取
    """
    __tablename__ = "interface_case_step_db"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_DB}

    step_content_id = step_content_id_column()
    target_id = Column(INTEGER, ForeignKey('db_execute.id', ondelete='SET NULL'), nullable=True, comment="关联数据库执行配置ID")

    db_execute = relationship(DBExecuteModel, foreign_keys=[target_id], lazy="select", cascade="delete")

    def _get_default_name(self) -> str:
        return "数据库操作"

    @property
    def content_desc(self) -> str:
        if self.db_execute:
            sql_preview = (self.db_execute.sql_text or "")[:50]
            return sql_preview + "..." if len(self.db_execute.sql_text or "") > 50 else sql_preview
        return ""

    def __repr__(self):
        return f"<DBStepContent(id={self.id}, target_id={self.target_id})>"

    @property
    def dynamic(self) -> str:
        return f"数据库执行 {self._get_default_name()}"