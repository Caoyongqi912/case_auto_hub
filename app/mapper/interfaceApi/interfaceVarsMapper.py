#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
InterfaceVars Mapper

接口用例变量数据访问层
提供用例变量的增删改查等数据库操作
"""
from typing import List, Optional

from sqlalchemy import and_, select, delete

from app.exception import NotFind
from app.mapper import Mapper
from app.mapper.interfaceApi.dynamicMapper import InterfaceCaseDynamicMapper
from app.model import async_session
from app.model.base import User
from app.model.interfaceAPIModel.interfaceCaseVarsModel import InterfaceCaseVars
from utils import log


class InterfaceVarsMapper(Mapper[InterfaceCaseVars]):
    """
    接口用例变量 Mapper

    继承自基础 Mapper，提供对 InterfaceCaseVars 模型的数据访问
    """
    __model__ = InterfaceCaseVars

    @classmethod
    async def insert_vars(
            cls,
            user: User,
            case_id: int,
            key: str,
            value: str
    ) -> InterfaceCaseVars:
        """
        插入变量

        在同一个用例中，key 必须唯一

        :param user: 创建用户
        :param case_id: 用例ID
        :param key: 变量键名
        :param value: 变量值
        :return: 创建的变量对象
        :raises NotFind: 当 key 已存在时抛出
        """
        try:
            async with cls.transaction() as session:
                key_exists = await session.execute(
                    select(InterfaceCaseVars).where(and_(
                        InterfaceCaseVars.key == key,
                        InterfaceCaseVars.case_id == case_id
                    ))
                )
                if key_exists.scalar():
                    raise NotFind(f"变量 key '{key}' 已存在")

                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    description=f"添加前置变量 {key} {value}",
                    user=user,
                    session=session
                )
                model = InterfaceCaseVars(
                    case_id=case_id,
                    key=key,
                    value=value,
                    creator=user.id,
                    creatorName=user.username
                )
                return await cls.add_flush_expunge(model=model, session=session)

        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def query_by(
            cls,
            case_id: Optional[int] = None,
            key: Optional[str] = None,
            uid: Optional[str] = None
    ) -> List[InterfaceCaseVars]:
        """
        根据条件查询变量

        :param case_id: 用例ID（可选）
        :param key: 变量键名（可选）
        :param uid: 变量唯一标识（可选）
        :return: 符合条件的变量列表
        """
        conditions = []

        if case_id is not None:
            conditions.append(InterfaceCaseVars.case_id == case_id)
        if key is not None:
            conditions.append(InterfaceCaseVars.key == key)
        if uid is not None:
            conditions.append(InterfaceCaseVars.uid == uid)

        if conditions:
            query = select(InterfaceCaseVars).where(and_(*conditions))
        else:
            query = select(InterfaceCaseVars)

        async with async_session() as session:
            result = await session.execute(query)
            return list(result.scalars().all())

    @classmethod
    async def delete_var(cls, uid: str, user: User) -> bool:
        """
        根据 uid 删除变量

        :param uid: 变量唯一标识
        :param user: 删除人
        :return: 是否删除成功
        """
        try:
            async with cls.transaction() as session:
                case_var = await cls.get_by_uid(uid=uid, session=session)
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_var.case_id,
                    description=f"添加前置变量 {case_var}",
                    user=user,
                    session=session
                )
                result = await session.execute(
                    delete(InterfaceCaseVars).where(InterfaceCaseVars.uid == uid)
                )

                return result.rowcount > 0
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def get_by_case_id(cls, case_id: int) -> List[InterfaceCaseVars]:
        """
        根据用例ID获取所有变量

        :param case_id: 用例ID
        :return: 该用例下的所有变量列表
        """
        async with async_session() as session:
            result = await session.execute(
                select(InterfaceCaseVars).where(
                    InterfaceCaseVars.case_id == case_id
                )
            )
            return list(result.scalars().all())


__all__ = ["InterfaceVarsMapper"]
