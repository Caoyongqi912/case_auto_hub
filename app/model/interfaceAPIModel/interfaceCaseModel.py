#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/2
# @Author : cyq
# @File : interfaceCaseModel
# @Software: PyCharm
# @Desc:接口用例
from datetime import datetime

from app.model.basic import BaseModel
from sqlalchemy import Column, String, INTEGER, ForeignKey, Float, DATETIME


class InterfaceCase(BaseModel):
    """
    接口用例
    """
    __tablename__ = "interface_case"
    
    case_title = Column(String(40), nullable=True, comment="标题")
    case_desc = Column(String(200), nullable=True, comment="描述")
    case_level = Column(String(10), comment="接口用例等级")
    case_status = Column(String(10), comment="接口用例状态")
    case_api_num = Column(INTEGER, default=0, comment="接口数量")
    module_id = Column(INTEGER, nullable=True, comment="所属模块")
    project_id = Column(INTEGER, ForeignKey("project.id", ondelete='set null'), nullable=True,
                        comment="所属产品")
    error_stop = Column(INTEGER, default=0, comment="错误停止 1是 0否")

    
    def __repr__(self):
        return f"InterfaceCase id=\"{self.id}\" uid=\"{self.uid}\" name=\"{self.case_title}\" desc=\"{self.case_desc}\" ..."