#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : test_case_mind
# @Software: PyCharm
from sqlalchemy import Column, ForeignKey, JSON, Integer

from app.model.basic import BaseModel


class TestCaseMind(BaseModel):
    __tablename__ = "test_case_mind"

    mind_node = Column(JSON, nullable=False, comment="脑图信息")

    requirement_id = Column(Integer, ForeignKey("requirement.id", ondelete='cascade'), nullable=False)
    module_id = Column(Integer, ForeignKey('module.id'), nullable=False, comment="所属模块")
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False, comment="所属项目")