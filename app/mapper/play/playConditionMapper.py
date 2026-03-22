#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/3/20
# @Author : cyq
# @File : playConditionMapper
# @Software: PyCharm
# @Desc:
from typing import List

from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.playUI.playCondition import PlayCondition
from app.model.playUI.playAssociation import ConditionStepAssociation
from app.model.playUI.playStepContent import PlayStepContent


class PlayConditionMapper(Mapper[PlayCondition]):
    """UI条件判断Mapper"""
    __model__ = PlayCondition


    @classmethod
    async def init_empty(cls,user:User,session:AsyncSession):
        """
        初始化空的条件判断
        :param user: 用户
        :param session: 会话对象
        :return: 条件判断实例
        """
        return await cls.save(creator_user=user, session=session)

    @classmethod
    async def get_condition_step_contents(cls, condition_id: int) -> List[PlayStepContent]:
        """
        获取条件关联的子步骤内容列表
        :param condition_id: 条件ID
        :return: 步骤内容列表
        """
        async with async_session() as session:
            stmt = select(PlayStepContent).join(
                ConditionStepAssociation,
                ConditionStepAssociation.step_content_id == PlayStepContent.id
            ).where(
                ConditionStepAssociation.condition_id == condition_id
            ).order_by(
                ConditionStepAssociation.step_order
            )

            result = await session.scalars(stmt)
            return result.all()

    @classmethod
    async def add_step_content_to_condition(
        cls,
        session: AsyncSession,
        condition_id: int,
        step_content_id: int,
        step_order: int = None
    ) -> ConditionStepAssociation:
        """
        为条件添加子步骤内容
        :param session: 会话对象
        :param condition_id: 条件ID
        :param step_content_id: 步骤内容ID
        :param step_order: 执行顺序
        :return: 关联实例
        """
        if step_order is None:
            last_order = await cls._get_last_step_order(condition_id, session)
            step_order = last_order + 1

        association = ConditionStepAssociation(
            condition_id=condition_id,
            step_content_id=step_content_id,
            step_order=step_order
        )
        session.add(association)
        await session.flush()
        await session.refresh(association)
        return association

    @classmethod
    async def _get_last_step_order(cls, condition_id: int, session: AsyncSession) -> int:
        """获取最后步骤顺序"""
        stmt = select(ConditionStepAssociation.step_order).where(
            ConditionStepAssociation.condition_id == condition_id
        ).order_by(ConditionStepAssociation.step_order.desc()).limit(1)

        result = await session.execute(stmt)
        return result.scalar() or 0
