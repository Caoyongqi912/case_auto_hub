#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/6
# @Author : cyq
# @File : basic
# @Software: PyCharm
# @Desc:
from datetime import datetime
from typing import Set, Optional

from sqlalchemy import Column, INTEGER, String, DATETIME
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped
from utils import GenerateTools, MyLoguru

LOG = MyLoguru().get_logger()
base = declarative_base()


class BaseModel(base):
    __abstract__ = True
    id = Column(INTEGER, primary_key=True, autoincrement=True)
    uid = Column(String(50), index=True, unique=True, default=GenerateTools.uid, comment="唯一标识")
    create_time = Column(DATETIME, default=datetime.now, comment="创建时间")
    update_time = Column(DATETIME, nullable=True, onupdate=datetime.now, comment="修改时间")
    creator = Column(INTEGER, comment="创建人")
    creatorName = Column(String(20), comment="创建人姓名")
    updater = Column(INTEGER, nullable=True, comment="修改人")
    updaterName = Column(String(20), comment="修改人姓名")

    @property
    def map(self) -> dict:
        """
        数据类型转换成字典

        使用 SQLAlchemy inspect 拿到当前 mapper 的所有 columns,
        兼容 Joined Table Inheritance 子类(子类实例的 __table__ 只
        含子表列,会漏掉基表继承字段)。
        """
        return self._to_dict_impl(exclude=None)

    def to_dict(self, exclude: Optional[Set[str]] = None):
        return self._to_dict_impl(exclude=exclude)

    def copy_map(self) -> dict:
        excludes = ['id', 'uid', "create_time", "update_time", 'creator', 'creatorName', 'updater', "updaterName"]
        return self._to_dict_impl(exclude=excludes)

    def _to_dict_impl(self, exclude: Optional[Set[str]] = None) -> dict:
        """
        统一的 to_dict 实现,被 map/to_dict/copy_map 共用。
        用 inspect(self.__class__).mapper.columns 拿所有列(含 JTI 继承的),
        避免子表 __table__ 漏字段。
        """
        _ = {}
        mapper = sa_inspect(self.__class__).mapper
        for col in mapper.columns:
            if exclude and col.key in exclude:
                continue
            value = getattr(self, col.key, None)
            if isinstance(value, datetime):
                _[col.key] = value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                _[col.key] = value
        return _
