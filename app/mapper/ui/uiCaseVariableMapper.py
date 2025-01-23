#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/7/4# @Author : cyq# @File : uiCaseExtractMapper# @Software: PyCharm# @Desc:from typing import Typefrom sqlalchemy import select, func, and_from app.exception import NotFindfrom app.mapper.ui.uiCaseMapper import UICaseMapperfrom app.model import async_sessionfrom app.model.base import Userfrom app.model.ui import UICaseModel, UIVariablesModelfrom app.mapper import Mapper, Tclass UICaseVariableMapper(Mapper):    __model__ = UIVariablesModel    @classmethod    async def insert(cls: Type[T], user: User,  **kwargs) -> T:        """        插入数据        同一个case 校验 key 唯一        :param user        :param case_id        :param kwargs:        :return:        """        caseId = kwargs.get("case_id")        try:            async with async_session() as session:                async with session.begin():                    await UICaseMapper.get_by_id(ident=caseId, session=session)                    key_exists = await session.execute(                        select(UIVariablesModel).where(and_(                            UIVariablesModel.key == kwargs.get("key"),                            UIVariablesModel.case_id == caseId                        ))                    )                    if key_exists.scalar():                        raise NotFind("key 已存在")                    return await cls.save_no_session(session=session, **kwargs)        except Exception as e:            raise e