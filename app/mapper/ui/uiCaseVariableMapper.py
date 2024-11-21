#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/7/4# @Author : cyq# @File : uiCaseExtractMapper# @Software: PyCharm# @Desc:from typing import Typefrom sqlalchemy import select, func, and_from app.exception import NotFindfrom app.model import async_sessionfrom app.model.ui import UICaseModel,UIVariablesModelfrom app.mapper import Mapper, Tclass UICaseVariableMapper(Mapper):    __model__ = UIVariablesModel    @classmethod    async def insert(cls: Type[T], **kwargs) -> T:        """        插入数据        :param kwargs:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    # 查询caseId                    case_exists = await session.execute(                        select(UICaseModel).where(UICaseModel.id == kwargs.get("caseId"))                    )                    if not case_exists.scalar():                        raise NotFind("caseId 不存在")                    key_exists = await session.execute(                        select(UIVariablesModel).where(and_(                            UIVariablesModel.key == kwargs.get("key"),                            UIVariablesModel.caseId == kwargs.get("caseId")                        ))                    )                    if key_exists.scalar():                        raise NotFind("key 已存在")                    creator = kwargs.get("creator")                    user = await cls.get_creator(creator, session)                    kwargs["creator"] = user.id                    kwargs["creatorName"] = user.username                    return await super(UICaseVariableMapper, cls).insert(**kwargs)        except Exception as e:            raise e