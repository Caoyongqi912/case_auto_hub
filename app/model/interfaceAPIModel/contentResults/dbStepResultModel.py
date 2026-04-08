#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : dbStepResultModel
# @Software: PyCharm
# @Desc: 数据库步骤执行结果模型

from sqlalchemy import Column, INTEGER, ForeignKey, JSON, TEXT, String
from sqlalchemy.orm import relationship
from app.model.interfaceAPIModel.contentResults.baseStepResultModel import (
    BaseStepResult,
    step_result_id_column
)
from enums.CaseEnum import CaseStepContentType


class DBStepResult(BaseStepResult):
    """
    数据库步骤执行结果
    
    content_name: 固定为 "数据库操作"
    content_desc: SQL预览
    """
    __tablename__ = "interface_case_content_result_db"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_DB}

    step_result_id = step_result_id_column()

    # 关联的DB配置ID
    db_config_id = Column(
        INTEGER,
        ForeignKey('case_content_db_execute.id', ondelete='SET NULL'),
        nullable=True,
        comment="关联数据库执行配置ID"
    )

    # SQL信息
    sql_text = Column(TEXT, nullable=True, comment="SQL语句")
    db_type = Column(INTEGER, nullable=True, comment="数据库类型 1MySQL 2Oracle 3Redis")

    # 执行结果
    execute_result = Column(JSON, nullable=True, comment="执行结果")
    affect_rows = Column(INTEGER, nullable=True, comment="影响行数")

    # relationship
    db_config = relationship("CaseContentDBExecute", foreign_keys=[db_config_id], lazy="noload")

    @property
    def content_name(self) -> str:
        return "数据库操作"

    @property
    def content_desc(self) -> str:
        if self.sql_text:
            preview = self.sql_text[:50]
            return preview + "..." if len(self.sql_text) > 50 else preview
        return ""

    def __repr__(self):
        return f"<DBStepResult(id={self.id}, db_type={self.db_type}, affect_rows={self.affect_rows})>"
