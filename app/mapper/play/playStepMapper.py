#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/2
# @Author : cyq
# @File : playStepMapper
# @Software: PyCharm
# @Desc:
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.playUI import   PlayStepModel
from enums.CaseEnum import PlayStepContentType
from utils import MyLoguru
log = MyLoguru().get_logger()


class PlayStepV2Mapper(Mapper[PlayStepModel]):
    __model__ = PlayStepModel

    @classmethod
    async def copy_step(cls, step_id: int, user: User, copy_step_name: bool = False, is_common: bool = False,
                        session: AsyncSession = None) -> PlayStepModel:
        """
                步骤复制

        :param step_id:目标步骤ID
        :param user:User 创建人
        :param copy_step_name: 是否完全复制步骤名 否则 + （副本）
        :param is_common:是否复制成公共
        :param session:上下文
        :return PlayStep
        """

        # 使用传入的session或创建新的
        should_close = False
        if session is None:
            session = async_session()
            should_close = True

        try:
            # 查询步骤
            step = await cls.get_by_id(ident=step_id, session=session)

            new_step = step.copy_map()
            if not copy_step_name:
                new_step['name'] = f"{new_step['name']} (副本)"
            new_step.update({
                'is_common': is_common,
                'creator': user.id,
                'creatorName': user.username
            })
            result = await cls.save(**new_step, session=session)
            # 如果是临时session，需要提交
            if should_close:
                await session.commit()

            return result
        except Exception as e:
            # 发生异常时回滚
            if should_close and session:
                await session.rollback()
            raise e
        finally:
            if should_close and session:
                await session.close()

    @classmethod
    async def update_step(cls, id: int, **kwargs):
        """
        更新步骤
        :param id: 步骤ID
        :param kwargs: 更新参数
        :return: 更新后的步骤对象
        """

        from app.model.playUI.playStepContent import PlayStepContent
        from sqlalchemy import update

        try:
            async with async_session() as session:
                async with session.begin():
                    # 1. 更新 PlayStepModel
                    step = await cls.update_by_id(
                        session=session,
                        ident=id,
                        **kwargs
                    )

                    # 2. 批量更新关联的 PlayStepContent
                    # 只有当 name 或 method 被修改时才同步
                    if 'name' in kwargs or 'method' in kwargs:
                        stmt = update(PlayStepContent).where(
                            and_(
                                PlayStepContent.target_id == id,
                                PlayStepContent.content_type == PlayStepContentType.STEP_PLAY
                            )
                        ).values(
                            content_name=kwargs.get('name', step.name),
                            content_desc=kwargs.get('method', step.method)
                        )
                        await session.execute(stmt)

        except Exception as e:
            log.exception(e)
            raise e

    @classmethod
    async def get_by_ids(cls, play_step_id_list: List[int], session: AsyncSession) -> List[PlayStepModel]:
        """
        查询多个步骤
        
        Args:
            play_step_id_list: 步骤ID列表
            session: 数据库会话对象
            
        Returns:
            List[PlayStepModel]: 步骤对象列表，顺序与传入的ID列表一致
        """
        try:
            if not play_step_id_list:
                return []

            result = await session.execute(
                select(cls.__model__).where(cls.__model__.id.in_(play_step_id_list))
            )
            steps = result.scalars().all()

            # 创建ID到步骤对象的映射
            step_map = {step.id: step for step in steps}

            # 按照传入的ID列表顺序构建结果
            ordered_steps = []
            for step_id in play_step_id_list:
                if step_id in step_map:
                    ordered_steps.append(step_map[step_id])

            return ordered_steps
        except Exception as e:
            log.exception(e)
            raise e
