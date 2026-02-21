#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/2/4
# @Author : cyq
# @File : PlayResult
# @Software: PyCharm
# @Desc:
from sqlalchemy import ForeignKey, Column, INTEGER, String, JSON, DATETIME, BOOLEAN, Text
from datetime import datetime

from app.model import BaseModel


class PlayStepContentResult(BaseModel):
    """
    PlayStepContentResult
    """
    __tablename__ = "play_step_content_result"

    play_case_result_id = Column(INTEGER, ForeignKey("play_case_result.id",
                                                     ondelete='CASCADE'), nullable=True, comment="所属case result")

    play_task_result_id = Column(INTEGER, ForeignKey("play_task_result.id",
                                                     ondelete='CASCADE'), nullable=True, comment="所属task result")
    content_id = Column(INTEGER, ForeignKey('play_step_content.id', ondelete='SET NULL'), comment="步骤ID")
    content_name = Column(String(250), nullable=True, comment="步骤名称")
    content_desc = Column(String(250), nullable=True, comment="步骤描述")
    content_step = Column(INTEGER, nullable=False, comment="步骤")
    # CaseStepContentType
    content_type = Column(INTEGER, nullable=False, comment="步骤类型")
    # STEP GROUP ..
    content_target_result_id = Column(INTEGER, nullable=True, comment="目标ID")
    

        # 层级关系字段
    parent_result_id = Column(INTEGER, ForeignKey('play_step_content_result.id', ondelete='SET NULL'),
     nullable=True, comment="父步骤结果ID，用于步骤组场景")

    extracts = Column(JSON, nullable=True, comment="变量")
    # 断言
    content_asserts = Column(JSON, nullable=True, comment="断言信息")

    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    use_time = Column(String(50), nullable=True, comment="用时")

    starter_id = Column(INTEGER, comment="运行人ID")
    starter_name = Column(String(20), comment="运行人姓名")
    content_result = Column(BOOLEAN, default=False, comment="运行结果")
    content_message = Column(Text, nullable=True, comment="运行信息")
    content_ignore_error = Column(BOOLEAN, default=False, comment="是否忽略异常")
    content_screenshot_path = Column(String(500), nullable=True, comment="截图路径")

    def __repr__(self):
        return f"<CaseContentResult id={self.id} type={self.content_type} content_target_result_id={self.content_target_result_id} result={self.content_result}/>"
