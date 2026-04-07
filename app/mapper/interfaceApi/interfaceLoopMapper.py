#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceLoopMapper
# @Software: PyCharm
# @Desc: 循环 Mapper - 处理循环及其关联接口的管理

from typing import List, Optional

from sqlalchemy import select, insert, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.interfaceAPIModel.interfaceLoopModel import InterfaceLoopModal
from app.model.interfaceAPIModel.associationModel import InterfaceLoopAPIAssociation
from app.model.interfaceAPIModel.interfaceModel import Interface
from utils import log


class InterfaceLoopMapper(Mapper[InterfaceLoopModal]):
    """
    循环 Mapper

    提供循环的增删改查、关联管理等功能
    """

    __model__ = InterfaceLoopModal

    @classmethod
    async def add_empty_loop(cls, session: AsyncSession, user: User) -> InterfaceLoopModal:
        """
        创建空白循环

        Args:
            session: 数据库会话
            user: 创建用户

        Returns:
            InterfaceLoopModal: 创建的循环实例
        """
        loop = cls.__model__(
            creator=user.id,
            creatorName=user.username,
        )
        return await cls.add_flush_expunge(session=session, model=loop)

    @classmethod
    async def associate_apis(
        cls,
        loop_id: int,
        interface_id_list: List[int],
        session: AsyncSession
    ) -> None:
        """
        关联接口到循环

        Args:
            loop_id: 循环 ID
            interface_id_list: 接口 ID 列表
            session: 数据库会话
        """
        try:
            last_index = await cls.get_last_step_order(loop_id, session)
            values = [
                {
                    "loop_id": loop_id,
                    "interface_api_id": interface_id,
                    "step_order": last_index + index + 1
                }
                for index, interface_id in enumerate(interface_id_list)
            ]
            if values:
                await session.execute(
                    insert(InterfaceLoopAPIAssociation).values(values)
                )
        except Exception as e:
            log.error(f"associate_apis error: {e}")
            raise

    @classmethod
    async def query_interfaces_by_loop_id(cls, loop_id: int) -> List[Interface]:
        """
        查询循环关联的接口列表

        Args:
            loop_id: 循环 ID

        Returns:
            List[Interface]: 接口列表，按执行顺序排序
        """
        try:
            async with async_session() as session:
                stmt = (
                    select(Interface)
                    .join(InterfaceLoopAPIAssociation)
                    .where(
                        InterfaceLoopAPIAssociation.loop_id == loop_id,
                        Interface.id == InterfaceLoopAPIAssociation.interface_api_id
                    )
                    .order_by(InterfaceLoopAPIAssociation.step_order)
                )
                result = await session.scalars(stmt)
                return result.all()
        except Exception as e:
            log.error(f"query_interfaces_by_loop_id error: {e}")
            raise

    @classmethod
    async def disassociate_api(
        cls,
        loop_id: int,
        interface_id: int,
        session: AsyncSession
    ) -> None:
        """
        解除循环与接口的关联

        Args:
            loop_id: 循环 ID
            interface_id: 接口 ID
            session: 数据库会话
        """
        try:
            await session.execute(
                delete(InterfaceLoopAPIAssociation).where(
                    and_(
                        InterfaceLoopAPIAssociation.loop_id == loop_id,
                        InterfaceLoopAPIAssociation.interface_api_id == interface_id
                    )
                )
            )
        except Exception as e:
            log.error(f"disassociate_api error: {e}")
            raise

    @classmethod
    async def reorder_loop_apis(
        cls,
        loop_id: int,
        interface_id_list: List[int],
        session: AsyncSession
    ) -> None:
        """
        重新排序循环关联的接口

        实现策略：先删除所有关联，再按新顺序插入

        Args:
            loop_id: 循环 ID
            interface_id_list: 新的接口 ID 列表顺序
            session: 数据库会话
        """
        try:
            # 1. 删除旧关联
            await session.execute(
                delete(InterfaceLoopAPIAssociation).where(
                    InterfaceLoopAPIAssociation.loop_id == loop_id
                )
            )

            # 2. 插入新关联
            if interface_id_list:
                values = [
                    {
                        "loop_id": loop_id,
                        "interface_api_id": interface_id,
                        "step_order": index
                    }
                    for index, interface_id in enumerate(interface_id_list, start=1)
                ]
                await session.execute(
                    insert(InterfaceLoopAPIAssociation).values(values)
                )
        except Exception as e:
            log.error(f"reorder_loop_apis error: {e}")
            raise

    @classmethod
    async def delete_loop(cls, loop_id: int, session: AsyncSession) -> bool:
        """
        删除循环

        关联的 InterfaceLoopAPIAssociation 会通过数据库外键的 CASCADE 自动删除

        Args:
            loop_id: 循环 ID
            session: 数据库会话
        """
        try:

            await session.execute(
            delete(Interface).where(
                Interface.id.in_(
                    select(InterfaceLoopAPIAssociation.interface_api_id)
                    .where(InterfaceLoopAPIAssociation.loop_id == loop_id)
                ),
                Interface.is_common == 0  # 非公共
            )
        )



            loop = await InterfaceLoopMapper.get_by_id(
                ident=loop_id, session=session
            )
            if not loop:
                return False
            await session.delete(loop)
            return True
        except Exception as e:
            log.error(f"delete_loop error: {e}")
            raise

    @classmethod
    async def copy_loop(cls, loop_id: int, user: User, session: AsyncSession) -> Optional[InterfaceLoopModal]:
        """
        复制循环及其关联接口的子步骤
        非公共接口的子步骤会复制并关联，公共接口的子步骤保持原样关联
        step_order 与原顺序保持一致
        :param loop_id: 循环ID
        :param user: 用户对象
        :param session: 会话对象
        :return: 复制后的循环对象
        """
        from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper

        loop = await cls.get_by_id(ident=loop_id, session=session)
        if not loop:
            return None

        new_loop = await cls.copy_one(
            target=loop,
            user=user,
            session=session,
        )

        assoc_result = await session.execute(
            select(InterfaceLoopAPIAssociation)
            .where(InterfaceLoopAPIAssociation.loop_id == loop_id)
            .order_by(InterfaceLoopAPIAssociation.step_order)
        )
        original_assoc = assoc_result.scalars().all()

        new_assoc = []
        for assoc in original_assoc:
            original_interface = await InterfaceMapper.get_by_id(ident=assoc.interface_api_id, session=session)
            if original_interface.is_common:
                new_interface_id = original_interface.id
            else:
                new_interface = await InterfaceMapper.copy_one(
                    target=original_interface,
                    user=user,
                    session=session,
                    is_common=False,
                )
                new_interface_id = new_interface.id

            new_assoc.append({
                "loop_id": new_loop.id,
                "interface_api_id": new_interface_id,
                "step_order": assoc.step_order
            })

        if new_assoc:
            await session.execute(insert(InterfaceLoopAPIAssociation), new_assoc)

        return new_loop

    @classmethod
    async def get_last_step_order(cls, loop_id: int, session: AsyncSession) -> int:
        """
        获取当前循环的最大排序值

        Args:
            loop_id: 循环 ID
            session: 数据库会话

        Returns:
            int: 当前最大排序值，无关联则返回 0
        """
        stmt = (
            select(InterfaceLoopAPIAssociation.step_order)
            .where(InterfaceLoopAPIAssociation.loop_id == loop_id)
            .order_by(InterfaceLoopAPIAssociation.step_order.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar() or 0


__all__ = ["InterfaceLoopMapper"]
