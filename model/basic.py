#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : _basic# @Software: PyCharm# @Desc:from sqlalchemy import Column, INTEGER, String, DATETIMEfrom sqlalchemy.orm import Mapped, declarative_basefrom datetime import datetimefrom model import async_enginefrom utils import GenerateTools, MyLoguruLOG = MyLoguru().get_logger()class BaseModel(declarative_base()):    __abstract__ = True    id: Mapped[int] = Column(INTEGER, primary_key=True, autoincrement=True)    uid: Mapped[str] = Column(String(50), index=True, unique=True, default=GenerateTools.uid, comment="唯一标识")    create_time: Mapped[datetime] = Column(DATETIME, default=datetime.now, comment="创建时间")    update_time: Mapped[datetime] = Column(DATETIME, nullable=True, onupdate=datetime.now, comment="修改时间")    creator = Column(INTEGER, comment="创建人")    creatorName = Column(String(20), comment="创建人姓名")    updater = Column(INTEGER, nullable=True, comment="修改人")    updaterName = Column(String(20), comment="修改人姓名")    @property    def map(self) -> dict:        """        数据类型转换成字典        :return:        """        _ = dict()        for c in self.__table__.columns:            v = getattr(self, c.name)            if isinstance(v, datetime):                _[c.name] = v.strftime("%Y-%m-%d %H:%M:%S")            else:                _[c.name] = v        return _async def create_table():    async with async_engine.begin() as conn:        for i in BaseModel.metadata.tables:            LOG.debug(i)  # 打印出所有表的元数据        await conn.run_sync(BaseModel.metadata.create_all,                            checkfirst=True)