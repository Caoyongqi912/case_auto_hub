#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/2
# @Author : cyq
# @File : playConfigMapper
# @Software: PyCharm
# @Desc:
from typing import List, Dict

from app.mapper import Mapper
from app.model.playUI import PlayConfig, PlayCaseVariables, PlayMethod
from sqlalchemy import insert

from app.model.playUI.PlayConfig import PlayLocator


class PlayMethodMapper(Mapper[PlayMethod]):
    __model__ = PlayMethod

    @classmethod
    async def init_play_methods(cls, methods: List[Dict[str, str]]):

        try:
            async with cls.transaction() as session:
                await session.execute(
                    insert(cls.__model__).values(methods)
                )
        except Exception as e:
            raise


class PlayLocatorMapper(Mapper[PlayLocator]):
    __model__ = PlayLocator

    @classmethod
    async def init_play_locators(cls, locators: List[Dict[str, str]]):
        try:
            async with cls.transaction() as session:
                await session.execute(
                    insert(cls.__model__).values(locators)
                )
        except Exception as e:
            raise


class PlayCaseVariablesMapper(Mapper[PlayCaseVariables]):
    __model__ = PlayCaseVariables


class PlayConfigMapper(Mapper[PlayConfig]):
    __model__ = PlayConfig
