#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/15
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc:
from typing import Optional

from pydantic import Field, BaseModel
from app.exception import ParamsError


class PageSchema(BaseModel):
    """
    分页参数
    """
    current: Optional[int] = Field(1)
    pageSize: Optional[int] = Field(10)
    creator: Optional[int] = Field(default=None)
    sort: Optional[dict] = Field(default=None, description="排序参数，接受 JSON 字典格式")


class BaseSchema:

    @staticmethod
    def not_empty(value):
        if isinstance(value, str) and len(value.strip()) == 0:
            raise ParamsError("不能为空")
        if not isinstance(value, int):
            if not value:
                raise ParamsError("不能为空")
        return value
