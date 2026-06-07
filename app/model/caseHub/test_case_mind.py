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

    # 脑图归属：需求维度 或 计划维度，至少填一个
    # 计划脑图为新流程主入口，需求脑图保留以兼容老入口（仅读）
    requirement_id = Column(
        Integer,
        ForeignKey("requirement.id", ondelete='cascade'),
        nullable=True,
        comment="所属需求（脑图按需求维度时可空）",
    )
    plan_id = Column(
        Integer,
        ForeignKey('case_plan.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
        comment="所属计划（脑图按计划维度时填写）",
    )
    module_id = Column(Integer, ForeignKey('module.id'), nullable=True, comment="所属模块")
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False, comment="所属项目")
