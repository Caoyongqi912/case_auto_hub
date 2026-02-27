#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/30
# @Author : cyq
# @File : playStepContent
# @Software: PyCharm
# @Desc:
from datetime import datetime

from app.model import BaseModel
from sqlalchemy import Column, String, INTEGER, ForeignKey, TEXT, FLOAT, JSON, BOOLEAN, DATETIME

from enums.CaseEnum import PlayStepContentType


class PlayStepContent(BaseModel):
    """
    PlayStepContent
    """

    __tablename__ = "play_step_content"
    content_name = Column(String(250), nullable=True, comment="步骤名称")
    content_desc = Column(String(250), nullable=True, comment="步骤描述")
    content_type = Column(INTEGER, default=PlayStepContentType.STEP_PLAY, nullable=False, comment="步骤类型")

    enable = Column(BOOLEAN, default=1, nullable=False, comment="是否启用")
    is_common = Column(BOOLEAN, default=0, nullable=False, comment="是否公共")
    script_text = Column(TEXT, nullable=True, comment="脚本文本")
    assert_list = Column(JSON, nullable=True, comment="断言")

    target_id = Column(INTEGER, nullable=True, comment="外键 ID ")

    def __repr__(self):
        if self.content_type == PlayStepContentType.STEP_PLAY:
            return f"<UI STEP (id={self.id},Name=\"{self.content_name}\", Desc=\"{self.content_desc}\"/>"
        elif self.content_type == PlayStepContentType.STEP_PLAY_GROUP:
            return f"<UI GROUP STEP (id={self.id},Name=\"{self.content_name}\", Desc=\"{self.content_desc}\"/>"
        elif self.content_type == PlayStepContentType.STEP_PLAY_SCRIPT:
            return f"<UI SCRIPT STEP (id={self.id},Name=\"{self.content_name}\", Desc=\"{self.content_desc}\" />"
        return ""


class PlayStepGroup(BaseModel):
    __tablename__ = "play_group"
    name = Column(String(40), nullable=False, comment="组名称")
    description = Column(String(40), nullable=False, comment="组描述")
    step_num = Column(INTEGER, nullable=False, default=0, comment="步骤数量")
    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    project_id = Column(INTEGER, ForeignKey("project.id", ondelete='set null'), nullable=True,
                        comment="所属产品")

    def __repr__(self):
        return f"<PlayStepGroup(id={self.id}, name={self.name}, description={self.description}, step_num={self.step_num} />"
