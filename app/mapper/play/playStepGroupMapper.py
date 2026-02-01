from typing import List

from sqlalchemy import select, insert, delete, and_, update, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.playUI.playAssociation import PlayGroupStepAssociation
from app.model.playUI.playStepContent import PlayStepGroup
from app.model.playUI.playStep import PlayStepModel
from app.mapper.play.playStepMapper import PlayStepV2Mapper


class LastIndexHelper:
    """索引查询辅助类
    
    提供获取用例步骤最后索引的功能，用于确保新添加的步骤能够正确排序
    """

    @staticmethod
    async def get_group_step_last_index(group_id: int, session: AsyncSession) -> int:
        """
        获取用例步骤的最后索引
        
        Args:
            group_id: 用例组ID
            session: 数据库会话对象
            
        Returns:
            int: 最后索引值，如果没有步骤则返回0
        """
        stmt = select(PlayGroupStepAssociation.step_order).where(
            PlayGroupStepAssociation.group_id == group_id
        ).order_by(
            PlayGroupStepAssociation.step_order.desc()
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar() or 0


class AssociationHelper:
    """关联关系辅助类
    
    提供创建用例组与步骤之间关联关系的功能
    """

    @staticmethod
    async def create_steps_group_association(
            session: AsyncSession,
            group_id: int,
            step_list: List[int],
            start_index: int
    ) -> None:
        """
        批量创建用例组与步骤的关联关系
        
        Args:
            session: 数据库会话对象
            group_id: 用例组ID
            step_list: 步骤ID列表
            start_index: 起始索引，新步骤将从该索引后开始排序
            
        Notes:
            使用IGNORE前缀避免重复关联导致的错误
        """
        values = [{
            "group_id": group_id,
            "play_step_id": step_id,
            "step_order": index
        } for index, step_id in enumerate(step_list, start=start_index + 1)]

        if values:
            await session.execute(
                insert(PlayGroupStepAssociation).prefix_with('IGNORE').values(values)
            )

    @staticmethod
    async def create_single_group_association(
            session: AsyncSession,
            group_id: int,
            play_step_id: int,
            step_order: int
    ):
        """
        创建单个用例组与步骤的关联关系
        
        Args:
            session: 数据库会话对象
            group_id: 用例组ID
            play_step_id: 步骤ID
            step_order: 步骤顺序
            
        Notes:
            使用IGNORE前缀避免重复关联导致的错误
        """
        await session.execute(
            insert(PlayGroupStepAssociation).prefix_with('IGNORE').values({
                "group_id": group_id,
                "play_step_id": play_step_id,
                "step_order": step_order
            })
        )

    @staticmethod
    async def get_last_step_index(session: AsyncSession, group_id: int) -> int:
        """
        获取用例组的最后步骤索引
        
        Args:
            session: 数据库会话对象
            group_id: 用例组ID
            
        Returns:
            int: 最后索引值，如果没有步骤则返回0
        """
        stmt = select(PlayGroupStepAssociation.step_order).where(
            PlayGroupStepAssociation.group_id == group_id
        ).order_by(
            PlayGroupStepAssociation.step_order.desc()
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar() or 0


class PlayStepGroupMapper(Mapper[PlayStepGroup]):
    __model__ = PlayStepGroup

    @classmethod
    async def association_steps(cls, group_id: int, quote: bool, play_step_id_list: List[int], user: User) -> None:
        """
        关联公共步骤到用例组
        
        Args:
            group_id: 用例组ID
            quote: 是否直接引用步骤（True为引用，False为复制）
            play_step_id_list: 公共步骤ID列表
            user: 当前操作用户
            
        Notes:
            - 当quote为False时，会复制步骤并创建新的非公共步骤
            - 自动更新用例组的步骤数量
            - 使用事务确保操作的原子性
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    # 获取用例组并更新步骤数量
                    group = await cls.get_by_id(ident=group_id, session=session)
                    group.step_num += len(play_step_id_list)

                    # 获取当前最后步骤索引
                    last_index = await AssociationHelper.get_last_step_index(session, group_id)

                    step_list = []
                    # 复制步骤（非引用模式）
                    if not quote:
                        for step_id in play_step_id_list:
                            step = await PlayStepV2Mapper.copy_step(
                                step_id=step_id,
                                session=session,
                                user=user,
                                copy_step_name=True,
                                is_common=False,
                            )
                            step_list.append(step.id)

                    # 如果是引用模式，直接使用原步骤ID列表
                    step_list = step_list or play_step_id_list

                    # 批量创建关联关系
                    values = [{
                        "group_id": group_id,
                        "play_step_id": step_id,
                        "step_order": index
                    } for index, step_id in enumerate(step_list, start=last_index + 1)]

                    if values:
                        await session.execute(
                            insert(PlayGroupStepAssociation).prefix_with('IGNORE').values(values)
                        )
        except Exception as e:
            # 保留原始异常信息并重新抛出
            raise

    @classmethod
    async def query_steps_by_group_id(cls, group_id: int) -> list[PlayStepModel]:
        """
        查询指定用例组下的所有步骤
        
        Args:
            group_id: 用例组ID
            
        Returns:
            list[PlayStepModel]: 步骤列表，按步骤顺序排序
            
        Notes:
            - 通过关联表查询用例组下的所有步骤
            - 结果按步骤顺序排序
        """
        try:
            async with async_session() as session:
                stmt = select(PlayStepModel).join(
                    PlayGroupStepAssociation,
                    PlayGroupStepAssociation.play_step_id == PlayStepModel.id
                ).where(
                    PlayGroupStepAssociation.group_id == group_id
                ).order_by(
                    PlayGroupStepAssociation.step_order
                )

                result = await session.scalars(stmt)
                return result.all()

        except Exception as e:
            raise e

    @classmethod
    async def insert_play_step(cls, group_id: int, user: User, **kwargs) -> None:
        """
        插入私有步骤到用例组
        
        Args:
            group_id: 用例组ID
            user: 当前操作用户
            **kwargs: 步骤相关参数
            
        Notes:
            - 自动更新用例组的步骤数量
            - 为新步骤分配正确的顺序索引
            - 使用事务确保操作的原子性
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    # 获取用例组并更新步骤数量
                    group = await cls.get_by_id(ident=group_id, session=session)
                    group.step_num += 1

                    # 创建新步骤
                    play_step = await PlayStepV2Mapper.save(
                        creator_user=user,
                        session=session,
                        **kwargs
                    )

                    # 获取当前最后步骤索引并计算新步骤的顺序
                    last_index = await AssociationHelper.get_last_step_index(session, group_id)

                    # 创建关联关系
                    await session.execute(
                        insert(PlayGroupStepAssociation).prefix_with('IGNORE').values({
                            "group_id": group_id,
                            "play_step_id": play_step.id,
                            "step_order": last_index + 1
                        })
                    )

        except Exception:
            raise

    @classmethod
    async def copy_step(cls, group_id: int, step_id: int, user: User) -> None:
        """
        复制步骤到用例组
        
        Args:
            group_id: 用例组ID
            step_id: 要复制的步骤ID
            user: 当前操作用户
            
        Notes:
            - 自动更新用例组的步骤数量
            - 复制后的步骤为非公共步骤
            - 为新步骤分配正确的顺序索引
            - 使用事务确保操作的原子性
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    # 获取用例组并更新步骤数量
                    group = await cls.get_by_id(ident=group_id, session=session)
                    group.step_num += 1

                    # 复制步骤
                    step = await PlayStepV2Mapper.copy_step(
                        step_id=step_id,
                        session=session,
                        user=user,
                        is_common=False,
                    )

                    # 获取当前最后步骤索引并计算新步骤的顺序
                    last_index = await AssociationHelper.get_last_step_index(session, group_id)

                    # 创建关联关系
                    await session.execute(
                        insert(PlayGroupStepAssociation).prefix_with('IGNORE').values({
                            "group_id": group_id,
                            "play_step_id": step.id,
                            "step_order": last_index + 1
                        })
                    )

        except Exception as e:
            raise e

    @classmethod
    async def reorder_step(cls, step_list: List[int], group_id: int) -> None:
        """
        重新排序用例组中的步骤
        
        Args:
            step_list: 步骤ID列表，按期望的顺序排列
            group_id: 用例组ID
            
        Notes:
            - 使用SQL的CASE语句批量更新步骤顺序
            - 只更新指定列表中的步骤顺序
            - 一次数据库操作完成所有排序更新，提高性能
        """

        try:
            async with async_session() as session:
                # 构建步骤ID到新顺序的映射
                whens = {step_id: index for index, step_id in enumerate(step_list, start=1)}

                # 使用CASE语句批量更新步骤顺序
                await session.execute(update(PlayGroupStepAssociation)
                .where(
                    and_(
                        PlayGroupStepAssociation.play_step_id.in_(step_list),
                        PlayGroupStepAssociation.group_id == group_id
                    )
                )
                .values(
                    step_order=case(whens, value=PlayGroupStepAssociation.play_step_id)
                ))

        except Exception as e:
            raise e

    @classmethod
    async def remove_step(cls, group_id: int, step_id: int) -> None:
        """
        从用例组中移除步骤
        
        Args:
            group_id: 用例组ID
            step_id: 要移除的步骤ID
            
        Notes:
            - 自动更新用例组的步骤数量
            - 移除用例组与步骤的关联关系
            - 对于非公共步骤，会同时删除步骤本身
            - 使用事务确保操作的原子性
        """

        try:
            async with async_session() as session:
                async with session.begin():
                    # 获取用例组并更新步骤数量
                    group = await cls.get_by_id(ident=group_id, session=session)
                    if group.step_num > 0:
                        group.step_num -= 1

                    # 获取步骤信息
                    step = await PlayStepV2Mapper.get_by_id(ident=step_id, session=session)

                    # 移除关联关系
                    await session.execute(
                        delete(PlayGroupStepAssociation).where(
                            and_(
                                PlayGroupStepAssociation.play_step_id == step_id,
                                PlayGroupStepAssociation.group_id == group_id,
                            )
                        )
                    )

                    # 非公共步骤直接删除
                    if not step.is_common:
                        await session.delete(step)

        except Exception as e:
            raise e

    @classmethod
    async def query_by_id(cls, group_id_list: List[int], session: AsyncSession):
        """

        :param group_id_list:
        :param session:
        :return:
        """

        result = await session.execute(
            select(cls.__model__).where(cls.__model__.id.in_(group_id_list))
        )
        steps = result.scalars().all()

        # 创建ID到步骤对象的映射
        step_map = {step.id: step for step in steps}

        # 按照传入的ID列表顺序构建结果
        ordered_steps = []
        for step_id in group_id_list:
            if step_id in step_map:
                ordered_steps.append(step_map[step_id])

        return ordered_steps

    @classmethod
    async def copy_group(cls, group_id: int, user: User):
        """
        复制组
        :param group_id:
        :param user:
        :param session:
        :return:
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    return await cls.copy_group2(group_id, user, session)
        except Exception as e:
            raise e

    @classmethod
    async def copy_group2(cls, group_id: int, user: User, session: AsyncSession) -> PlayStepGroup:
        """
        复制组
        :param group_id:
        :param user:
        :param session:
        :return:
        """

        try:

            origin_group = await cls.get_by_id(ident=group_id, session=session)
            origin_group_map = origin_group.copy_map()
            group = await cls.add_flush_expunge(
                model=PlayStepGroup(
                    **origin_group_map,
                    creator=user.id,
                    creatorName=user.creatorName
                ),
                session=session
            )

            stmt = select(PlayStepModel).join(
                PlayGroupStepAssociation,
                PlayGroupStepAssociation.play_step_id == PlayStepModel.id
            ).where(
                PlayGroupStepAssociation.group_id == group_id
            ).order_by(
                PlayGroupStepAssociation.step_order
            )

            origin_steps = await session.scalars(stmt)
            new_step_id_list = []
            for origin_step in origin_steps:
                if origin_step.is_common:
                    new_step_id_list.append(origin_step.id)
                else:
                    new_step = await PlayStepV2Mapper.copy_step(
                        step_id=origin_step.id,
                        user=user,
                        session=session,
                        is_common=False,
                        copy_step_name=True
                    )
                    new_step_id_list.append(new_step.id)
            await AssociationHelper.create_steps_group_association(
                step_list=new_step_id_list,
                group_id=group.id,
                session=session,
                start_index=1)

            return group
        except Exception as e:

            raise e

    @classmethod
    async def remove_group(cls, group_id: int):
        """
        删除
        :param group_id:
        :return:
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    group = await cls.get_by_id(ident=group_id, session=session)

                    stmt = delete(PlayGroupStepAssociation
                                  ).where(
                        PlayGroupStepAssociation.group_id == group_id
                    )
                    await session.execute(stmt)

                    stmt = select(PlayStepModel).join(
                        PlayGroupStepAssociation,
                        PlayGroupStepAssociation.play_step_id == PlayStepModel.id
                    ).where(
                        PlayGroupStepAssociation.group_id == group_id
                    ).order_by(
                        PlayGroupStepAssociation.step_order
                    )

                    steps = await session.scalars(stmt)
                    for step in steps:
                        if not step.is_common:
                            await session.delete(step)
                    await session.delete(group)
        except Exception as e:
            raise e
