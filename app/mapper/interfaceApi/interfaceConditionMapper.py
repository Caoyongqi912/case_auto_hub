#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceConditionMapper
# @Software: PyCharm
# @Desc: 条件 Mapper - 处理条件及其关联接口的管理

from typing import List, Optional

from sqlalchemy import select, delete, insert, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.interfaceAPIModel.interfaceConditionModel import InterfaceCondition
from app.model.interfaceAPIModel.interfaceModel import Interface
from app.model.interfaceAPIModel.associationModel import InterfaceConditionAPIAssociation
from utils import log


class InterfaceConditionMapper(Mapper[InterfaceCondition]):
    """
    条件 Mapper

    提供条件的增删改查、关联管理等功能
    """

    __model__ = InterfaceCondition

    @classmethod
    async def add_empty_condition(cls, session: AsyncSession, user: User) -> InterfaceCondition:
        """
        创建空白条件

        Args:
            session: 数据库会话
            user: 创建用户

        Returns:
            InterfaceCondition: 创建的条件实例
        """
        condition = InterfaceCondition(
            creator=user.id,
            creatorName=user.username,
        )
        return await cls.add_flush_expunge(session, condition)

    @classmethod
    async def query_interfaces_by_condition_id(cls, condition_id: int, session: Optional[AsyncSession] = None) -> List[Interface]:
        """
        查询条件关联的接口列表

        Args:
            condition_id: 条件 ID
            session: 数据库会话（可选，不传则自动创建）

        Returns:
            List[Interface]: 接口列表，按执行顺序排序
        """
        should_close = False
        try:
            if not session:
                session = async_session()
                should_close = True

            stmt = (
                select(Interface)
                .join(InterfaceConditionAPIAssociation)
                .where(
                    InterfaceConditionAPIAssociation.condition_id == condition_id,
                    Interface.id == InterfaceConditionAPIAssociation.interface_api_id
                )
                .order_by(InterfaceConditionAPIAssociation.step_order)
            )
            result = await session.scalars(stmt)
            return result.all()
        except Exception as e:
            log.error(f"query_interfaces_by_condition_id error: {e}")
            raise
        finally:
            if should_close:
                await session.close()

    @classmethod
    async def delete_condition(cls, condition_id: int, session: AsyncSession) -> bool:
        """
        删除条件

        关联的 InterfaceConditionAPIAssociation 会通过数据库外键的 CASCADE 自动删除

        Args:
            condition_id: 条件 ID
            session: 数据库会话
        """
        try:


            await session.execute(
            delete(Interface).where(
                Interface.id.in_(
                    select(InterfaceConditionAPIAssociation.interface_api_id)
                    .where(InterfaceConditionAPIAssociation.condition_id == condition_id)
                ),
                Interface.is_common == 0  # 非公共
            )
        )
            condition = await cls.get_by_id(
                ident=condition_id, session=session
            )
            if not condition:
                return False
            await session.delete(condition)
            return True
        except Exception as e:
            log.error(f"delete_condition error: {e}")
            raise

    @classmethod
    async def associate_interfaces(
        cls,
        condition_id: int,
        interface_id_list: List[int],
    ) -> None:
        """
        关联接口到条件

        Args:
            condition_id: 条件 ID
            interface_id_list: 接口 ID 列表
        """
        try:
            async with cls.transaction() as session:
                await AssociationHelper.create_condition_api_association(session=session, condition_id=condition_id, interface_id_list=interface_id_list)
        except Exception as e:
            log.error(f"associate_interfaces error: {e}")
            raise

    @classmethod
    async def remove_association_interface(cls, condition_id: int, interface_id: int):
        """
        解除关联
        :param condition_id: 条件ID
        :param interface_id: 接口ID
        """
        try:
            async with cls.transaction() as session:
                await session.execute(
                    delete(InterfaceConditionAPIAssociation).where(
                        and_(
                            InterfaceConditionAPIAssociation.condition_id == condition_id,
                            InterfaceConditionAPIAssociation.interface_api_id == interface_id
                        )
                    )
                )
        except Exception as e:
            log.error(f'remove_association_interface error: {e}')
            raise
    @classmethod
    async def reorder_condition_apis(cls, condition_id: int, interface_id_list: List[int]):
        """
        子步骤重新排序
        :param condition_id: 条件ID
        :param interface_id_list: 接口ID列表
        """
        try:
            async with cls.transaction() as session:
                update_values = []
                for index, interface_id in enumerate(interface_id_list, start=1):
                    update_values.append({
                        "condition_id": condition_id,
                        "interface_api_id": interface_id,
                        "step_order": index
                    })

                # 批量更新
                if update_values:
                    await session.execute(
                        update(InterfaceConditionAPIAssociation),
                        update_values
                    )

        except Exception as e:
                log.error(f'reorder_condition_apis error: {e}')
                raise



    @classmethod
    async def copy_condition(cls, condition_id: int, user: User, session: AsyncSession) -> InterfaceCondition:
        """
        复制条件及其关联接口的子步骤
        非公共接口的子步骤会复制并关联，公共接口的子步骤保持原样关联
        step_order 与原顺序保持一致
        :param condition_id: 条件ID
        :param user: 用户对象
        :param session: 会话对象
        :return: 复制后的条件对象
        """
        from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
        condition = await cls.get_by_id(ident=condition_id,session=session)
        if not condition:
            return False
        new_condition = await cls.copy_one(
            target=condition,
            user=user,
            session=session,
        )

        assoc_result = await session.execute(
            select(InterfaceConditionAPIAssociation)
            .where(InterfaceConditionAPIAssociation.condition_id == condition_id)
            .order_by(InterfaceConditionAPIAssociation.step_order)
        )
        original_assocs = assoc_result.scalars().all()

        new_assocs = []
        for assoc in original_assocs:
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

            new_assocs.append({
                "condition_id": new_condition.id,
                "interface_api_id": new_interface_id,
                "step_order": assoc.step_order
            })

        if new_assocs:
            await session.execute(insert(InterfaceConditionAPIAssociation), new_assocs)

        return new_condition

class LastIndexHelper:
    """索引查询辅助类"""

    @staticmethod
    async def get_condition_apis_last_index(condition_id: int, session: AsyncSession) -> int:
        """
        查询条件子步骤最后的索引
        :param condition_id: condition_id
        :param session: 会话对象
        :return: 最后索引值
        """
        stmt = select(InterfaceConditionAPIAssociation.step_order).where(
            InterfaceConditionAPIAssociation.condition_id == condition_id
        ).order_by(
            InterfaceConditionAPIAssociation.step_order.desc()
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar() or 0


class AssociationHelper:
    """关联操作辅助类"""

    @staticmethod
    async def create_condition_api_association(
        session: AsyncSession,
        condition_id: int,
        interface_id_list: List[int]
    ):
        """
        创建条件与API的关联
        :param session: 会话对象
        :param condition_id: 条件ID
        :param interface_id_list: 接口ID列表
        """
        last_index = await LastIndexHelper.get_condition_apis_last_index(condition_id, session)
        values = [
            {
                "condition_id": condition_id,
                "interface_api_id": interface_api_id,
                "step_order": index
            } for index, interface_api_id in enumerate(interface_id_list, start=last_index + 1)
        ]

        if values:
            await session.execute(
                insert(InterfaceConditionAPIAssociation).prefix_with('IGNORE').values(values)
            )