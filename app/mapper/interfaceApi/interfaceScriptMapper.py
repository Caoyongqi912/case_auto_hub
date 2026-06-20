#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : interfaceScriptMapper
# @Software: PyCharm
# @Desc:
from typing import List, Dict

from sqlalchemy import insert

from app.mapper import Mapper
from app.model.interfaceAPIModel.interfaceScriptDescModel import InterfaceScriptDesc

class InterfaceScriptMapper(Mapper[InterfaceScriptDesc]):

    __model__ = InterfaceScriptDesc


    @classmethod
    async def init_interface_funcs(cls, methods: List[Dict[str, str]]):

        try:
            async with cls.transaction() as session:
                await session.execute(
                    insert(cls.__model__).values(methods)
                )
        except Exception as e:
            raise
__all__ = ["InterfaceScriptMapper"]