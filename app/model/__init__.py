#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : __init__.py# @Software: PyCharm# @Desc:from asyncio import current_taskfrom sqlalchemy.ext.asyncio import create_async_enginefrom sqlalchemy.ext.asyncio import AsyncSessionfrom sqlalchemy.ext.asyncio import async_sessionmakerfrom sqlalchemy.ext.asyncio import async_scoped_sessionfrom config import Configfrom .basic import BaseModelasync_engine = create_async_engine(Config.ASYNC_SQLALCHEMY_URI,                                   echo=True,                                   max_overflow=0,                                   pool_size=50,                                   pool_recycle=1500)AsyncSessionMaker = async_sessionmaker(    async_engine,    class_=AsyncSession,    expire_on_commit=False,)async_session = async_scoped_session(    AsyncSessionMaker,    scopefunc=current_task)async def create_table():    async with async_engine.begin() as conn:        await conn.run_sync(BaseModel.metadata.create_all,                            checkfirst=True)