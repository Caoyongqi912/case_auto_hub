#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceCaseMapper
# @Software: PyCharm
# @Desc: 用例 Mapper - 处理用例及其步骤内容的管理

import asyncio
from typing import List, Sequence, Dict, Callable

from sqlalchemy import select, insert, delete, update
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper.interfaceApi.interfaceConditionMapper import InterfaceConditionMapper
from app.mapper.interfaceApi.interfaceLoopMapper import InterfaceLoopMapper
from app.model import async_session
from app.mapper import Mapper
from app.model.base import User
from app.model.interfaceAPIModel import contents
from app.model.interfaceAPIModel.contents import (
    InterfaceCaseContents,
    APIStepContent,
    ConditionStepContent,
    LoopStepContent,
    GroupStepContent,
    DBStepContent,
    WhileStepContent,
)
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.mapper.interfaceApi.interfaceCaseContentMapper import InterfaceCaseContentMapper
from enums.CaseEnum import CaseStepContentType
from utils import log





STEP_DELETE_STRATEGIES: Dict[CaseStepContentType, Callable[[int, AsyncSession], bool]] = {
    CaseStepContentType.STEP_API: InterfaceMapper.remove_self_interface,
    CaseStepContentType.STEP_API_CONDITION: InterfaceConditionMapper.delete_condition,
    CaseStepContentType.STEP_LOOP: InterfaceLoopMapper.delete_loop,
}




class InterfaceCaseMapper(Mapper[InterfaceCase]):
    """
    用例 Mapper

    提供用例的增删改查、步骤管理、复制等功能
    """

    __model__ = InterfaceCase

    # ==================== 关联操作 ====================

    @classmethod
    async def associate_interface(
        cls,
        user: User,
        case_id: int,
        interface_id: int = None
    ):
        """
        关联单个接口到用例

        如果不提供 interface_id，则创建空白接口

        Args:
            user: 操作用户
            case_id: 用例 ID
            interface_id: 接口 ID（可选）

        Returns:
            InterfaceCaseContents: 创建的步骤内容
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                case.case_api_num += 1

                if interface_id:
                    content = await InterfaceCaseContentMapper.insert_content(
                        session=session,
                        content_type=CaseStepContentType.STEP_API,
                        target_id=interface_id,
                        user=user
                    )
                else:
                    empty_interface = await InterfaceMapper.association_empty_interface(
                        user=user,
                        module_id=case.module_id,
                        project_id=case.project_id,
                        session=session,
                    )
                    content = await InterfaceCaseContentMapper.insert_content(
                        session=session,
                        content_type=CaseStepContentType.STEP_API,
                        target_id=empty_interface.id,
                        user=user
                    )
                last_index = await cls._get_last_step_order(case_id, session)
                await cls._create_association(session, case_id, content.id, last_index + 1)
        except Exception as e:
            log.error(f"associate_interface error: {e}")
            raise

    @classmethod
    async def associate_interfaces(
        cls,
        user: User,
        case_id: int,
        interface_id_list: List[int]
    ):
        """
        批量关联接口到用例

        Args:
            user: 操作用户
            case_id: 用例 ID
            interface_id_list: 接口 ID 列表

        """
        if not interface_id_list:
            return []

        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                case.case_api_num += len(interface_id_list)

                last_index = await cls._get_last_step_order(case_id, session)
                contents = []

                for idx, interface_id in enumerate(interface_id_list):
                    content = await InterfaceCaseContentMapper.insert_content(
                        user=user,
                        session=session,
                        content_type=CaseStepContentType.STEP_API,
                        target_id=interface_id
                    )
                    contents.append(content)


                content_ids = [content.id for content in contents]
                await cls._create_associations(
                    session=session,
                    content_ids=content_ids,
                    start_index=last_index + 1,
                    case_id=case_id
                )
        except Exception as e:
            log.error(f"associate_interfaces error: {e}")
            raise

    @classmethod
    async def associate_groups(
        cls,
        user: User,
        case_id: int,
        group_id_list: List[int]
    ):
        """
        批量关联接口组到用例

        Args:
            user: 操作用户
            case_id: 用例 ID
            group_id_list: 接口组 ID 列表

        Returns:
            List[InterfaceCaseContents]: 创建的步骤内容列表
        """
        if not group_id_list:
            return []

        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                case.case_api_num += len(group_id_list)

            case_step_content_group_apis = []
            for group_id in group_id_list:
                content = await InterfaceCaseContentMapper.insert_content(
                    user=user,
                    session=session,
                    content_type=CaseStepContentType.STEP_API_GROUP,
                    target_id=group_id
                )
                case_step_content_group_apis.append(content)
            last_index = await cls._get_last_step_order(case_id=case_id,session=session)
            content_ids = [content.id for content in case_step_content_group_apis]
            await cls._create_associations(
                session=session,
                content_ids=content_ids,
                start_index=last_index + 1,
                case_id=case_id
            )
        except Exception as e:
            log.error(f"associate_groups error {e}")
            raise

    @classmethod
    async def associate_condition(
        cls,
        user: User,
        case_id: int
    ):
        """
        关联条件到用例

        Args:
            user: 操作用户
            case_id: 用例 ID

        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                case.case_api_num += 1

                condition = await InterfaceConditionMapper.add_empty_condition(
                    session=session, user=user
                )
                content = await InterfaceCaseContentMapper.insert_content(
                    session=session,
                    content_type=CaseStepContentType.STEP_API_CONDITION,
                    target_id=condition.id,
                    user=user
                )

                last_index = await cls._get_last_step_order(case_id, session)
                await cls._create_association(session, case_id, content.id, last_index + 1)
        except Exception as e:
            log.error(f"associate_condition error {e}")
            raise


    @classmethod
    async def associate_loop(
        cls,
        user: User,
        case_id: int,
        **kwargs
    ):
        """
        关联循环到用例

        Args:
            user: 操作用户
            case_id: 用例 ID
            **kwargs: 循环配置参数

        Returns:
            Dict: 包含 content 和 loop 的字典
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                case.case_api_num += 1

                loop = await InterfaceLoopMapper.save(
                    creator_user=user,
                    session=session,
                    **kwargs
                )
                content = await InterfaceCaseContentMapper.insert_content(
                    session=session,
                    content_type=CaseStepContentType.STEP_LOOP,
                    target_id=loop.id,
                    user=user
                )

                last_index = await cls._get_last_step_order(case_id, session)
                await cls._create_association(session, case_id, content.id, last_index + 1)
        except Exception as e:
            log.error(f"associate_loop error : {e}")
            raise

    # ==================== 步骤管理 ====================

    @classmethod
    async def reorder_steps(
        cls,
        case_id: int,
        content_step_order: List[int]
    ):
        """
        重新排序用例步骤


        Args:
            case_id: 用例 ID
            content_step_order: 步骤内容 ID 列表（新顺序）
        """

        try:
            async with cls.transaction() as session:
                update_values = [
                    {
                        "interface_case_content_id": step_id,
                        "interface_case_id": case_id,
                        "step_order": index
                    }
                    for index, step_id in enumerate(content_step_order, start=1)
                ]
                await session.execute(
                    update(InterfaceCaseStepContentAssociation),
                    update_values
                )
        except Exception as e:
            log.error(f"reorder_steps error: {e}")
            raise


    @classmethod
    async def copy_step(cls, case_id: int, content_id: int, user: User)->None:
        """
        复制用例步骤

        Args:
            case_id: 用例 ID
            content_id: 步骤内容 ID
            user: 操作用户
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                case.case_api_num += 1

                content = await InterfaceCaseContentMapper.copy_content(
                    content_id=content_id,
                    session=session,
                    user=user
                )

                last_index = await cls._get_last_step_order(case_id, session)
                await cls._create_association(
                    session, case_id, content.id, last_index + 1
                )

        except Exception as e:
            log.error(f"copy_step error: {e}")
            raise
    
    
    @classmethod
    async def copy_case(cls, case_id: int, user: User) -> None:
        """
        复制用例

        Args:
            case_id: 源用例 ID
            user: 操作用户

        Returns:
            InterfaceCase: 复制后的用例
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(ident=case_id, session=session)

                new_case = cls.__model__(
                    creator=user.id,
                    creatorName=user.username,
                    **case.copy_map()
                )
                new_case.case_title = case.case_title + "（副本）"
                await cls.add_flush_expunge(session, new_case)

                contents = await cls.query_steps(case_id=case_id, session=session)

                # 按原顺序串行复制（或并发后保持顺序）
                new_contents = []
                for content in contents:  # ✅ 串行，保持顺序
                    new_content = await InterfaceCaseContentMapper.copy_content(
                        content=content,
                        session=session,
                        user=user
                    )
                    new_contents.append(new_content)

                # ✅ 用 new_case.id 和 new_contents，按索引顺序设置 step_order
                assoc_values = [
                    {
                        "interface_case_id": new_case.id,                   
                        "interface_case_content_id": new_content.id, 
                        "step_order": index
                    }
                    for index, new_content in enumerate(new_contents, start=1)
                ]
                await session.execute(
                     insert(InterfaceCaseStepContentAssociation).values(assoc_values)
                )
                
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def remove_case(cls, case_id: int) -> None:
        """
        删除用例

        同时删除：
        - 所有关联的步骤内容
        - 条件步骤关联的条件
        - 循环步骤关联的循环
        - 私有 API

        Args:
            case_id: 用例 ID
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                contents = await cls.query_steps(case_id, session)

                delete_tasks = []
                for content in contents:
                    strategy_func = STEP_DELETE_STRATEGIES.get(content.content_type)
                    if strategy_func:
                        delete_tasks.append(strategy_func(content.target_id, session))

                for i in range(0, len(delete_tasks), 5):
                    batch = delete_tasks[i:i + 5]
                    await asyncio.gather(*batch)

                await session.delete(case)
        except Exception as e:
            log.error(f"delete_case error: {e}")
            raise
    
    
    
    @classmethod
    async def remove_step(cls, case_id: int, content_id: int) -> None:
        """
        移除用例步骤

        根据步骤类型执行不同的删除逻辑：
        - 私有 API：删除关联的接口
        - 条件步骤：删除关联的条件及其关联的非公共接口
        - 循环步骤：删除关联的循环及其关联的非公共接口
        - 其他步骤：仅删除步骤内容

        Args:
            case_id: 用例 ID
            content_id: 步骤内容 ID
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                content = await InterfaceCaseContentMapper.get_by_id(
                    ident=content_id, session=session
                )

                log.info(f"delete content type={content.content_type}")

                strategy_func = STEP_DELETE_STRATEGIES.get(content.content_type)
                if strategy_func:
                    await strategy_func(content.target_id, session)

                if case.case_api_num > 0:
                    case.case_api_num -= 1
        except Exception as e:
            log.error(f"remove_step error: {e}")
            raise

    # ==================== 查询操作 ====================

    @classmethod
    async def query_steps(
        cls,
        case_id: int,
        session: AsyncSession = None
    ) -> Sequence[InterfaceCaseContents]:
        """
        查询用例步骤列表

        Args:
            case_id: 用例 ID
            session: 数据库会话（可选）

        Returns:
            Sequence[InterfaceCaseContents]: 步骤内容列表，按顺序排序，预加载关联数据
        """
        async def _query(s: AsyncSession):
            result = await s.scalars(
                select(InterfaceCaseContents)
                .join(
                    InterfaceCaseStepContentAssociation,
                    InterfaceCaseContents.id == InterfaceCaseStepContentAssociation.interface_case_content_id
                )
                .options(
                    joinedload(APIStepContent.interface_api),
                    joinedload(ConditionStepContent.interface_condition),
                    joinedload(LoopStepContent.interface_loop),
                    joinedload(GroupStepContent.interface_group),
                    joinedload(DBStepContent.db_execute),
                    joinedload(WhileStepContent.interface_condition),
                )
                .where(InterfaceCaseStepContentAssociation.interface_case_id == case_id)
                .order_by(InterfaceCaseStepContentAssociation.step_order)
            )
            return result.unique().all()

        if session:
            return await _query(session)
        else:
            async with async_session() as s:
                return await _query(s)
            
            
    # ==================== 私有方法 ====================

    @classmethod
    async def _get_last_step_order(cls, case_id: int, session: AsyncSession) -> int:
        """
        获取当前用例的最大步骤排序值

        Args:
            case_id: 用例 ID
            session: 数据库会话

        Returns:
            int: 当前最大排序值，无步骤则返回 0
        """
        stmt = (
            select(InterfaceCaseStepContentAssociation.step_order)
            .where(InterfaceCaseStepContentAssociation.interface_case_id == case_id)
            .order_by(InterfaceCaseStepContentAssociation.step_order.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar() or 0


    @classmethod
    async def _create_association(
        cls,
        session: AsyncSession,
        case_id: int,
        content_id: int,
        step_order: int
    ) -> None:
        """
        创建用例与步骤内容的关联

        Args:
            session: 数据库会话
            case_id: 用例 ID
            content_id: 步骤内容 ID
            step_order: 步骤顺序
        """
        await session.execute(
            insert(InterfaceCaseStepContentAssociation).prefix_with("IGNORE").values({
                "interface_case_id": case_id,
                "interface_case_content_id": content_id,
                "step_order": step_order
            })
        )

    @staticmethod
    async def _create_associations(
            session: AsyncSession,
            case_id: int,
            content_ids: List[int],
            start_index: int
    ):
        """
        创建用例与内容的关联
        :param session: 会话对象
        :param case_id: 用例ID
        :param content_ids: 内容ID列表
        :param start_index: 起始索引
        """
        values = [{
            "interface_case_id": case_id,
            "interface_case_content_id": content_id,
            "step_order": index
        } for index, content_id in enumerate(content_ids, start=start_index + 1)]

        if values:
            await session.execute(
                insert(InterfaceCaseStepContentAssociation).prefix_with("IGNORE").values(values)
            )



__all__ = ["InterfaceCaseMapper"]
