#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : _basic# @Software: PyCharm# @Desc:from enum import IntEnumfrom typing import Any, TypeVarT = TypeVar('T', bound='BaseEnum')class BaseEnum(IntEnum):    @classmethod    def enum(cls: T, value: Any) -> T:        """        获取枚举的value        :param value:        :return:        """        for k, v in cls.__members__.items():            if v.value == value:                return v    @classmethod    def getValue(cls, name: str) -> int:        for k, v in cls.__members__.items():            if v.name == name:                return v.value    @classmethod    def values(cls):        return [v.value for v in cls]    @classmethod    def names(cls):        return [v.name for v in cls]    @classmethod    def getName(cls, value: Any) -> str:        for k, v in cls.__members__.items():            if v.value == value:                return v.name