#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceResultMapper# @Software: PyCharm# @Desc:from keyword import kwlistfrom app.mapper import Mapperfrom app.model.base import Userfrom app.model.interface import InterfaceResultModel, InterfaceModelfrom app.model import async_sessionfrom enums import InterfaceAPIStatusEnumclass InterfaceResultMapper(Mapper):    __model__ = InterfaceResultModel    @classmethod    async def set_init(cls,                       interface: InterfaceModel,                       starter: User,                       **kwargs):        """        接口执行 初始化 结果        """        try:            async with async_session() as session:                with session.begin():                    c = cls.__model__(                        interfaceID=interface.id,                        interfaceName=interface.name,                        interfaceUid=interface.uid,                        interfaceDesc=interface.desc,                        status=InterfaceAPIStatusEnum.RUNNING,                        starterId=starter.id,                        starterName=starter.username,                        **kwargs                    )                    await cls.add_flush_expunge(session, c)                    return c        except Exception as e:            raise e