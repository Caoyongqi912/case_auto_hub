#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/20# @Author : cyq# @File : project# @Software: PyCharm# @Desc:from sqlalchemy import Column, String, INTEGER, ForeignKey, Table, BOOLEANfrom app.model.basic import BaseModelfrom sqlalchemy.orm import relationshipprojectUser = Table(    "project_user", BaseModel.metadata,    Column("project_id", INTEGER, ForeignKey("project.id", ondelete='CASCADE'), primary_key=True),    Column("user_id", INTEGER, ForeignKey("user.id", ondelete='CASCADE'), primary_key=True))class Project(BaseModel):    __tablename__ = "project"    title = Column(String(20), unique=True, comment="项目名称")    description = Column("description", String(100), nullable=True, comment="项目描述")    chargeId = Column(INTEGER, comment="项目负责人ID")    chargeName = Column(String(20), nullable=True, comment="项目负责人姓名")    # 用户跟项目是 多对多 绑定    users = relationship("User", backref="project", lazy="dynamic",                         secondary=projectUser)