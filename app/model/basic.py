#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : basic# @Software: PyCharm# @Desc:from datetime import datetimefrom typing import Set, Optionalfrom sqlalchemy import Column, INTEGER, String, DATETIMEfrom sqlalchemy.ext.declarative import declarative_basefrom sqlalchemy.orm import Mappedfrom utils import GenerateTools, MyLoguruLOG = MyLoguru().get_logger()base = declarative_base()class BaseModel(base):    __abstract__ = True    id: Mapped[int] = Column(INTEGER, primary_key=True, autoincrement=True)    uid: Mapped[str] = Column(String(50), index=True, unique=True, default=GenerateTools.uid, comment="唯一标识")    create_time: Mapped[datetime] = Column(DATETIME, default=datetime.now, comment="创建时间")    update_time: Mapped[datetime] = Column(DATETIME, nullable=True, onupdate=datetime.now, comment="修改时间")    creator = Column(INTEGER, comment="创建人")    creatorName = Column(String(20), comment="创建人姓名")    updater = Column(INTEGER, nullable=True, comment="修改人")    updaterName = Column(String(20), comment="修改人姓名")    @property    def map(self) -> dict:        """        数据类型转换成字典        :return:        """        _ = dict()        for c in self.__table__.columns:            v = getattr(self, c.name)            if isinstance(v, datetime):                _[c.name] = v.strftime("%Y-%m-%d %H:%M:%S")            else:                _[c.name] = v        return _    def to_dict(self, exclude: Optional[Set[str]] = None):        _ = dict()        for c in self.__table__.columns:            if exclude and c.name in exclude:                continue            v = getattr(self, c.name)            if isinstance(v, datetime):                _[c.name] = v.strftime("%Y-%m-%d %H:%M:%S")            else:                _[c.name] = v        return _    @property    def copy_map(self):        excludes = ['id', 'uid', "create_time", "update_time", 'creator', 'creatorName', 'updater', "updaterName"]        _ = {}        for c in self.__table__.columns:            if c.name in excludes:                continue            try:                value = getattr(self, c.name)            except AttributeError:                continue            if isinstance(value, datetime):                _[c.name] = value.strftime("%Y-%m-%d %H:%M:%S")            else:                _[c.name] = value        return _