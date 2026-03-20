#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/3/20
# @Author : cyq
# @File : playCondition
# @Software: PyCharm
# @Desc:
from sqlalchemy import Column, String, INTEGER
from app.model import BaseModel


class PlayCondition(BaseModel):
    """
    UI条件判断模型
    """
    __tablename__ = "play_condition"

    condition_key = Column(String(40), nullable=True, comment="条件key(变量名)")
    condition_value = Column(String(40), nullable=True, comment="条件value")
    condition_operator = Column(INTEGER, nullable=True, comment="比较操作符")
    condition_step_num = Column(INTEGER, default=0, comment="子步骤数量")

    def __repr__(self):
        return f"<PlayCondition(id={self.id}, key={self.condition_key}, value={self.condition_value}, operator={self.condition_operator})>"
