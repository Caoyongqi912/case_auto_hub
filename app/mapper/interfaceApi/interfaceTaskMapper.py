#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/7
# @Author : cyq
# @File : interfaceTaskMapper
# @Software: PyCharm
# @Desc: 任务 Mapper - 处理任务及其关联接口/用例的管理

from typing import List, Optional

from sqlalchemy import and_, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.mapper import Mapper
from app.mapper.interfaceApi.dynamicMapper import InterfaceTaskDynamicMapper
from app.model import async_session
from app.model.base import User
from app.model.interfaceAPIModel.interfaceTaskModel import InterfaceTask
from app.model.interfaceAPIModel.interfaceModel import Interface
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.model.interfaceAPIModel.associationModel import (
    InterfaceCaseTaskAssociation,
    InterfaceAPITaskAssociation,
)
from utils import log


__all__ = ["InterfaceTaskMapper"]


class InterfaceTaskMapper(Mapper[InterfaceTask]):
    __model__ = InterfaceTask


    @classmethod
    async def insert_task(cls, user: User, **kwargs) -> InterfaceTask:
        try:
            async with cls.transaction() as session:
                task = await cls.save(
                    creator_user=user,
                    session=session,
                    **kwargs
                )
                await InterfaceTaskDynamicMapper.new_dynamic(
                    entity_name=task.interface_task_title,
                    entity_id=task.id,
                    session=session,
                    user=user
                )
                return task
        except Exception as e:
            log.error(f"insert_interface_case error: {e}")
            raise

    @classmethod
    async def update_task(cls, case_id: int, user: User, **kwargs) -> InterfaceTask:
        """
        用例调整
        """
        try:
            async with cls.transaction() as session:
                old_task = await cls.get_by_id(ident=case_id, session=session)
                new_task = await cls.update_by_id(
                    session=session,
                    update_user=user,
                    **kwargs
                )
                await InterfaceTaskDynamicMapper.append_dynamic(
                    entity_id=old_task.id,
                    user=user,
                    old_info=old_task.to_dict(),
                    new_info=new_task.to_dict(),
                    session=session
                )
                return new_task
        except Exception as e:
            log.error(f"update_interface_case error: {e}")
            raise


    @classmethod
    async def query_association_interfaces(
            cls,
            task_id: int,
    ) -> List[Interface]:
        """
        查询任务关联的接口列表

        Args:
            task_id: 任务ID
        """
        try:
            async with async_session() as session:
                stmt = select(Interface).join(
                    InterfaceAPITaskAssociation,
                    InterfaceAPITaskAssociation.interface_api_id == Interface.id
                ).where(InterfaceAPITaskAssociation.interface_task_id == task_id).order_by(InterfaceAPITaskAssociation.step_order)
                result = await session.scalars(stmt)
                return result.all()
        except Exception as e:
            log.error(f"query_association_interfaces error: {e}")
            raise


    @classmethod
    async def query_association_interface_cases(
            cls,
            task_id: int,
    ) -> List[InterfaceCase]:
        """
        查询任务关联的用例列表

        Args:
            task_id: 任务ID
            session: 可选数据库会话
        """

        try:
            async with async_session() as session:
                stmt = select(InterfaceCase).join(
                    InterfaceCaseTaskAssociation,
                    InterfaceCaseTaskAssociation.interface_case_id == InterfaceCase.id
                ).where(InterfaceCaseTaskAssociation.interface_task_id == task_id
                        ).order_by(InterfaceCaseTaskAssociation.step_order)
                result = await session.scalars(stmt)
                return result.all()

        except Exception as e:
            log.error(f"query_association_interface_cases error: {e}")
            raise

    @classmethod
    async def association_interfaces(
            cls,
            task_id: int,
            interface_ids: List[int]
    ) -> bool:
        """
        关联接口到任务

        Args:
            task_id: 任务ID
            interface_ids: 接口ID列表
        """
        if not interface_ids:
            return False

        try:
            async with cls.transaction() as session:
                task = await cls.get_by_id(ident=task_id, session=session)
                if not task:
                    return False

                last_step_order = await cls.get_api_last_index(task_id=task_id, session=session)
                await cls._insert_interfaces_association(
                    session=session,
                    task_id=task_id,
                    interface_ids=interface_ids,
                    start_order=last_step_order
                )
                task.interface_task_total_apis_num += len(interface_ids)
                return True
        except Exception as e:
            log.exception(f"association_interfaces error: {e}")
            raise

    @classmethod
    async def association_interface_cases(
            cls,
            task_id: int,
            case_ids: List[int]
    ) -> bool:
        """
        关联用例到任务

        Args:
            task_id: 任务ID
            case_ids: 用例ID列表
        """
        if not case_ids:
            return False

        try:
            async with cls.transaction() as session:
                task = await cls.get_by_id(ident=task_id, session=session)
                if not task:
                    return False

                last_step_order = await cls.get_case_last_index(task_id=task_id, session=session)
                await cls._insert_cases_association(
                    session=session,
                    task_id=task_id,
                    case_ids=case_ids,
                    start_order=last_step_order
                )
                task.interface_task_total_cases_num += len(case_ids)
                return True
        except Exception as e:
            log.error(f"association_interface_cases error: {e}")
            raise

    @classmethod
    async def remove_association_interface(
            cls,
            task_id: int,
            interface_id: int
    ) -> bool:
        """
        解除接口与任务的关联

        Args:
            task_id: 任务ID
            interface_id: 接口ID
        """
        try:
            async with cls.transaction() as session:
                result = await session.execute(
                    delete(InterfaceAPITaskAssociation).where(
                        and_(
                            InterfaceAPITaskAssociation.interface_task_id == task_id,
                            InterfaceAPITaskAssociation.interface_api_id == interface_id
                        )
                    )
                )
                if result.rowcount == 0:
                    return False

                task = await cls.get_by_id(ident=task_id, session=session)
                if task and task.interface_task_total_apis_num > 0:
                    task.interface_task_total_apis_num -= 1
                return True
        except Exception as e:
            log.error(f"remove_association_interface error: {e}")
            raise

    @classmethod
    async def remove_association_interface_case(
            cls,
            task_id: int,
            case_id: int
    ) -> bool:
        """
        解除用例与任务的关联

        Args:
            task_id: 任务ID
            case_id: 用例ID
        """
        try:
            async with cls.transaction() as session:
                result = await session.execute(
                    delete(InterfaceCaseTaskAssociation).where(
                        and_(
                            InterfaceCaseTaskAssociation.interface_task_id == task_id,
                            InterfaceCaseTaskAssociation.interface_case_id == case_id
                        )
                    )
                )
                if result.rowcount == 0:
                    return False

                task = await cls.get_by_id(ident=task_id, session=session)
                if task and task.interface_task_total_cases_num > 0:
                    task.interface_task_total_cases_num -= 1
                return True
        except Exception as e:
            log.error(f"remove_association_interface_case error: {e}")
            raise

    @classmethod
    async def reorder_interface(
            cls,
            task_id: int,
            interface_ids: List[int]
    ) -> bool:
        """
        重新排序任务关联的接口（先删后插策略）

        Args:
            task_id: 任务ID
            interface_ids: 按新顺序排列的接口ID列表
        """
        if not interface_ids:
            return False

        try:
            async with cls.transaction() as session:
                await session.execute(
                    delete(InterfaceAPITaskAssociation).where(
                        InterfaceAPITaskAssociation.interface_task_id == task_id
                    )
                )

                values = [
                    {
                        "interface_task_id": task_id,
                        "interface_api_id": interface_id,
                        "step_order": index
                    }
                    for index, interface_id in enumerate(interface_ids, start=1)
                ]
                await session.execute(insert(InterfaceAPITaskAssociation).values(values))
                return True
        except Exception as e:
            log.error(f"reorder_interface error: {e}")
            raise

    @classmethod
    async def reorder_interface_case(
            cls,
            task_id: int,
            case_ids: List[int]
    ) -> bool:
        """
        重新排序任务关联的用例（先删后插策略）

        Args:
            task_id: 任务ID
            case_ids: 按新顺序排列的用例ID列表
        """
        if not case_ids:
            return False

        try:
            async with cls.transaction() as session:
                await session.execute(
                    delete(InterfaceCaseTaskAssociation).where(
                        InterfaceCaseTaskAssociation.interface_task_id == task_id
                    )
                )

                values = [
                    {
                        "interface_task_id": task_id,
                        "interface_case_id": case_id,
                        "step_order": index
                    }
                    for index, case_id in enumerate(case_ids, start=1)
                ]
                await session.execute(insert(InterfaceCaseTaskAssociation).values(values))
                return True
        except Exception as e:
            log.error(f"reorder_interface_case error: {e}")
            raise

    @staticmethod
    async def get_case_last_index(task_id: int, session: AsyncSession) -> int:
        """
        获取用例关联的最大排序值

        Args:
            task_id: 任务ID
            session: 数据库会话
        """
        result = await session.execute(
            select(InterfaceCaseTaskAssociation.step_order)
            .where(InterfaceCaseTaskAssociation.interface_task_id == task_id)
            .order_by(InterfaceCaseTaskAssociation.step_order.desc())
            .limit(1)
        )
        last_step_order = result.scalar()
        return last_step_order if last_step_order is not None else 0

    @staticmethod
    async def get_api_last_index(task_id: int, session: AsyncSession) -> int:
        """
        获取接口关联的最大排序值

        Args:
            task_id: 任务ID
            session: 数据库会话
        """
        result = await session.execute(
            select(InterfaceAPITaskAssociation.step_order)
            .where(InterfaceAPITaskAssociation.interface_task_id == task_id)
            .order_by(InterfaceAPITaskAssociation.step_order.desc())
            .limit(1)
        )
        last_step_order = result.scalar()
        return last_step_order if last_step_order is not None else 0

    @staticmethod
    async def _insert_cases_association(
            session: AsyncSession,
            task_id: int,
            case_ids: List[int],
            start_order: int
    ):
        """
        批量插入用例关联（内部方法）

        Args:
            session: 数据库会话
            task_id: 任务ID
            case_ids: 用例ID列表
            start_order: 起始排序值
        """
        if not case_ids:
            return

        values = [
            {
                "interface_task_id": task_id,
                "interface_case_id": case_id,
                "step_order": index
            }
            for index, case_id in enumerate(case_ids, start=start_order + 1)
        ]
        await session.execute(
            insert(InterfaceCaseTaskAssociation).prefix_with("IGNORE").values(values)
        )

    @staticmethod
    async def _insert_interfaces_association(
            session: AsyncSession,
            task_id: int,
            interface_ids: List[int],
            start_order: int
    ):
        """
        批量插入接口关联（内部方法）

        Args:
            session: 数据库会话
            task_id: 任务ID
            interface_ids: 接口ID列表
            start_order: 起始排序值
        """
        if not interface_ids:
            return

        values = [
            {
                "interface_task_id": task_id,
                "interface_api_id": interface_id,
                "step_order": index
            }
            for index, interface_id in enumerate(interface_ids, start=start_order + 1)
        ]
        await session.execute(
            insert(InterfaceAPITaskAssociation).prefix_with("IGNORE").values(values)
        )
