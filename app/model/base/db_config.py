#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/17# @Author : cyq# @File : db_config# @Software: PyCharm# @Desc:from sqlalchemy import Column, String, Integerfrom app.model import BaseModelclass DBConfig(BaseModel):    __tablename__ = "db_config"    db_name = Column(String(50), nullable=False, comment="数据库自定义名称")    db_type = Column(Integer, nullable=False, comment="数据库类型")    db_host = Column(String(50), nullable=False, comment="数据库地址")    db_port = Column(Integer, nullable=False, comment="数据库端口")    db_username = Column(String(50), nullable=False, comment="数据库用户名")    db_password = Column(String(50), nullable=False, comment="数据库密码")    db_database = Column(String(50), nullable=False, comment="数据库名称")    @property    def config(self):        if self.db_type == 1:            return {                "host": self.db_host,                "port": self.db_port,                "user": self.db_username,                "password": self.db_password,                "db": self.db_database,                "autocommit": True            }        elif self.db_type == 2:            return {                "host": self.db_host,                "port": self.db_port,                "service_name": self.db_database,                "username": self.db_username,                "password": self.db_password,            }        else:            _ = dict(                host=self.db_host,                port=self.db_port,                db=self.db_database,                decode_responses=True,                max_connections=100            )            if self.db_password and self.db_username:                _.update(password=self.db_password, username=self.db_username)            return _