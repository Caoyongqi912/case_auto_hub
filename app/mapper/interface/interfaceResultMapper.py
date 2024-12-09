#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceResultMapper# @Software: PyCharm# @Desc:from app.mapper import Mapperfrom app.model.interface import InterfaceResultModel, InterfaceCaseResultModelfrom app.model import async_sessionfrom utils import MyLogurufrom sqlalchemy import deletelog = MyLoguru().get_logger()class InterfaceResultMapper(Mapper):    __model__ = InterfaceResultModel    @classmethod    async def set_result(cls,                         **kwargs):        """        接口执行 初始化 结果        """        try:            async with async_session() as session:                async with session.begin():                    c = cls.__model__(                        **kwargs                    )                    await cls.add_flush_expunge(session, c)                    return c        except Exception as e:            log.exception(e)            raise eclass InterfaceCaseResultMapper(Mapper):    __model__ = InterfaceCaseResultModel    @classmethod    async def delete_by_caseId(cls, caseId: int):        """删除"""        try:            async with async_session() as session:                delete_stmt = delete(cls.__model__).where(                    InterfaceCaseResultModel.interfaceCaseID == caseId                )                await session.execute(delete_stmt)                await session.commit()        except Exception as e:            raise e    @classmethod    async def init(cls, **kwargs) -> InterfaceCaseResultModel:        """        初始化        :return:        """        try:            async with async_session() as session:                async with session.begin():                    c = cls.__model__(                        **kwargs                    )                    await cls.add_flush_expunge(session, c)                    return c        except Exception as e:            log.error(e)            raise e    @classmethod    async def set_result_field(cls, caseResult: InterfaceCaseResultModel):        try:            async with async_session() as session:                async with session.begin():                    await cls.add_flush_expunge(session, caseResult)        except Exception as e:            log.error(e)            raise e