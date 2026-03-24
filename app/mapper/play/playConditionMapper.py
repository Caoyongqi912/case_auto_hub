#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/3/20
# @Author : cyq
# @File : playConditionMapper
# @Software: PyCharm
# @Desc:
import asyncio
from operator import and_
from typing import List

from sqlalchemy import select, insert, delete, update, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.playUI.playCondition import PlayCondition
from app.model.playUI.playAssociation import ConditionStepAssociation
from app.model.playUI.playStepContent import PlayStepContent
from enums.CaseEnum import PlayStepContentType
from utils import log


class PlayConditionMapper(Mapper[PlayCondition]):
    """UI条件判断Mapper"""
    __model__ = PlayCondition

    @classmethod
    async def reorder_content(cls, condition_id: int, content_child_list_id: List[int]):
        try:
            async with async_session() as session:
                async with session.begin():
                    condition = await cls.get_by_id(ident=condition_id, session=session)

                    existing_associations = await session.execute(
                        select(ConditionStepAssociation.step_content_id).where(
                            and_(
                                ConditionStepAssociation.condition_id == condition_id,
                                ConditionStepAssociation.step_content_id.in_(content_child_list_id)
                            )
                        )
                    )
                    existing_ids = {ident[0] for ident in existing_associations.all()}

                    if len(existing_ids) != len(content_child_list_id):
                        invalid_ids = set(content_child_list_id) - existing_ids
                        log.warning(f"以下步骤内容ID不属于 条件 {condition_id}: {invalid_ids}")
                    # 创建CASE语句的条件映射
                    whens = {step_id: index for index, step_id in enumerate(content_child_list_id, start=1)}
                    result = await session.execute(
                        update(ConditionStepAssociation)
                        .where(
                            and_(
                                ConditionStepAssociation.step_content_id.in_(content_child_list_id),
                                ConditionStepAssociation.condition_id == condition_id
                            )
                        )
                        .values(
                            step_order=case(whens, value=ConditionStepAssociation.step_content_id)
                        )
                    )


        except Exception:
            raise

    @classmethod
    async def remove_content(cls, condition_id: int, content_id: int):
        """
        移除条件关联的步骤内容
        :param condition_id: 条件ID
        :param content_id: 步骤内容ID
        Notes:
            - 自动更新条件的子步骤数量
            - 移除条件与步骤内容的关联关系
            - 对于非公共步骤内容，会同时删除步骤本身
            - 使用事务确保操作的原子性
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    condition = await cls.get_by_id(ident=condition_id, session=session)
                    step_content = await session.get(PlayStepContent, content_id)

                    if not condition or not step_content:
                        return

                    await session.execute(
                        delete(ConditionStepAssociation).where(
                            and_(
                                ConditionStepAssociation.condition_id == condition.id,
                                ConditionStepAssociation.step_content_id == step_content.id
                            )
                        )
                    )

                    if condition.condition_step_num > 0:
                        condition.condition_step_num -= 1

                    if not step_content.is_common:
                        await session.delete(step_content)

        except Exception as e:
            raise e

    @classmethod
    async def init_empty(cls, user: User, session: AsyncSession):
        """
        初始化空的条件判断
        :param user: 用户
        :param session: 会话对象
        :return: 条件判断实例
        """
        return await cls.save(creator_user=user, session=session)

    @classmethod
    async def insert_content_step(cls, case_id: int, content_id: int, user: User, **kwargs):
        """
        插入私有content step 2 condition content
        """
        async with async_session() as session:
            async with session.begin():
                from app.mapper.play import PlayStepContentMapper, PlayStepV2Mapper

                content = await PlayStepContentMapper.get_by_id(ident=content_id, session=session)
                condition = await cls.get_by_id(ident=content.target_id, session=session)

                play_step = await PlayStepV2Mapper.save(
                    creator_user=user,
                    session=session,
                    **kwargs
                )
                play_step_content = await PlayStepContentMapper.init_content(
                    target_id=play_step.id,
                    is_common=False,
                    content_type=PlayStepContentType.STEP_PLAY,
                    session=session,
                    content_desc=play_step.method,
                    content_name=play_step.name
                )

                last_order = await cls._get_last_step_order(condition_id=condition.id, session=session)
                step_order = last_order + 1
                condition.condition_step_num += 1

                stmt = insert(ConditionStepAssociation).values(
                    {
                        "condition_id": condition.id,
                        "step_content_id": play_step_content.id,
                        "step_order": step_order
                    }
                )
                await session.execute(stmt)


    @classmethod
    async def choice_common_steps(cls,condition_id:int,quote:bool,play_step_id_list:List[int],user: User):
        """

        """
        from app.mapper.play import PlayStepV2Mapper,PlayStepContentMapper

        try:
            async with async_session() as session:
                async with session.begin():
                    condition = await cls.get_by_id(ident=condition_id, session=session)
                    condition.condition_step_num += len(play_step_id_list)
                    case_step_content_play_step_list = []
                    if quote:
                        steps = await PlayStepV2Mapper.get_by_ids(play_step_id_list, session)
                        if not steps:
                            log.warning(f"未找到ID为{play_step_id_list}的步骤")
                            return
                        step_map = {step.id: step for step in steps}
                        for play_step_id in play_step_id_list:
                            step = step_map.get(play_step_id)
                            if step:
                                content = await PlayStepContentMapper.init_content(
                                    target_id=play_step_id,
                                    content_type=PlayStepContentType.STEP_PLAY,
                                    session=session,
                                    is_common=True,
                                    content_desc=step.method,
                                    content_name=step.name
                                )
                                case_step_content_play_step_list.append(content)
                    else:
                        # 使用异步并发处理，提高复制步骤的效率
                        copy_jobs = []
                        for play_step_id in play_step_id_list:
                            copy_jobs.append(
                                PlayStepV2Mapper.copy_step(
                                    step_id=play_step_id,
                                    session=session,
                                    copy_step_name=True,
                                    is_common=False,
                                    user=user
                                )
                            )

                        try:
                            copied_steps = await asyncio.gather(*copy_jobs)
                        except Exception as gather_err:
                            log.exception(f"复制步骤时出现错误: {gather_err}")
                            raise ValueError("复制步骤失败")

                        for step in copied_steps:
                            content = await PlayStepContentMapper.init_content(
                                target_id=step.id,
                                content_type=PlayStepContentType.STEP_PLAY,
                                session=session,
                                content_desc=step.method,
                                content_name=step.name,
                                is_common=False
                            )
                            case_step_content_play_step_list.append(content)
                    last_index = await cls._get_last_step_order(condition_id, session)
                    content_ids = [content.id for content in case_step_content_play_step_list]

                    if content_ids:
                        values = []
                        for index, content_id in enumerate(content_ids, start=last_index + 1):
                            values.append({
                                "condition_id": condition_id,
                                "step_content_id": content_id,
                                "step_order": index
                            })

                        if values:
                            await session.execute(
                                insert(ConditionStepAssociation).prefix_with('IGNORE').values(values)
                            )
                    else:
                        log.warning(f"没有创建任何步骤关联，用例ID: {condition_id}")
                        # 回滚步骤数量更新
                        condition.condition_step_num -= len(play_step_id_list)


        except Exception:
            raise
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
    async def _get_last_step_order(cls, condition_id: int, session: AsyncSession) -> int:
        """获取最后步骤顺序"""
        stmt = select(ConditionStepAssociation.step_order).where(
            ConditionStepAssociation.condition_id == condition_id
        ).order_by(ConditionStepAssociation.step_order.desc()).limit(1)

        result = await session.execute(stmt)
        return result.scalar() or 0
