#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceCaseMapper
# @Software: PyCharm
# @Desc: 用例 Mapper - 处理用例及其步骤内容的管理

import asyncio
from typing import List, Sequence, Dict, Callable, Any

from sqlalchemy import select, insert, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.mapper.interfaceApi.dynamicMapper import InterfaceCaseDynamicMapper
from app.mapper.interfaceApi.interfaceConditionMapper import InterfaceConditionMapper
from app.mapper.interfaceApi.interfaceLoopMapper import InterfaceLoopMapper
from app.mapper.project.dbConfigMapper import DBExecuteMapper
from app.exception import CommonError
from app.mapper import Mapper
from app.model.base import User
from app.model.interfaceAPIModel.associationModel import InterfaceCaseStepContentAssociation
from app.model.interfaceAPIModel.contents import (
    InterfaceCaseContents,
    GroupStepContent,
    DBStepContent,
)
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.mapper.interfaceApi.interfaceCaseContentMapper import InterfaceCaseContentMapper
from enums.CaseEnum import CaseStepContentType
from utils import log

STEP_DELETE_STRATEGIES: Dict[CaseStepContentType, Callable] = {
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

    @classmethod
    async def insert_interface_case(cls, user: User, **kwargs) -> InterfaceCase:
        try:
            async with cls.transaction() as session:
                interface_case = await cls.save(
                    creator_user=user,
                    session=session,
                    **kwargs
                )
                await InterfaceCaseDynamicMapper.new_dynamic(
                    entity_name=interface_case.case_title,
                    entity_id=interface_case.id,
                    session=session,
                    user=user
                )
                return interface_case
        except Exception as e:
            log.exception(f"insert_interface_case error: {e}")
            raise

    @classmethod
    async def update_interface_case(cls, case_id: int, user: User, **kwargs) -> InterfaceCase:
        """
        用例调整
        """
        try:
            # 直接传 id 参数，避免修改 kwargs
            async with cls.transaction() as session:
                old_case = await cls.get_by_id(ident=case_id, session=session)
                old_case_map = old_case.to_dict()
                # 在 expunge 前通过 hook 获取快照，避免 detached instance 错误
                new_case_map_holder = {}
                new_case = await cls.update_by_id(
                    session=session,
                    id=case_id,
                    update_user=user,
                    post_update_hook=lambda t: new_case_map_holder.__setitem__('m', t.to_dict()) or t,
                    **kwargs
                )
                new_case_map = new_case_map_holder['m']
                await InterfaceCaseDynamicMapper.append_dynamic(
                    entity_id=old_case.id,
                    user=user,
                    old_info=old_case_map,
                    new_info=new_case_map,
                    session=session
                )
                return new_case
        except Exception as e:
            log.exception(f"update_interface_case error: {e}")
            raise

    # ==================== 关联操作 ====================

    @classmethod
    async def associate_interface(cls, case_id: int, user: User):
        """
        创建默认 接口进行关联

        Args:
            user: 操作用户
            case_id: 用例 ID
        Returns:
            创建的步骤内容列表
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                last_index = await cls._get_last_step_order(case_id, session)
                empty_interface = await InterfaceMapper.association_empty_interface(
                    module_id=case.module_id,
                    project_id=case.project_id,
                    user=user,
                    session=session
                )
                content = await InterfaceCaseContentMapper.insert_content(
                    user=user,
                    session=session,
                    content_type=CaseStepContentType.STEP_API,
                    target_id=empty_interface.id,
                )
                await cls._create_association(
                    session=session,
                    content_id=content.id,
                    step_order=last_index + 1,
                    case_id=case_id
                )

                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"添加私有接口步骤  {empty_interface.interface_name}"
                )
                return empty_interface
        except Exception as e:
            log.exception(f"associate_interface error: {e}")
            raise

    @classmethod
    async def associate_interfaces(
            cls,
            user: User,
            case_id: int,
            interface_id_list: List[int] = None,
            is_copy: bool = False
    ) -> List[InterfaceCaseContents]:
        """
        批量关联接口到用例

        Args:
            user: 操作用户
            case_id: 用例 ID
            interface_id_list: 接口 ID 列表
            copy: 是否复制添加（复制时创建私有接口副本）

        Returns:
            创建的步骤内容列表
        """

        if not interface_id_list:
            return []

        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                last_index = await cls._get_last_step_order(case_id, session)

                if is_copy:
                    interface_ids_to_add = []
                    for interface_id in interface_id_list:
                        new_interface = await InterfaceMapper.copy_one(
                            target=interface_id,
                            session=session,
                            is_common=False
                        )
                        interface_ids_to_add.append(new_interface.id)
                else:
                    interface_ids_to_add = interface_id_list[:]

                await session.execute(
                    update(InterfaceCase)
                    .where(InterfaceCase.id == case_id)
                    .values(case_api_num=InterfaceCase.case_api_num + len(interface_ids_to_add))
                )

                contents = [
                    await InterfaceCaseContentMapper.insert_content(
                        user=user,
                        session=session,
                        content_type=CaseStepContentType.STEP_API,
                        target_id=interface_id
                    )
                    for interface_id in interface_ids_to_add
                ]

                await cls._create_associations(
                    session=session,
                    content_ids=[content.id for content in contents],
                    start_index=last_index + 1,
                    case_id=case_id
                )

                # 重新计算并同步 case_api_num
                await cls.recompute_case_api_num(case_id, session)
                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"关联接口步骤  {''.join([content.dynamic for content in contents])}"
                )
                return contents
        except Exception as e:
            log.exception(f"associate_interfaces error: {e}")
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
                await session.execute(
                    update(InterfaceCase)
                    .where(InterfaceCase.id == case_id)
                    .values(case_api_num=InterfaceCase.case_api_num + len(group_id_list))
                )

                case_step_content_group_apis = []
                for group_id in group_id_list:
                    content = await InterfaceCaseContentMapper.insert_content(
                        user=user,
                        session=session,
                        content_type=CaseStepContentType.STEP_API_GROUP,
                        target_id=group_id
                    )
                    case_step_content_group_apis.append(content)
                last_index = await cls._get_last_step_order(case_id=case_id, session=session)
                content_ids = [content.id for content in case_step_content_group_apis]
                await cls._create_associations(
                    session=session,
                    content_ids=content_ids,
                    start_index=last_index + 1,
                    case_id=case_id
                )
                # 重新计算并同步 case_api_num
                await cls.recompute_case_api_num(case_id, session)
                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"关联接口组步骤  {''.join([content.content_name if content.content_name else '' for content in case_step_content_group_apis])}"
                )

                return case_step_content_group_apis
        except Exception as e:
            log.exception(f"associate_groups error {e}")
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
                await session.execute(
                    update(InterfaceCase)
                    .where(InterfaceCase.id == case_id)
                    .values(case_api_num=InterfaceCase.case_api_num + 1)
                )

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
                # 重新计算并同步 case_api_num
                await cls.recompute_case_api_num(case_id, session)
                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"添加条件步骤  {content.dynamic}"
                )
        except Exception as e:
            log.exception(f"associate_condition error {e}")
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
                await session.execute(
                    update(InterfaceCase)
                    .where(InterfaceCase.id == case_id)
                    .values(case_api_num=InterfaceCase.case_api_num + 1)
                )

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
                # 重新计算并同步 case_api_num
                await cls.recompute_case_api_num(case_id, session)
                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"添加步骤  {content.dynamic}"
                )
        except Exception as e:
            log.exception(f"associate_loop error : {e}")
            raise

    @classmethod
    async def associate_db(cls, user: User, case_id: int):
        """
        关联DB操作
        """
        try:
            async with cls.transaction() as session:
                await session.execute(
                    update(InterfaceCase)
                    .where(InterfaceCase.id == case_id)
                    .values(case_api_num=InterfaceCase.case_api_num + 1)
                )
                db_execute = await DBExecuteMapper.init_empty(creator_user=user, session=session)
                content = await InterfaceCaseContentMapper.insert_content(
                    session=session,
                    content_type=CaseStepContentType.STEP_API_DB,
                    target_id=db_execute.id,
                    user=user
                )
                last_index = await cls._get_last_step_order(case_id, session)
                await cls._create_association(session, case_id, content.id, last_index + 1)
                # 重新计算并同步 case_api_num
                await cls.recompute_case_api_num(case_id, session)
                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"添加步骤  {content.dynamic}"
                )
        except Exception as e:
            log.exception(f"associate_db error {e}")
            raise

    @classmethod
    async def associate_content(
            cls,
            user: User,
            case_id: int,
            content_type: int,
    ):
        try:
            content = None
            async with cls.transaction() as session:
                match content_type:
                    case CaseStepContentType.STEP_API_WAIT:
                        content = await InterfaceCaseContentMapper.insert_content(
                            user=user,
                            session=session,
                            content_type=CaseStepContentType.STEP_API_WAIT,
                            wait_time=0
                        )
                    case CaseStepContentType.STEP_API_DB:
                        content = await InterfaceCaseContentMapper.insert_content(
                            user=user,
                            session=session,
                            content_type=CaseStepContentType.STEP_API_DB,
                        )
                    case CaseStepContentType.STEP_API_ASSERT:
                        content = await InterfaceCaseContentMapper.insert_content(
                            user=user,
                            session=session,
                            content_type=CaseStepContentType.STEP_API_ASSERT,
                        )
                    case CaseStepContentType.STEP_API_SCRIPT:
                        content = await InterfaceCaseContentMapper.insert_content(
                            user=user,
                            session=session,
                            content_type=CaseStepContentType.STEP_API_SCRIPT,
                            script_text=""
                        )
                    case _:
                        raise CommonError(f"不支持的步骤类型: {content_type}")
                log.debug(f"associate_content {content} {case_id}")
                last_index = await cls._get_last_step_order(case_id=case_id, session=session)
                if not content:
                    raise CommonError(f"associate_content 创建步骤内容失败: case_id={case_id}, content_type={content_type}")
                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"关联了步骤： {content.dynamic}"
                )
                await cls._create_association(session, case_id, content.id, last_index + 1)

        except Exception as e:
            log.exception(f"associate_content error {e}")
            raise

    # ==================== 步骤管理 ====================

    @classmethod
    async def reorder_steps(
            cls,
            case_id: int,
            content_step_order: List[int],
            user: User
    ):
        """
        重新排序用例步骤（先删后插策略）

        Args:
            case_id: 用例 ID
            user: 操作人
            content_step_order: 步骤内容 ID 列表（新顺序）
        """
        if not content_step_order:
            return

        try:
            async with cls.transaction() as session:
                await session.execute(
                    delete(InterfaceCaseStepContentAssociation).where(
                        InterfaceCaseStepContentAssociation.interface_case_id == case_id
                    )
                )

                values = [
                    {
                        "interface_case_id": case_id,
                        "interface_case_content_id": step_id,
                        "step_order": index
                    }
                    for index, step_id in enumerate(content_step_order, start=1)
                ]
                await session.execute(
                    insert(InterfaceCaseStepContentAssociation).values(values)
                )

                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"进行了排序"
                )
        except Exception as e:
            log.exception(f"reorder_steps error: {e}")
            raise

    @classmethod
    async def copy_step(cls, case_id: int, content_id: int, user: User) -> None:
        """
        复制用例步骤

        Args:
            case_id: 用例 ID
            content_id: 步骤内容 ID
            user: 操作用户
        """
        try:
            async with cls.transaction() as session:
                await session.execute(
                    update(InterfaceCase)
                    .where(InterfaceCase.id == case_id)
                    .values(case_api_num=InterfaceCase.case_api_num + 1)
                )
                origin_content = await InterfaceCaseContentMapper.get_by_id(session=session, ident=content_id)
                content = await InterfaceCaseContentMapper.copy_content(
                    content=origin_content,
                    session=session,
                    user=user
                )

                last_index = await cls._get_last_step_order(case_id, session)
                await cls._create_association(
                    session, case_id, content.id, last_index + 1
                )
                # 重新计算并同步 case_api_num
                await cls.recompute_case_api_num(case_id, session)

                # dynamic
                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"复制了步骤 {origin_content.content_name}"
                )
        except Exception as e:
            log.exception(f"copy_step error: {e}")
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
                if contents:
                    # 按原顺序串行复制（或并发后保持顺序）
                    new_contents = []
                    for content in contents: 
                        new_content = await InterfaceCaseContentMapper.copy_content(
                            content=content,
                            session=session,
                            user=user
                        )
                        new_contents.append(new_content)

                    #  用 new_case.id 和 new_contents，按索引顺序设置 step_order
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

                return new_case

        except Exception as e:
            log.exception(f"error: {e}")
            raise

    @classmethod
    async def remove_case(cls, case_id: int) -> None:
        """
        删除用例及所有关联的步骤内容

        删除流程：
        1. 查询所有步骤内容
        2. 根据类型调用对应的删除策略函数（删除关联的业务实体）
        3. 显式删除每个步骤内容记录
        4. 删除用例本身

        Args:
            case_id: 用例 ID
        """
        try:
            async with cls.transaction() as session:
                case = await cls.get_by_id(session=session, ident=case_id)
                contents = await cls.query_steps(case_id, session)

                for content in contents:
                    content_type = CaseStepContentType(content.content_type)
                    strategy_func = STEP_DELETE_STRATEGIES.get(content_type)

                    if strategy_func:
                        await strategy_func(content.target_id, session)

                    await session.delete(content)

                await session.delete(case)
        except Exception as e:
            log.exception(f"remove_case error: {e}")
            raise

    @classmethod
    async def remove_step(cls, case_id: int, content_id: int, user: User) -> None:
        """
        移除用例步骤

        Args:
            case_id: 用例 ID
            user: 操作人
            content_id: 步骤内容 ID（来自 step_content_id，即子表主键）
        """
        try:
            async with cls.transaction() as session:
                content = await InterfaceCaseContentMapper.get_by_id(
                    ident=content_id, session=session
                )

                await InterfaceCaseDynamicMapper.append_dynamic_detail(
                    case_id=case_id,
                    user=user,
                    session=session,
                    description=f"移除条件步骤  {content.dynamic}"
                )
                content_type = CaseStepContentType(content.content_type)
                target_id = content.target_id

                strategy_func = STEP_DELETE_STRATEGIES.get(content_type)
                if strategy_func:
                    await strategy_func(target_id, session)

                await session.delete(content)
                await session.execute(
                    update(InterfaceCase)
                    .where(InterfaceCase.id == case_id)
                    .values(case_api_num=InterfaceCase.case_api_num - 1)
                )
                # 重新计算 case_api_num（批量操作后 -1 可能不准确）
                await cls.recompute_case_api_num(case_id, session)
        except Exception as e:
            log.exception(f"remove_step error: {e}")
            raise

    # ==================== 查询操作 ====================

    @classmethod
    async def recompute_case_api_num(
            cls,
            case_id: int,
            session: AsyncSession = None
    ) -> int:
        """
        重新计算用例的 step 关联数并写回 case_api_num。

        各个关联操作会立即更新 case_api_num (给 UI 实时反馈)，但在事务末尾
        再执行一次 COUNT 对账，可以纠正批量操作或失败回滚导致的漂移。

        Args:
            case_id: 用例 ID
            session: 可选, 不传则开新事务

        Returns:
            int: 实际关联的 step 数
        """
        async def _do(sess: AsyncSession) -> int:
            # 直接 COUNT 关联表, 跟 case_api_num 字段语义对得上 (步骤关联数)
            result = await sess.execute(
                select(InterfaceCaseStepContentAssociation).where(
                    InterfaceCaseStepContentAssociation.interface_case_id == case_id
                )
            )
            actual_count = len(result.all())
            await sess.execute(
                update(InterfaceCase)
                .where(InterfaceCase.id == case_id)
                .values(case_api_num=actual_count)
            )
            return actual_count

        if session is not None:
            return await _do(session)
        async with cls.transaction() as session:
            return await _do(session)

    @classmethod
    async def query_steps(
            cls,
            case_id: int,
            session: AsyncSession = None
    ) -> Sequence[Any]:
        """
        查询用例步骤列表

        Args:
            case_id: 用例 ID
            session: 数据库会话（可选）

        Returns:
            Sequence[ Any]: 步骤内容列表
        """
        # 只查基类 + 关联表；strategy 会自行按 target_id fetch，无需 joinedload
        stmt = (
            select(InterfaceCaseContents)
            .join(
                InterfaceCaseStepContentAssociation,
                InterfaceCaseContents.id == InterfaceCaseStepContentAssociation.interface_case_content_id
            )
            .where(InterfaceCaseStepContentAssociation.interface_case_id == case_id)
            .order_by(InterfaceCaseStepContentAssociation.step_order)
        )

        async with cls.session_scope(session) as s:
            result = await s.scalars(stmt)
            steps = result.unique().all()
        return steps

    @classmethod
    async def query_content_dicts(
            cls,
            case_id: int,
            session: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        查询用例步骤列表 (字典形式, 给 controller 直接返 dict 给前端)

        与 query_steps 的区别:
        - query_steps 返 ORM 对象 (Sequence[Any]) - 给 step strategy 用
        - query_content_dicts 返 dict 列表 - 给 controller 返 JSON 用
        - 这里在 session 内 to_dict(), 避免 lazy load 在 session 关闭后爆 detached

        Args:
            case_id: 用例 ID
            session: 数据库会话（可选）

        Returns:
            List[Dict[str, Any]]: 步骤内容的 dict 列表
        """
        # 预加载 Group/DB 子类关联并在 session 内 to_dict()，避免关闭 session
        # 后 lazy load 触发 detached。strategy 路径不依赖 relationship 预加载，
        # 因此只在 controller 端点专用方法里加 selectinload。
        stmt = (
            select(InterfaceCaseContents)
            .join(
                InterfaceCaseStepContentAssociation,
                InterfaceCaseContents.id == InterfaceCaseStepContentAssociation.interface_case_content_id
            )
            .where(InterfaceCaseStepContentAssociation.interface_case_id == case_id)
            .order_by(InterfaceCaseStepContentAssociation.step_order)
            .options(
                selectinload(GroupStepContent.interface_group),
                selectinload(DBStepContent.db_execute),
            )
        )

        async with cls.session_scope(session) as s:
            result = await s.scalars(stmt)
            steps = result.unique().all()
            # session 内 to_dict: 此刻 relationship 仍 bound, lazy load 能
            # 成功 (虽然已被 selectinload 预加载, 但保留 fallback)
            return [step.to_dict() for step in steps]

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
        } for index, content_id in enumerate(content_ids, start=start_index)]

        if values:
            await session.execute(
                insert(InterfaceCaseStepContentAssociation).prefix_with("IGNORE").values(values)
            )


__all__ = ["InterfaceCaseMapper"]
