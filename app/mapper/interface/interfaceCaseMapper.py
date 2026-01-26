#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/10/21
# @Author : cyq
# @File : interfaceCaseMapper
# @Software: PyCharm
# @Desc: 接口用例相关的Mapper实现
from typing import List, Sequence, Optional

from sqlalchemy import select, insert, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.mapper.interface import InterfaceConditionMapper, InterfaceMapper
from app.model import async_session
from app.model.base import User
from app.model.interface import InterFaceCaseModel, InterfaceModel

from app.model.interface.InterfaceCaseStepContent import InterfaceCaseStepContent, \
    InterfaceCondition, InterfaceDBExecute, InterfaceLoopModal
from app.model.interface.association import InterfaceCaseStepContentAssociation, LoopAPIAssociation
from enums.CaseEnum import CaseStepContentType, LoopTypeEnum
from utils import log


class LastIndexHelper:
    """索引查询辅助类"""

    @staticmethod
    async def get_case_step_last_index(case_id: int, session: AsyncSession) -> int:
        """
        获取用例步骤的最后索引
        :param case_id: 用例ID
        :param session: 会话对象
        :return: 最后索引值
        """
        stmt = select(InterfaceCaseStepContentAssociation.step_order).where(
            InterfaceCaseStepContentAssociation.interface_case_id == case_id
        ).order_by(
            InterfaceCaseStepContentAssociation.step_order.desc()
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def get_loop_apis_last_index(api_id: int, session: AsyncSession) -> int:
        """
        获取循环API的最后索引
        :param api_id: API ID
        :param session: 会话对象
        :return: 最后索引值
        """
        stmt = select(LoopAPIAssociation.step_order).where(
            LoopAPIAssociation.api_id == api_id
        ).order_by(
            LoopAPIAssociation.step_order.desc()
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar() or 0


class AssociationHelper:
    """关联操作辅助类"""

    @staticmethod
    async def create_case_content_association(
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
                insert(InterfaceCaseStepContentAssociation).values(values)
            )

    @staticmethod
    async def create_single_case_content_association(
            session: AsyncSession,
            case_id: int,
            content_id: int,
            step_order: int
    ):
        """
        创建单个用例与内容的关联
        :param session: 会话对象
        :param case_id: 用例ID
        :param content_id: 内容ID
        :param step_order: 步骤顺序
        """
        await session.execute(
            insert(InterfaceCaseStepContentAssociation).values({
                "interface_case_id": case_id,
                "interface_case_content_id": content_id,
                "step_order": step_order
            })
        )


class InterfaceCaseMapper(Mapper[InterFaceCaseModel]):
    """接口用例Mapper"""
    __model__ = InterFaceCaseModel

    @classmethod
    async def association_apis(cls, interface_case_id: int, interface_id_list: List[int]):
        """
        创建APIS关联
        私有API 公共API
        """
        async with async_session() as session:
            async with session.begin():
                case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=interface_case_id)
                case.apiNum += len(interface_id_list)

                case_step_content_step_apis = []
                for interface_id in interface_id_list:
                    content = await InterfaceCaseStepContentMapper.init_content(
                        session=session,
                        content_type=CaseStepContentType.STEP_API,
                        target_id=interface_id,
                    )
                    case_step_content_step_apis.append(content)

                last_index = await LastIndexHelper.get_case_step_last_index(interface_case_id, session)
                content_ids = [content.id for content in case_step_content_step_apis]
                await AssociationHelper.create_case_content_association(
                    session, interface_case_id, content_ids, last_index
                )

    @classmethod
    async def association_loop(cls, case_id: int, user: User, **kwargs):
        """
        创建loop content
        """

        try:
            async with async_session() as session:
                async with session.begin():
                    case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=case_id)
                    case.apiNum += 1
                    last_index = await LastIndexHelper.get_case_step_last_index(case_id, session)

                    loop = await InterfaceLoopMapper.save(
                        creator_user=user,
                        session=session,
                        **kwargs
                    )

                    loop_content = await InterfaceCaseStepContentMapper.init_content(
                        session=session,
                        content_type=CaseStepContentType.STEP_LOOP,
                        target_id=loop.id,
                        is_common_api=False  # 私有
                    )

                    await AssociationHelper.create_single_case_content_association(
                        session, case_id, loop_content.id, last_index + 1
                    )
                    return loop

        except Exception:
            raise

    @classmethod
    async def association_api(cls, case_id: int, user: User, module_id: int, project_id: int):
        """
        创建一个私有API 、 关联CASE
        """

        async with async_session() as session:
            async with session.begin():
                case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=case_id)
                case.apiNum += 1
                api = await InterfaceMapper.empty_api(user=user, session=session, module_id=module_id,
                                                      project_id=project_id)
                last_index = await LastIndexHelper.get_case_step_last_index(case_id, session)

                condition_content = await InterfaceCaseStepContentMapper.init_content(
                    session=session,
                    content_type=CaseStepContentType.STEP_API,
                    target_id=api.id,
                    is_common_api=False  # 私有
                )

                await AssociationHelper.create_single_case_content_association(
                    session, case_id, condition_content.id, last_index + 1
                )
                return api

    @classmethod
    async def association_api_groups(cls, interface_case_id: int, api_group_id_list: List[int]):
        """
        关联组
        """
        async with async_session() as session:
            async with session.begin():
                case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=interface_case_id)
                case.apiNum += len(api_group_id_list)

                case_step_content_group_apis = []
                for group_id in api_group_id_list:
                    content = await InterfaceCaseStepContentMapper.init_content(
                        session=session,
                        content_type=CaseStepContentType.STEP_API_GROUP,
                        target_id=group_id
                    )
                    case_step_content_group_apis.append(content)

                last_index = await LastIndexHelper.get_case_step_last_index(interface_case_id, session)
                content_ids = [content.id for content in case_step_content_group_apis]
                await AssociationHelper.create_case_content_association(
                    session, interface_case_id, content_ids, last_index
                )

    @classmethod
    async def association_api_condition(cls, interface_case_id: int, user: User):
        """
        关联条件
        """
        from .interfaceMapper import InterfaceConditionMapper

        async with async_session() as session:
            async with session.begin():
                case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=interface_case_id)
                case.apiNum += 1

                condition = await InterfaceConditionMapper.add_empty_condition(session=session, user=user)

                condition_content = await InterfaceCaseStepContentMapper.init_content(
                    session=session,
                    content_type=CaseStepContentType.STEP_API_CONDITION,
                    target_id=condition.id
                )

                last_index = await LastIndexHelper.get_case_step_last_index(interface_case_id, session)
                await AssociationHelper.create_single_case_content_association(
                    session, interface_case_id, condition_content.id, last_index + 1
                )

    @classmethod
    async def reorder_content_step(cls, case_id: int, content_step_order: List[int]):
        """
        步骤排序
        """
        async with async_session() as session:
            # 构建批量更新数据
            update_values = []
            for index, step_id in enumerate(content_step_order, start=1):
                update_values.append({
                    "interface_case_content_id": step_id,
                    "interface_case_id": case_id,
                    "step_order": index
                })

            # 批量更新
            if update_values:
                await session.execute(
                    update(InterfaceCaseStepContentAssociation),
                    update_values
                )

            await session.commit()

    @classmethod
    async def remove_content_step(cls, case_id: int, content_step_id: int):
        """
        移除step
        删除 CONTENT_STEP 解除关联
        API 私有STEP 直接删除。
        API CONDITION 删除
        """
        from .interfaceMapper import InterfaceConditionMapper, InterfaceMapper

        async with async_session() as session:
            async with session.begin():
                case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=case_id)
                case.apiNum -= 1

                content: InterfaceCaseStepContent = await InterfaceCaseStepContentMapper.get_by_id(
                    ident=content_step_id, session=session)
                log.info(f"delete content  {content.content_type}  {content.is_common_api}")

                # API 步骤 私有API 删除
                if content.content_type == CaseStepContentType.STEP_API and not content.is_common_api:
                    interface = await InterfaceMapper.get_by_id(ident=content.target_id, session=session)
                    await session.delete(interface)

                # API CONDITION 删除
                if content.content_type == CaseStepContentType.STEP_API_CONDITION:
                    condition = await InterfaceConditionMapper.get_by_id(ident=content.target_id, session=session)
                    await session.delete(condition)

                await session.delete(content)

    @classmethod
    async def copy_content(cls, case_id: int, content_id: int, user: User):
        """
        复制步骤
        """
        async with async_session() as session:
            async with session.begin():
                case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=case_id)
                case.apiNum += 1

                content = await InterfaceCaseStepContentMapper.copy_content(
                    content_id=content_id,
                    session=session,
                    user=user
                )

                last_index = await LastIndexHelper.get_case_step_last_index(case_id, session)
                await AssociationHelper.create_single_case_content_association(
                    session, case_id, content.id, last_index + 1
                )

    @classmethod
    async def copy_case(cls, case_id: int, user: User):
        """
        复制用例
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    case: InterFaceCaseModel = await cls.get_by_id(ident=case_id, session=session)
                    new_case = cls.__model__(
                        creator=user.id,
                        creatorName=user.username,
                        **case.copy_map()
                    )
                    new_case.title = case.title + "（副本）"
                    await cls.add_flush_expunge(session, new_case)

                    contents = await cls.query_content_step(case_id=case_id, session=session)
                    for content in contents:
                        new_content = await InterfaceCaseStepContentMapper.copy_content(
                            content_id=content.id,
                            user=user,
                            session=session
                        )
                        last_index = await LastIndexHelper.get_case_step_last_index(new_case.id, session)
                        await AssociationHelper.create_single_case_content_association(
                            session, new_case.id, new_content.id, last_index + 1
                        )
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def query_content(cls, case_id: int):
        """
        查询步骤返回
        """
        async with async_session() as session:
            contents = await cls.query_content_step(case_id=case_id, session=session)
            log.info(f"contents = {contents}")
            return contents

    @classmethod
    async def remove_case(cls, case_id: int):
        """
        删除用例
        删除关联
        删除condition
        """
        async with async_session() as session:
            async with session.begin():
                case: InterFaceCaseModel = await cls.get_by_id(session=session, ident=case_id)

                contents = await cls.query_content_step(case_id, session)
                if contents:
                    for content in contents:
                        if content.content_type == CaseStepContentType.STEP_API_CONDITION:
                            condition: InterfaceCondition = await InterfaceConditionMapper.get_by_id(
                                ident=content.target_id,
                                session=session
                            )
                            await session.delete(condition)
                        await session.delete(content)
                await session.delete(case)

    @staticmethod
    async def query_content_step(case_id: int, session: AsyncSession) -> Sequence[InterfaceCaseStepContent]:
        """
        查询步骤
        """
        scalars_data = await session.scalars(
            select(InterfaceCaseStepContent).join(
                InterfaceCaseStepContentAssociation,
                InterfaceCaseStepContent.id == InterfaceCaseStepContentAssociation.interface_case_content_id
            ).where(
                InterfaceCaseStepContentAssociation.interface_case_id == case_id
            ).order_by(
                InterfaceCaseStepContentAssociation.step_order
            )
        )
        return scalars_data.all()

    @classmethod
    async def append_record(cls, creatorUser: User, recordId: str, caseId: int):
        """
        录制 append 用例
        """

        try:
            case: InterFaceCaseModel = await cls.get_by_id(ident=caseId)
            if not case:
                raise Exception("用例不存在")

            recordApi = await InterfaceMapper.copy_record_2_api(recordId, creatorUser)
            recordApi['name'] = recordApi['url'][:5] + '...'
            recordApi['desc'] = f"{recordApi['method']} : {recordApi['url']} "
            recordApi['is_common'] = False
            recordApi['status'] = "DEBUG"
            recordApi['level'] = "P2"
            recordApi['project_id'] = case.project_id
            recordApi['module_id'] = case.module_id

            async with async_session() as session:
                async with session.begin():
                    api = await InterfaceMapper.save(
                        creator_user=creatorUser,
                        session=session,
                        **recordApi
                    )

                    case.apiNum += 1
                    last_index = await LastIndexHelper.get_case_step_last_index(caseId, session)

                    condition_content = await InterfaceCaseStepContentMapper.init_content(
                        session=session,
                        content_type=CaseStepContentType.STEP_API,
                        target_id=api.id,
                        is_common_api=False  # 私有
                    )

                    await AssociationHelper.create_single_case_content_association(
                        session, caseId, condition_content.id, last_index + 1
                    )
        except Exception as e:
            log.error(e)
            raise


class InterfaceCaseStepContentMapper(Mapper[InterfaceCaseStepContent]):
    """接口用例步骤内容Mapper"""
    __model__ = InterfaceCaseStepContent

    @classmethod
    async def add_content(cls,
                          case_id: int,
                          user: User,
                          content_type: CaseStepContentType,
                          api_wait_time: Optional[int] = None,
                          api_script_text: Optional[str] = None,
                          api_assert_list: Optional[List] = None,
                          is_common_api: int = 1):
        """
        添加步骤
        添加content 本身
        - wait
        - script
        - assert

        添加外键
        - db execute
        """
        log.info(
            f"add_content "
            f"content_type = {content_type} "
            f"api_wait_time = {api_wait_time}"
            f"api_script_text = {api_script_text}"
            f"api_assert_list = {api_assert_list}"
        )

        async with async_session() as session:
            async with session.begin():
                case = await InterfaceCaseMapper.get_by_id(ident=case_id, session=session)
                case.apiNum += 1

                content: InterfaceCaseStepContent = InterfaceCaseStepContent(
                    content_type=content_type,
                    api_wait_time=api_wait_time,
                    api_script_text=api_script_text,
                    creator=user.id,
                    creatorName=user.username,
                    is_common_api=is_common_api,
                    api_assert_list=api_assert_list
                )

                last_index = await LastIndexHelper.get_case_step_last_index(case_id, session)

                # db
                if content_type == CaseStepContentType.STEP_API_DB:
                    from .interfaceMapper import InterfaceCaseContentDBExecuteMapper
                    _db = await InterfaceCaseContentDBExecuteMapper.init_empty(creator_user=user,
                                                                               session=session)
                    content.target_id = _db.id

                await cls.add_flush_expunge(session, content)
                await AssociationHelper.create_single_case_content_association(
                    session, case_id, content.id, last_index + 1
                )

    @classmethod
    async def init_content(cls,
                           session: AsyncSession,
                           content_type: CaseStepContentType,
                           target_id: int,
                           is_common_api: int = 1,
                           ) -> InterfaceCaseStepContent:
        """
        初始化content
        """
        from .interfaceMapper import InterfaceMapper, InterfaceGroupMapper

        content: InterfaceCaseStepContent = InterfaceCaseStepContent(
            content_type=content_type,
            target_id=target_id,
            is_common_api=is_common_api,
        )

        match content_type:
            case CaseStepContentType.STEP_API:
                if target_id:
                    interfaceAPI = await InterfaceMapper.get_by_id(ident=target_id, session=session)
                    content.content_name = interfaceAPI.name
                    content.content_desc = interfaceAPI.method
            case CaseStepContentType.STEP_API_GROUP:
                if target_id:
                    interfaceGroup = await InterfaceGroupMapper.get_by_id(ident=target_id, session=session)
                    content.content_name = interfaceGroup.name
                    content.content_desc = interfaceGroup.description

            case CaseStepContentType.STEP_LOOP:
                if target_id:
                    loop = await InterfaceLoopMapper.get_by_id(ident=target_id, session=session)
                    content.content_name = LoopTypeEnum(loop.loop_type).name

            case CaseStepContentType.STEP_API_CONDITION:
                pass

        return await cls.add_flush_expunge(session, content)

    @classmethod
    async def get_type_obj(cls, content_id: int, session: AsyncSession):
        """
        通过type 获取 对于模型
        """
        from .interfaceMapper import InterfaceMapper, InterfaceGroupMapper, InterfaceConditionMapper

        content: InterfaceCaseStepContent = await cls.get_by_id(ident=content_id, session=session)

        if content.content_type == CaseStepContentType.STEP_API and content.target_id:
            return await InterfaceMapper.get_by_id(ident=content.target_id, session=session)

        if content.content_type == CaseStepContentType.STEP_API_GROUP and content.target_id:
            return await InterfaceGroupMapper.get_by_id(ident=content.target_id, session=session)

        if content.content_type == CaseStepContentType.STEP_API_CONDITION and content.target_id:
            return await InterfaceConditionMapper.get_by_id(ident=content.target_id, session=session)

    @classmethod
    async def copy_content(cls, content_id: int, session: AsyncSession, user: User):
        """
        复制 Case Step Content
        condition 单独复制
        """
        from .interfaceMapper import InterfaceMapper, InterfaceConditionMapper

        content = await cls.get_by_id(ident=content_id, session=session)
        new_content = cls.__model__(
            **content.copy_map()
        )

        # 私有API的复制
        log.debug(f"复制私有API {content.is_common_api}")

        match content.content_type:
            # 复制 content 是 API
            # 复制 API
            # if common =》self
            case CaseStepContentType.STEP_API:
                new_api = await InterfaceMapper.copy_api(
                    apiId=content.target_id,
                    session=session,
                    creator=user,
                    is_common=False
                )
                new_content.target_id = new_api.id
                new_content.content_name = new_api.name
                new_content.content_desc = new_api.method
                new_content.is_common_api = False

            case CaseStepContentType.STEP_API_CONDITION:
                condition = await InterfaceConditionMapper.copy_one(content.target_id, session)
                new_content.target_id = condition.id

        return await cls.add_flush_expunge(session, new_content)


class InterfaceCaseContentDBExecuteMapper(Mapper[InterfaceDBExecute]):
    """接口用例数据库执行Mapper"""
    __model__ = InterfaceDBExecute

    @classmethod
    async def init_empty(cls, creator_user: User, session: AsyncSession = None) -> InterfaceDBExecute:
        """
        初始化空的数据库执行对象
        :param creator_user: 创建人
        :param session: 会话对象
        :return: 数据库执行对象
        """
        if session:
            return await cls.save(creator_user=creator_user, session=session)
        else:
            async with async_session() as session:
                return await cls.save(creator_user=creator_user, session=session)


class InterfaceLoopMapper(Mapper[InterfaceLoopModal]):
    """接口循环Mapper"""
    __model__ = InterfaceLoopModal

    @classmethod
    async def add_empty_loop(cls, session: AsyncSession, user: User):
        """
        添加空 loop
        :param session: 会话对象
        :param user: 用户对象
        :return: 循环对象
        """
        loop = cls.__model__(
            creator=user.id,
            creatorName=user.username,
        )
        return await cls.add_flush_expunge(
            session=session,
            model=loop
        )

    @classmethod
    async def association_apis(cls, loop_id: int, interface_id_list: List[int]):
        """
        关联api
        :param loop_id: 循环ID
        :param interface_id_list: 接口ID列表
        """
        async with async_session() as session:
            last_index = await LastIndexHelper.get_loop_apis_last_index(loop_id, session)
            values = [
                {
                    "loop_id": loop_id,
                    "api_id": interface_id,
                    "step_order": index
                } for index, interface_id in enumerate(interface_id_list, start=last_index + 1)
            ]

            if values:
                await session.execute(
                    insert(LoopAPIAssociation).values(values)
                )
            await session.commit()

    @classmethod
    async def query_loop_apis_by_content_id(cls, loop_id: int):
        """
        查询loop 子步骤
        :param loop_id: 循环ID
        :return: 接口列表
        """
        async with async_session() as session:
            loop = await cls.get_by_id(ident=loop_id, session=session)

            stmt = select(InterfaceModel).join(LoopAPIAssociation).where(
                LoopAPIAssociation.loop_id == loop.id,
                InterfaceModel.id == LoopAPIAssociation.api_id
            ).order_by(
                LoopAPIAssociation.step_order
            )
            result = await session.scalars(stmt)
            return result.all()

    @classmethod
    async def remove_association_api(cls, loop_id: int, interface_id: int):
        """
        解除关联
        """
        async with async_session() as session:
            await session.execute(
                delete(LoopAPIAssociation).where(
                    and_(
                        LoopAPIAssociation.loop_id == loop_id,
                        LoopAPIAssociation.api_id == interface_id
                    )
                )
            )
            await session.commit()

    @classmethod
    async def reorder_condition_apis(cls, loop_id: int, interface_id_list: List[int]):
        """
        子步骤重新排序
        """
        async with async_session() as session:
            # 先删除该条件下的所有关联
            await session.execute(
                delete(LoopAPIAssociation).where(
                    LoopAPIAssociation.loop_id == loop_id
                )
            )

            values = []
            for index, interface_id in enumerate(interface_id_list, start=1):
                values.append({
                    "loop_id": loop_id,
                    "api_id": interface_id,
                    "step_order": index
                })

            if values:
                await session.execute(
                    insert(LoopAPIAssociation).values(values)
                )
            await session.commit()
