#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceConditionMapper
# @Software: PyCharm
# @Desc: 条件 Mapper - 处理条件及其关联接口的管理

from typing import List, Optional, Sequence

from sqlalchemy import select, delete, insert, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
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
    async def query_interfaces_by_condition_id(cls, condition_id: int, session: Optional[AsyncSession] = None) -> \
            Sequence[Interface]:
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
    async def associate_self_interface(cls, case_id: int, condition_id: int, user: User) -> Interface:
        """
        添加私有接口
        """
        from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper

        try:
            async with cls.transaction() as session:
                case = await InterfaceCaseMapper.get_by_id(case_id, session=session)
                empty_interface = await InterfaceMapper.association_empty_interface(
                    module_id=case.module_id,
                    project_id=case.project_id,
                    user=user,
                    session=session
                )
                await AssociationHelper.create_condition_interface_association(
                    session=session,
                    condition_id=condition_id,
                    interface_id=empty_interface.id
                )
                return empty_interface


        except Exception as e:
            log.error(f"associate_self_interface error: {e}")
            raise

    @classmethod
    async def associate_interfaces(
            cls,
            condition_id: int,
            interface_id_list: List[int],
            copy: bool,
            user: User
    ) -> None:
        """
        关联接口到条件

        Args:
            condition_id: 条件 ID
            interface_id_list: 接口 ID 列表
            copy: 接口 ID 列表
            user: 用户
        """
        if not interface_id_list:
            return
        try:
            async with cls.transaction() as session:
                if copy:
                    interface_ids_to_add = []
                    for interface_id in interface_id_list:
                        new_interface = await InterfaceMapper.copy_one(
                            target=interface_id,
                            session=session,
                            user=user,
                            is_common=False
                        )
                        interface_ids_to_add.append(new_interface.id)

                else:
                    interface_ids_to_add = interface_id_list
                await AssociationHelper.create_condition_interfaces_association(session=session,
                                                                                condition_id=condition_id,
                                                                                interface_id_list=interface_ids_to_add)
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
                interface = await InterfaceMapper.get_by_id(ident=interface_id, session=session)
                if not interface.is_common:
                    await session.delete(interface)

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
    async def reorder_condition_apis(
            cls,
            condition_id: int,
            interface_id_list: List[int]
    ):
        """
        重新排序条件关联的接口（先删后插策略）

        Args:
            condition_id: 条件ID
            interface_id_list: 按新顺序排列的接口ID列表
        """
        if not interface_id_list:
            return

        try:
            async with cls.transaction() as session:
                await session.execute(
                    delete(InterfaceConditionAPIAssociation).where(
                        InterfaceConditionAPIAssociation.condition_id == condition_id
                    )
                )

                values = [
                    {
                        "condition_id": condition_id,
                        "interface_api_id": interface_id,
                        "step_order": index
                    }
                    for index, interface_id in enumerate(interface_id_list, start=1)
                ]
                await session.execute(
                    insert(InterfaceConditionAPIAssociation).values(values)
                )
        except Exception as e:
            log.error(f"reorder_condition_apis error: {e}")
            raise

    @classmethod
    async def copy_condition(cls, condition_id: int, user: User, session: AsyncSession) -> Optional[InterfaceCondition]:
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
        condition = await cls.get_by_id(ident=condition_id, session=session)
        if not condition:
            return None
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
                "condition_id": new_condition.id,
                "interface_api_id": new_interface_id,
                "step_order": assoc.step_order
            })

        if new_assoc:
            await session.execute(insert(InterfaceConditionAPIAssociation), new_assoc)

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
    async def create_condition_interface_association(
            session: AsyncSession,
            interface_id: int,
            condition_id: int
    ):
        last_index = await LastIndexHelper.get_condition_apis_last_index(condition_id, session)
        await session.execute(
            insert(InterfaceConditionAPIAssociation).values(
                {
                    "condition_id": condition_id,
                    "interface_api_id": interface_id,
                    "step_order": last_index + 1
                }
            )
        )

    @staticmethod
    async def create_condition_interfaces_association(
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
