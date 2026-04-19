#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/10
# @Author : cyq
# @File : interfaceResultMapper
# @Software: PyCharm
# @Desc: 接口执行结果 Mapper
from typing import Dict, Type, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base.user import User
from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceResult,
    InterfaceTaskResult,
    InterfaceCaseResult,
    InterfaceCaseContentResult,
    APIStepContentResult,
    GroupStepContentResult,
    ConditionStepContentResult,
    ScriptStepContentResult,
    DBStepContentResult,
    WaitStepContentResult,
    AssertStepContentResult,
    LoopStepContentResult,
)
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.model.base import EnvModel
from enums.CaseEnum import CaseStepContentType
from utils import log


class InterfaceCaseResultMapper(Mapper[InterfaceCaseResult]):
    __model__ = InterfaceCaseResult

    @classmethod
    async def page_case_results(cls):
        """业务流结果分页"""
        pass

    @classmethod
    async def query_case_result(cls, case_result_id: int):
        pass

    # @classmethod
    # async def init_case_result(cls, user: User, case: InterfaceCase, env: EnvModel):
    #
    #     try:
    #         async with cls.transaction() as session:
    #             case_result = InterfaceCaseResult(
    #                 case_id=case.id,
    #                 env_id=env.id,
    #                 starter_id=user.id,
    #                 starter_name=user.username,
    #             )
    #
    #     except Exception:
    #         pass

    
    @classmethod
    async def set_result_field(cls, caseResult: InterfaceCaseResult):
        try:
            async with cls.transaction() as session:
                await cls.add_flush_expunge(session, caseResult)
        except Exception as e:
            log.error(e)
            raise e



class InterfaceResultMapper(Mapper[InterfaceResult]):
    __model__ = InterfaceResult

    @classmethod
    async def set_result(cls, result: InterfaceResult):
        """
        设置接口结果
        """
        try:
            async with cls.transaction() as session:
                await cls.add_flush_expunge(session, result)
        except Exception as e:
            log.error(e)
            raise e

    @classmethod
    async def get_by_content_result_id(
        cls,
        content_result_id: int,
        session: AsyncSession = None
    ) -> List[InterfaceResult]:
        """
        通过 content_result_id 查询关联的 InterfaceResult

        Args:
            content_result_id: 步骤内容结果 ID
            session: 可选的数据库会话

        Returns:
            List[InterfaceResult]: 关联的接口结果列表
        """
        try:
            async with cls.session_scope(session) as session:
                stmt = select(InterfaceResult).where(
                    InterfaceResult.content_result_id == content_result_id
                )
                results = await session.scalars(stmt)
                return results.all()
        except Exception as e:
            log.error(f"get_by_content_result_id error: {e}")
            raise

    
class InterfaceTaskResultMapper(Mapper[InterfaceTaskResult]):
    __model__ = InterfaceTaskResult

    @classmethod
    async def set_result_field(cls, caseResult: InterfaceTaskResult):
        try:
            async with cls.transaction() as session:
                await cls.add_flush_expunge(session, caseResult)
        except Exception as e:
            log.error(e)
            raise e
    
    @classmethod
    async def delete_by_task_id(cls, task_id: int):
        """删除"""
        pass
    
class InterfaceContentStepResultMapper(Mapper[InterfaceCaseContentResult]):
    """
    步骤内容结果 Mapper

    设计说明：
    - 使用 Joined Table Inheritance 实现多态结果存储
    - 通过 content_type 自动路由到对应的子类结果表
    - 支持查询、插入、更新等操作
    """
    __model__ = InterfaceCaseContentResult

    RESULT_TYPE_MAP: Dict[CaseStepContentType, Type[InterfaceCaseContentResult]] = {
        CaseStepContentType.STEP_API: APIStepContentResult,
        CaseStepContentType.STEP_API_GROUP: GroupStepContentResult,
        CaseStepContentType.STEP_API_CONDITION: ConditionStepContentResult,
        CaseStepContentType.STEP_API_SCRIPT: ScriptStepContentResult,
        CaseStepContentType.STEP_API_DB: DBStepContentResult,
        CaseStepContentType.STEP_API_WAIT: WaitStepContentResult,
        CaseStepContentType.STEP_API_ASSERT: AssertStepContentResult,
        CaseStepContentType.STEP_LOOP: LoopStepContentResult,
    }

    @classmethod
    async def get_by_id(cls, ident: int, session: AsyncSession = None) -> InterfaceCaseContentResult:
        """
        根据 ID 获取步骤内容结果（多态查询）

        注意：在 Joined Table Inheritance 中，ident 是基类表的主键（id），
        SQLAlchemy 会自动处理多态返回对应的子类实例

        Args:
            ident: 步骤内容结果 ID
            session: 可选的数据库会话

        Returns:
            InterfaceCaseContentResult: 步骤内容结果实例（具体子类）
        """
        try:
            async with cls.session_scope(session) as session:
                result = await session.get(InterfaceCaseContentResult, ident)
                if not result:
                    raise ValueError(f"步骤内容结果不存在，id: {ident}")
                return result
        except Exception as e:
            log.error(e)
            raise e


    @classmethod
    async def query_by_case_result_id(
        cls,
        case_result_id: int,
        session: AsyncSession = None
    ) -> List[InterfaceCaseContentResult]:
        """
        通过 case_result_id 查询所有步骤内容结果

        Args:
            case_result_id: 用例执行结果 ID
            session: 可选的数据库会话

        Returns:
            List[InterfaceCaseContentResult]: 步骤内容结果列表（包含多态子类）
        """
        stmt = (
            select(InterfaceCaseContentResult)
            .where(InterfaceCaseContentResult.case_result_id == case_result_id)
            .order_by(InterfaceCaseContentResult.content_step)
        )

        try:
            async with cls.session_scope(session) as session:
                result = await session.scalars(stmt)
                return result.all()
        except Exception as e:
            log.error(e)
            raise e


    @classmethod
    async def query_by_task_result_id(
        cls,
        task_result_id: int,
        session: AsyncSession = None
    ) -> List[InterfaceCaseContentResult]:
        """
        通过 task_result_id 查询所有步骤内容结果

        Args:
            task_result_id: 任务执行结果 ID
            session: 可选的数据库会话

        Returns:
            List[InterfaceCaseContentResult]: 步骤内容结果列表（包含多态子类）
        """
        stmt = (
            select(InterfaceCaseContentResult)
            .where(InterfaceCaseContentResult.task_result_id == task_result_id)
            .order_by(InterfaceCaseContentResult.content_step)
        )

        if session:
            result = await session.scalars(stmt)
            return result.all()
        else:
            async with cls.session_scope() as session:
                result = await session.scalars(stmt)
                return result.all()

    @classmethod
    async def query_by_content_type(
        cls,
        case_result_id: int,
        content_type: CaseStepContentType,
        session: AsyncSession = None
    ) -> List[InterfaceCaseContentResult]:
        """
        通过 case_result_id 和 content_type 查询特定类型的步骤内容结果

        Args:
            case_result_id: 用例执行结果 ID
            content_type: 步骤类型
            session: 可选的数据库会话

        Returns:
            List[InterfaceCaseContentResult]: 指定类型的步骤内容结果列表
        """
        stmt = (
            select(InterfaceCaseContentResult)
            .where(
                InterfaceCaseContentResult.case_result_id == case_result_id,
                InterfaceCaseContentResult.content_type == content_type
            )
            .order_by(InterfaceCaseContentResult.content_step)
        )

        if session:
            result = await session.scalars(stmt)
            return result.all()
        else:
            async with cls.session_scope() as session:
                result = await session.scalars(stmt)
                return result.all()

    @classmethod
    async def insert_result(
        cls,
        content_type: CaseStepContentType,
        case_result_id: Optional[int] = None,
        task_result_id: Optional[int] = None,
        content_id: Optional[int] = None,
        content_name: Optional[str] = None,
        content_desc: Optional[str] = None,
        content_step: int = 0,
        **kwargs
    ) -> InterfaceCaseContentResult:
        """
        插入步骤内容结果

        根据 content_type 自动创建对应的子类实例，
        SQLAlchemy 会自动处理基类和子类记录的插入

        Args:
            content_type: 步骤类型
            case_result_id: 用例执行结果 ID
            task_result_id: 任务执行结果 ID
            content_id: 步骤内容 ID
            content_name: 步骤名称
            content_desc: 步骤描述
            content_step: 步骤序号
            **kwargs: 子类特有字段（如 interface_result_id, assert_data 等）

        Returns:
            InterfaceCaseContentResult: 创建的步骤内容结果实例

        示例:
            # 插入 API 步骤结果
            api_result = await InterfaceContentStepResultMapper.insert_result(
                content_type=CaseStepContentType.STEP_API,
                case_result_id=1,
                content_id=10,
                content_name="登录接口",
                content_step=1,
                interface_result_id=100
            )

            # 插入 Condition 步骤结果
            condition_result = await InterfaceContentStepResultMapper.insert_result(
                content_type=CaseStepContentType.STEP_API_CONDITION,
                case_result_id=1,
                content_id=20,
                content_name="条件判断",
                content_step=2,
                condition_result=True,
                assert_data={"expected": 200, "actual": 200}
            )
        """
        try:
            async with cls.transaction() as session:
                result_model = cls.RESULT_TYPE_MAP.get(content_type)
                if not result_model:
                    raise ValueError(f"不支持的 content_type: {content_type}")

                result = result_model(
                    case_result_id=case_result_id,
                    task_result_id=task_result_id,
                    content_id=content_id,
                    content_name=content_name,
                    content_desc=content_desc,
                    content_step=content_step,
                    content_type=content_type,
                    **kwargs
                )
                return await cls.add_flush_expunge(session=session, model=result)
        

        except Exception as e:
            log.error(f"insert_result {content_type} error: {e}")
            raise

    @classmethod
    async def update_result(
        cls,
        result_id: int,
        session: AsyncSession = None,
        **kwargs
    ) -> InterfaceCaseContentResult:
        """
        更新步骤内容结果

        自动识别目标实例的实际类型（基类或子类），
        从该类的表结构中获取有效列进行更新

        Args:
            result_id: 步骤内容结果 ID
            session: 可选的数据库会话
            **kwargs: 更新字段

        Returns:
            InterfaceCaseContentResult: 更新后的步骤内容结果实例
        """
        try:
            if session is None:
                async with cls.transaction() as session:
                    return await cls._do_update(session, result_id, **kwargs)
            else:
                return await cls._do_update(session, result_id, **kwargs)
        except Exception as e:
            log.error(f"update_result {result_id} error: {e}")
            raise

    @classmethod
    async def _do_update(
        cls,
        session: AsyncSession,
        result_id: int,
        **kwargs
    ) -> InterfaceCaseContentResult:
        """执行更新逻辑"""
        target = await cls.get_by_id(result_id, session)
        await session.refresh(target)

        base_columns = set(InterfaceCaseContentResult.__table__.columns.keys())
        child_columns = set(target.__class__.__table__.columns.keys())
        valid_columns = base_columns | child_columns
        update_fields = {k: v for k, v in kwargs.items() if k in valid_columns}

        for field, value in update_fields.items():
            setattr(target, field, value)

        await session.flush()
        session.expunge(target)

        return target

    @classmethod
    async def query_with_interface_results(
        cls,
        case_result_id: int,
        session: AsyncSession = None
    ) -> List[dict]:
        """
        查询步骤内容结果并包含关联的 interface_result 信息

        Args:
            case_result_id: 用例执行结果 ID
            session: 可选的数据库会话

        Returns:
            List[dict]: 包含完整结果信息的字典列表
        """
        results = await cls.query_by_case_result_id(case_result_id, session)
        result_dicts = [result.to_dict() for result in results]

        for result_dict in result_dicts:
            content_id = result_dict['id']
            content_type = result_dict['content_type']

            if content_type == CaseStepContentType.STEP_API:
                interface_results = await InterfaceResultMapper.get_by_content_result_id(content_id, session)
                if interface_results:
                    result_dict['interface_result'] = interface_results[0].to_dict()
            elif content_type in (
                CaseStepContentType.STEP_API_GROUP,
                CaseStepContentType.STEP_API_CONDITION,
                CaseStepContentType.STEP_LOOP,
            ):
                interface_results = await InterfaceResultMapper.get_by_content_result_id(content_id, session)
                result_dict['interface_results'] = [r.to_dict() for r in interface_results]

        return result_dicts

    @classmethod
    async def delete_by_case_result_id(
        cls,
        case_result_id: int,
        session: AsyncSession = None
    ) -> int:
        """
        删除指定用例执行结果的所有步骤内容结果

        Args:
            case_result_id: 用例执行结果 ID
            session: 可选的数据库会话

        Returns:
            int: 删除的记录数
        """
        from sqlalchemy import delete

        stmt = delete(InterfaceCaseContentResult).where(
            InterfaceCaseContentResult.case_result_id == case_result_id
        )

        if session:
            result = await session.execute(stmt)
            await session.flush()
            return result.rowcount
        else:
            async with cls.transaction() as session:
                result = await session.execute(stmt)
                return result.rowcount

    @classmethod
    async def get_statistics_by_case_result_id(
        cls,
        case_result_id: int,
        session: AsyncSession = None
    ) -> dict:
        """
        获取指定用例执行结果的统计信息

        Args:
            case_result_id: 用例执行结果 ID
            session: 可选的数据库会话

        Returns:
            dict: 统计信息
                {
                    "total": 10,
                    "success": 8,
                    "fail": 2,
                    "by_type": {
                        "API": {"total": 5, "success": 4, "fail": 1},
                        "GROUP": {"total": 2, "success": 2, "fail": 0},
                        ...
                    }
                }
        """
        results = await cls.query_by_case_result_id(case_result_id, session)

        stats = {
            "total": len(results),
            "success": sum(1 for r in results if r.result is True),
            "fail": sum(1 for r in results if r.result is False),
            "by_type": {}
        }

        for content_type in CaseStepContentType:
            type_results = [r for r in results if r.content_type == content_type]
            if type_results:
                stats["by_type"][content_type.name] = {
                    "total": len(type_results),
                    "success": sum(1 for r in type_results if r.result is True),
                    "fail": sum(1 for r in type_results if r.result is False),
                }

        return stats




    @classmethod
    async def query_steps_result(cls,case_result_id: int):

        stmt = select(InterfaceCaseContentResult).options(
            joinedload(APIStepContentResult.interface_result),
            joinedload(GroupStepContentResult.interface_results),
            joinedload(ConditionStepContentResult.interface_results),
        ).where(
            InterfaceCaseContentResult.case_result_id == case_result_id
        ).order_by(
            InterfaceCaseContentResult.content_step
        )
        async with async_session() as s:
            result = await s.scalars(stmt)
            steps = result.unique().all()
        return steps

    @classmethod
    async def bulk_insert_results(
        cls,
        items: List[Dict],
        session: AsyncSession = None
    ) -> int:
        """
        批量插入步骤内容结果（支持多态）

        设计说明：
        - 由于 InterfaceCaseContentResult 使用 Joined Table Inheritance
        - 不同子类映射到不同的表（基类表 + 子类表）
        - 需要按 content_type 分组后，使用对应的子类模型批量插入
        - SQLAlchemy 会自动处理基类表和子类表的插入

        Args:
            items: 数据字典列表，每个字典必须包含 content_type 字段
            session: 可选的数据库会话

        Returns:
            int: 插入的记录数
        """
        if not items:
            return 0

        from collections import defaultdict
        grouped_items: Dict[CaseStepContentType, List[Dict]] = defaultdict(list)

        for item in items:
            content_type = item.get('content_type')
            if content_type is None:
                log.error(f"bulk_insert_results: 缺少 content_type 字段: {item}")
                continue
            grouped_items[content_type].append(item)

        total_inserted = 0

        try:
            if session:
                for content_type, type_items in grouped_items.items():
                    result_model = cls.RESULT_TYPE_MAP.get(content_type)
                    if not result_model:
                        log.error(f"bulk_insert_results: 不支持的 content_type: {content_type}")
                        continue

                    models = [result_model(**item) for item in type_items]
                    session.add_all(models)
                    total_inserted += len(models)

                await session.flush()
                return total_inserted
            else:
                async with cls.transaction() as session:
                    for content_type, type_items in grouped_items.items():
                        result_model = cls.RESULT_TYPE_MAP.get(content_type)
                        if not result_model:
                            log.error(f"bulk_insert_results: 不支持的 content_type: {content_type}")
                            continue

                        models = [result_model(**item) for item in type_items]
                        session.add_all(models)
                        total_inserted += len(models)

                    return total_inserted
        except Exception as e:
            log.error(f"bulk_insert_results error: {e}")
            raise

__all__ = ["InterfaceCaseResultMapper",
           "InterfaceResultMapper",
           "InterfaceTaskResultMapper",
           "InterfaceContentStepResultMapper"
           ]