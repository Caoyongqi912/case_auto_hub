#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : testCaseStepMapper
# @Software: PyCharm
# @Desc: 测试用例步骤数据访问层
from typing import List, Dict, Any, Sequence

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.caseHub.caseHUB import TestCaseStep
from utils import log


class TestCaseStepMapper(Mapper[TestCaseStep]):
    __model__ = TestCaseStep

    @classmethod
    async def update_step(cls, user: User, id: int, **kwargs):
        """
        更新用例步骤，并记录变更动态

        :param user: 操作用户
        :param id: 步骤ID
        :param kwargs: 更新字段
        """
        from app.mapper.caseHub.caseDynamicMapper import CaseDynamicMapper

        log.info(f"更新步骤 {id}")
        log.debug(f"更新参数 {kwargs}")

        try:
            async with async_session() as session:
                async with session.begin():
                    step = await cls.get_by_id(ident=id, session=session)
                    before_info = {
                        "action": step.action,
                        "expected_result": step.expected_result
                    }

                    new_step = await cls.update_cls(step, session, **kwargs)
                    after_info = {
                        "action": new_step.action,
                        "expected_result": new_step.expected_result
                    }

                    await CaseDynamicMapper.update_dynamic(
                        cr=user,
                        case_id=new_step.test_case_id,
                        old_case=before_info,
                        new_case=after_info,
                        session=session
                    )
        except Exception as e:
            log.error(f"update_step error: id={id}, error={e}")
            raise

    @classmethod
    async def reorder_steps(cls, step_ids: List[int]):
        """
        批量重排序用例步骤

        :param step_ids: 步骤ID列表（新的排序顺序）
        """
        from sqlalchemy import case

        try:
            async with async_session() as session:
                async with session.begin():
                    case_stmt = case(
                        *[(TestCaseStep.id == step_id, index) for index, step_id in enumerate(step_ids, start=1)],
                        else_=0
                    )
                    await session.execute(
                        update(TestCaseStep)
                        .where(TestCaseStep.id.in_(step_ids))
                        .values(order=case_stmt)
                    )
        except Exception as e:
            log.error(f"reorder_steps error: step_ids={step_ids}, error={e}")
            raise

    @classmethod
    async def copy_step(cls, step_id: int, user: User):
        """
        复制指定步骤

        :param step_id: 被复制的步骤ID
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    step: TestCaseStep = await cls.get_by_id(ident=step_id, session=session)

                    await session.execute(
                        update(TestCaseStep)
                        .where(
                            and_(
                                TestCaseStep.test_case_id == step.test_case_id,
                                TestCaseStep.order > step.order
                            )
                        )
                        .values(order=TestCaseStep.order + 1)
                    )

                    new_step_data = step.copy_map()
                    new_step_data["creator"] = user.id
                    new_step_data["creatorName"] = user.username
                    new_step_data["order"] = step.order + 1

                    await cls.save(session=session, **new_step_data)
        except Exception as e:
            log.error(f"copy_step error: step_id={step_id}, error={e}")
            raise

    @classmethod
    async def add_default_step(cls, caseId: int, user: User):
        """
        为用例添加一条默认空步骤

        :param caseId: 用例ID
        :param user: 操作用户
        """
        try:
            async with async_session() as session:
                last_order = await cls.get_last_order(case_id=caseId, session=session)

                session.add(
                    cls.__model__(
                        test_case_id=caseId,
                        order=last_order + 1,
                        creator=user.id,
                        creatorName=user.username
                    )
                )
                await session.commit()
        except Exception as e:
            log.error(f"add_default_step error: caseId={caseId}, error={e}")
            raise

    @classmethod
    async def save_steps(cls, case_id: int, steps: List[Dict[str, Any]], session: AsyncSession, user: User):
        """
        批量保存用例步骤

        :param case_id: 用例ID
        :param steps: 步骤数据列表
        :param session: 数据库会话
        :param user: 操作用户
        """
        if not steps:
            return

        try:
            step_objects = []
            for index, step_data in enumerate(steps):
                step_data["test_case_id"] = case_id
                step_data["order"] = index
                step_data["creator"] = user.id
                step_data["creatorName"] = user.username
                step_objects.append(cls.__model__(**step_data))

            session.add_all(step_objects)
            await session.flush()
        except Exception as e:
            log.error(f"save_steps error: case_id={case_id}, error={e}")
            raise

    @classmethod
    async def query_sub_steps(cls, case_id: int, session: AsyncSession = None) -> Sequence[TestCaseStep]:
        """
        查询用例的所有步骤

        :param case_id: 用例ID
        :param session: 可选的数据库会话
        :return: 步骤列表
        """
        try:
            if session:
                return await cls._query_steps(session, case_id)
            async with async_session() as sess:
                return await cls._query_steps(sess, case_id)
        except Exception as e:
            log.error(f"query_sub_steps error: case_id={case_id}, error={e}")
            raise

    @staticmethod
    async def _query_steps(session: AsyncSession, case_id: int) -> Sequence[TestCaseStep]:
        """内部方法：查询步骤"""
        steps = await session.scalars(
            select(TestCaseStep)
            .where(TestCaseStep.test_case_id == case_id)
            .order_by(TestCaseStep.order)
        )
        return steps.all()

    @staticmethod
    async def get_last_order(case_id: int, session: AsyncSession) -> int:
        """
        获取用例的最大步骤排序号

        :param case_id: 用例ID
        :param session: 数据库会话
        :return: 最大排序号，不存在则返回0
        """
        stmt = (
            select(TestCaseStep.order)
            .where(TestCaseStep.test_case_id == case_id)
            .order_by(TestCaseStep.order.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar() or 0
