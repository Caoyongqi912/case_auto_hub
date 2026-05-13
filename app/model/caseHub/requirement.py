#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : requirement
# @Software: PyCharm
from sqlalchemy import Column, ForeignKey, String, Integer, JSON

from app.model.basic import BaseModel


class Requirement(BaseModel):
    __tablename__ = "requirement"
    module_id = Column(Integer, nullable=True, comment="所属模块")
    project_id = Column(Integer, ForeignKey("project.id"), nullable=True,
                        comment="所属项目")

    requirement_url = Column(String(500), nullable=True, comment="需求链接")
    requirement_name = Column(String(500), nullable=True, comment="需求名")
    requirement_level = Column(String(5), nullable=True, comment="需求等级 P1 P2 P0")
    process = Column(Integer, default=5,
                     comment="用例进度  1'二轮测试' | 2'一轮测试中' |3'待测试' | 4'完成' | 5'编写中';")

    develops = Column(JSON, nullable=True, comment="开发人员")
    maintainer = Column(Integer, nullable=True, comment="测试人员")
    case_type = Column(Integer, default=1, comment="1 case 2 mind")

    case_number = Column(Integer, default=0, comment="关联用例数量")

    def __repr__(self):
        return f"<CaseHUB(id={self.id},requirement_name={self.requirement_name}) >"