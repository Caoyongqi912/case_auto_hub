#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/2
# @Author : cyq
# @File : playStep
# @Software: PyCharm
# @Desc:
from sqlalchemy import Column, String, BOOLEAN, ForeignKey, INTEGER, JSON
from sqlalchemy.orm import relationship
from app.model import BaseModel


class PlayStepModel(BaseModel):
    __tablename__ = "play_steps"

    name = Column(String(40), nullable=False, comment="步骤名称")
    description = Column(String(250), nullable=True, comment="步骤描述")
    # .xx
    selector = Column(String(250), nullable=True, comment="步骤元素定位器")
    locator = Column(String(40), nullable=True, comment="Locator获取方式")
    iframe_name = Column(String(250), nullable=True, comment="iframe")
    method = Column(String(40), nullable=True, comment="对locator操作方法")
    key = Column(String(40), nullable=True, comment="key")
    value = Column(String(250), nullable=True, comment="可能要传入的值")
    new_page = Column(BOOLEAN, default=False, comment="是否打开新页面")
    is_ignore = Column(BOOLEAN, default=False, comment="忽略异常")
    is_common = Column(BOOLEAN, default=False, comment="是否是公共步骤")


    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    project_id = Column(INTEGER, ForeignKey("project.id", ondelete="set null"), nullable=True, comment="所属项目")

    def __repr__(self):
        return f"<PlayStepModel (name='{self.name}'  description='{self.description}' method={self.method})>"

    @property
    def desc(self):
        if len(self.description) > 10:
            return self.description[:10] + "..."
        return self.description
