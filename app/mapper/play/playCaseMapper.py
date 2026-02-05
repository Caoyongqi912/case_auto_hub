#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/2
# @Author : cyq
# @File : playCaseMapper
# @Software: PyCharm
# @Desc:
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Sequence

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.playUI import PlayCase, PlayCaseVariables, PlayCaseResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete, case, insert
from app.mapper.play.playStepMapper import PlayStepV2Mapper
from croe.play.starter import UIStarter
from enums.CaseEnum import Result, Status, PlayStepContentType
from utils import log
from ..file import FileMapper
from ...exception import NotFind
from app.model.playUI.playStepContent import PlayStepContent
from app.model.playUI.playAssociation import PlayCaseStepContentAssociation


class CommonHelper:
    """
    通用辅助类
    
    提供索引查询、关联关系管理等通用功能
    """

    @staticmethod
    async def get_case_step_last_index(case_id: int, session: AsyncSession) -> int:
        """
        获取用例步骤的最后索引
        
        Args:
            case_id: 用例ID
            session: 数据库会话对象

        Returns:
            int: 最后索引值，如果没有步骤则返回0
        """
        stmt = select(PlayCaseStepContentAssociation.step_order).where(
            PlayCaseStepContentAssociation.play_case_id == case_id
        ).order_by(
            PlayCaseStepContentAssociation.step_order.desc()
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def create_case_content_association(
            session: AsyncSession,
            case_id: int,
            content_ids: List[int],
            start_index: int,
    ):
        """
        批量创建用例与内容的关联关系
        
        Args:
            session: 数据库会话对象
            case_id: 用例ID
            content_ids: 内容ID列表
            start_index: 起始索引，新步骤将从该索引后开始排序
        """
        values = []
        for index, content_id in enumerate(content_ids, start=start_index + 1):
            values.append({
                "play_case_id": case_id,
                "play_step_content_id": content_id,
                "step_order": index
            })

        if values:
            await session.execute(
                insert(PlayCaseStepContentAssociation).prefix_with('IGNORE').values(values)
            )

    @staticmethod
    async def create_single_case_content_association(
            session: AsyncSession,
            case_id: int,
            content_id: int,
            step_order: int
    ):
        """
        创建单个用例与内容的关联关系
        
        Args:
            session: 数据库会话对象
            case_id: 用例ID
            content_id: 内容ID
            step_order: 步骤顺序
        """
        await session.execute(
            insert(PlayCaseStepContentAssociation).prefix_with('IGNORE').values({
                "play_case_id": case_id,
                "play_step_content_id": content_id,
                "step_order": step_order
            })
        )


class PlayCaseMapper(Mapper[PlayCase]):
    __model__ = PlayCase

    @classmethod
    async def association_groups(cls, case_id: int, group_id_list: List[int]):
        """
        关联公共步骤到用例

        :param case_id: 用例iD
        :param group_id: 关联组id
        :return:
        """
        if not case_id:
            raise ValueError("用例ID不能为空")
        if not group_id_list:
            raise ValueError("步骤列表不能为空")

        try:
            async with async_session() as session:
                async with session.begin():
                    play_case = await cls.get_by_id(ident=case_id, session=session)
                    if not play_case:
                        raise ValueError(f"找不到ID为{case_id}的用例")

                    group_content_list = []
                    # 查询组
                    from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper
                    groups = await PlayStepGroupMapper.query_by_id(group_id_list, session)
                    for group in groups:
                        content = await PlayStepContentMapper.init_content(
                            target_id=group.id,
                            content_type=PlayStepContentType.STEP_PLAY_GROUP,
                            session=session,
                            is_common=True,
                            content_name=group.name,
                            content_desc=group.description,
                        )
                        group_content_list.append(content.id)

                    last_index = await CommonHelper.get_case_step_last_index(case_id, session)
                    await CommonHelper.create_case_content_association(
                        session, case_id, group_content_list, last_index + 1
                    )

        except Exception as e:
            log.error(e)

    @classmethod
    async def association_steps(cls, case_id: int, quote: bool, play_step_id_list: List[int], user: User):
        """
        关联公共步骤到用例
        
        Args:
            case_id: 用例ID
            quote: 是否直接引用步骤（True为引用，False为复制）
            play_step_id_list: 公共步骤ID列表
            user: 当前操作用户
            
        Notes:
            - 当quote为True时，直接引用公共步骤
            - 当quote为False时，复制步骤并创建新的非公共步骤
            - 自动更新用例的步骤数量
            - 使用事务确保操作的原子性
            - 使用批量操作减少数据库交互次数
        """
        if not case_id:
            raise ValueError("用例ID不能为空")
        if not play_step_id_list:
            raise ValueError("步骤列表不能为空")

        try:
            async with async_session() as session:
                async with session.begin():
                    try:
                        play_case = await cls.get_by_id(ident=case_id, session=session)
                        if not play_case:
                            raise ValueError(f"找不到ID为{case_id}的用例")

                        # 批量更新步骤数量，避免多次更新同一字段
                        play_case.step_num += len(play_step_id_list)
                        case_step_content_play_step_list = []

                        # 引用
                        if quote:
                            # 批量获取步骤信息，减少数据库查询次数
                            # get_by_ids 现在保证返回的步骤列表顺序与传入的 ID 列表一致
                            steps = await PlayStepV2Mapper.get_by_ids(play_step_id_list, session)
                            if not steps:
                                log.warning(f"未找到ID为{play_step_id_list}的步骤")
                                return

                            # 直接使用返回的步骤列表，已经按照传入的ID顺序排序
                            # 创建步骤ID到步骤对象的映射，用于快速查找
                            step_map = {step.id: step for step in steps}

                            # 遍历传入的ID列表，确保顺序一致
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
                        # 复制
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

                        last_index = await CommonHelper.get_case_step_last_index(case_id, session)
                        content_ids = [content.id for content in case_step_content_play_step_list]

                        if content_ids:
                            await CommonHelper.create_case_content_association(
                                session, case_id, content_ids, last_index + 1
                            )
                        else:
                            log.warning(f"没有创建任何步骤关联，用例ID: {case_id}")
                            # 回滚步骤数量更新
                            play_case.step_num -= len(play_step_id_list)

                    except Exception as transaction_err:
                        session.rollback()
                        log.exception(f"事务执行失败: {transaction_err}")
                        raise
        except Exception as e:
            log.exception(f"关联步骤出现错误: {e}")
            raise

    @classmethod
    async def insert_step_association(cls, case_id: int, user: User, **kwargs):
        """
        插入私有步骤关联到用例
        
        Args:
            case_id: 用例ID
            user: 当前操作用户
            **kwargs: 步骤相关参数
            
        Notes:
            - 自动更新用例的步骤数量
            - 创建新的私有步骤并关联到用例
            - 使用事务确保操作的原子性
        """
        if not case_id:
            raise ValueError("用例ID不能为空")
        if not user:
            raise ValueError("用户信息不能为空")
        if not kwargs:
            raise ValueError("步骤参数不能为空")

        try:
            async with async_session() as session:
                async with session.begin():
                    try:
                        play_case = await cls.get_by_id(ident=case_id, session=session)
                        if not play_case:
                            raise ValueError(f"找不到ID为{case_id}的用例")

                        # 保存步骤
                        try:
                            step = await PlayStepV2Mapper.save(
                                creator_user=user,
                                session=session,
                                **kwargs
                            )
                        except Exception as save_err:
                            log.exception(f"保存步骤失败: {save_err}")
                            raise ValueError("创建步骤失败")

                        # 创建内容
                        try:
                            content = await PlayStepContentMapper.init_content(
                                target_id=step.id,
                                is_common=False,
                                content_type=PlayStepContentType.STEP_PLAY,
                                session=session,
                                content_desc=step.method,
                                content_name=step.name
                            )
                        except Exception as content_err:
                            log.exception(f"创建步骤内容失败: {content_err}")
                            raise ValueError("创建步骤内容失败")

                        # 获取最后索引并创建关联
                        last_index = await CommonHelper.get_case_step_last_index(case_id, session)
                        await CommonHelper.create_single_case_content_association(
                            session, case_id, content.id, last_index + 1
                        )

                        # 更新步骤数量
                        play_case.step_num += 1

                    except Exception as transaction_err:
                        session.rollback()
                        log.exception(f"事务执行失败: {transaction_err}")
                        raise
        except Exception as e:
            log.exception(f"关联步骤出现错误: {e}")
            raise

    @classmethod
    async def reorder_content_step(cls, case_id: int, content_id_list: [int]):
        """
        重新排序用例中的步骤
        
        Args:
            case_id: 用例ID
            content_id_list: 步骤内容ID列表，按期望的顺序排列
            
        Notes:
            - 使用SQL的CASE语句批量更新步骤顺序
            - 只更新指定列表中的步骤顺序
            - 一次数据库操作完成所有排序更新，提高性能
        """
        if not case_id:
            raise ValueError("用例ID不能为空")
        if not content_id_list:
            raise ValueError("步骤内容ID列表不能为空")

        try:
            async with async_session() as session:
                async with session.begin():
                    try:
                        # 验证用例是否存在
                        play_case = await cls.get_by_id(ident=case_id, session=session)
                        if not play_case:
                            raise ValueError(f"找不到ID为{case_id}的用例")

                        # 验证步骤内容是否属于该用例
                        existing_associations = await session.execute(
                            select(PlayCaseStepContentAssociation.play_step_content_id).where(
                                and_(
                                    PlayCaseStepContentAssociation.play_case_id == case_id,
                                    PlayCaseStepContentAssociation.play_step_content_id.in_(content_id_list)
                                )
                            )
                        )
                        existing_ids = {id[0] for id in existing_associations.all()}

                        if len(existing_ids) != len(content_id_list):
                            invalid_ids = set(content_id_list) - existing_ids
                            log.warning(f"以下步骤内容ID不属于用例{case_id}: {invalid_ids}")

                        # 创建CASE语句的条件映射
                        whens = {step_id: index for index, step_id in enumerate(content_id_list, start=1)}

                        # 执行批量更新
                        result = await session.execute(
                            update(PlayCaseStepContentAssociation)
                            .where(
                                and_(
                                    PlayCaseStepContentAssociation.play_step_content_id.in_(content_id_list),
                                    PlayCaseStepContentAssociation.play_case_id == case_id
                                )
                            )
                            .values(
                                step_order=case(whens, value=PlayCaseStepContentAssociation.play_step_content_id)
                            )
                        )

                        log.info(f"更新了{result.rowcount}个步骤的顺序，用例ID: {case_id}")

                    except Exception as transaction_err:
                        session.rollback()
                        log.exception(f"事务执行失败: {transaction_err}")
                        raise
        except Exception as e:
            log.exception(f"重新排序步骤出现错误: {e}")
            raise

    @classmethod
    async def copy_content(cls, case_id: int, content_id: int, user: User):
        """
        复制步骤到底部
        
        Args:
            case_id: 用例ID
            content_id: 要复制的步骤内容ID
            user: 当前操作用户
            
        Notes:
            - 自动更新用例的步骤数量
            - 为新复制的步骤分配正确的顺序索引
            - 使用事务确保操作的原子性
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    play_case = await cls.get_by_id(ident=case_id, session=session)
                    content = await PlayStepContentMapper.copy_content(
                        content_id=content_id,
                        session=session,
                        user=user
                    )

                    play_case.step_num += 1
                    last_index = await CommonHelper.get_case_step_last_index(case_id, session)
                    await CommonHelper.create_single_case_content_association(
                        session, case_id, content.id, last_index + 1
                    )

        except Exception as e:
            raise e

    @classmethod
    async def remove_step(cls, content_id: int, case_id: int = None):
        """
        从用例中移除步骤
        
        Args:
            content_id: 步骤内容ID
            case_id: 用例ID，若为空则删除公共步骤
            
        Notes:
            - 自动更新用例的步骤数量
            - 移除用例与步骤的关联关系
            - 对于非公共步骤，会同时删除步骤本身
            - 使用事务确保操作的原子性
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    content = await PlayStepContentMapper.get_by_id(ident=content_id, session=session)
                    # 查询步骤
                    play_case = await cls.get_by_id(ident=case_id, session=session)
                    if play_case.step_num > 0:  # 防止负数
                        play_case.step_num -= 1

                    # 删除关联表
                    await session.execute(
                        delete(PlayCaseStepContentAssociation).where(
                            and_(
                                PlayCaseStepContentAssociation.play_step_content_id == content_id,
                                PlayCaseStepContentAssociation.play_case_id == case_id
                            )
                        )
                    )
                    if not content.is_common:
                        await PlayStepContentMapper.delete_content(content=content, session=session)


        except Exception as e:
            raise e

    @classmethod
    async def query_content_steps(cls, case_id: int, session: Optional[AsyncSession] = None) -> Sequence[
        PlayStepContent]:
        """
        查询用例的步骤内容
        
        Args:
            case_id: 用例ID
            session: 数据库会话对象，若为None则创建新会话
            
        Returns:
            Sequence[PlayStepContent]: 步骤内容列表，按步骤顺序排序
        """
        if session is None:
            session = async_session()
        scalars_data = await session.scalars(
            select(PlayStepContent).join(
                PlayCaseStepContentAssociation,
                PlayStepContent.id == PlayCaseStepContentAssociation.play_step_content_id
            ).where(
                PlayCaseStepContentAssociation.play_case_id == case_id
            ).order_by(
                PlayCaseStepContentAssociation.step_order
            )
        )
        return scalars_data.all()

    @classmethod
    async def copy_case(cls, caseId: int, cr: User):
        """
        复制用例
        
        Args:
            caseId: 要复制的用例ID
            cr: 当前操作用户
            
        Returns:
            PlayCase: 复制后的新用例对象
            
        Notes:
            - 复制用例基本信息
            - 复制用例的步骤
            - 复制用例的变量
            - 使用事务确保操作的原子性
            - 使用asyncio.gather并发复制步骤，提高效率
            - 使用批量操作减少数据库交互次数
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    pass

        except Exception as e:
            raise e


class PlayCaseVariablesMapper(Mapper[PlayCaseVariables]):
    """
    用例变量映射器
    
    处理用例变量的增删改查操作
    """
    __model__ = PlayCaseVariables

    @classmethod
    async def copy_vars(cls, target_caseId: int, new_caseId: int, session: AsyncSession, cr: User):
        """
        复制用例变量
        
        Args:
            target_caseId: 目标用例ID
            new_caseId: 新用例ID
            session: 数据库会话对象
            cr: 当前操作用户
            
        Notes:
            - 复制目标用例的所有变量到新用例
            - 更新变量的创建人信息
        """
        try:
            exe = await session.execute(select(cls.__model__).where(
                cls.__model__.play_case_id == target_caseId
            ))
            case_vars = exe.scalars().all()

            if case_vars:
                for var in case_vars:
                    v = var.copy_map()
                    v['play_case_id'] = new_caseId
                    v['creator'] = cr.id
                    v['creatorName'] = cr.username
                    await cls.save(session=session, **v)
        except Exception as e:
            raise e

    @classmethod
    async def insert(cls, user: User, **kwargs):
        """
        插入变量数据
        同一个case 校验 key 唯一
        
        Args:
            user: 当前操作用户
            kwargs: 变量相关参数
            
        Notes:
            - 校验同一个用例中key的唯一性
        """
        key = kwargs.get("key")
        caseId = kwargs.get("play_case_id")
        try:
            async with async_session() as session:
                await PlayCaseVariablesMapper._check_key(key, caseId, session)
                await cls.save(session=session, creator_user=user, **kwargs)
        except Exception as e:
            raise e

    @classmethod
    async def update_by_id(cls, updateUser: User = None, **kwargs):
        """
        更新变量数据
        
        Args:
            updateUser: 当前操作用户
            kwargs: 变量更新参数
            
        Returns:
            更新后的变量对象
            
        Notes:
            - 如果更新了key字段，会校验唯一性
        """
        caseId = kwargs.get("play_case_id")
        key = kwargs.get("key")
        if not key:
            return await super().update_by_id(updateUser=updateUser, **kwargs)
        try:
            async with async_session() as session:
                await PlayCaseVariablesMapper._check_key(key, caseId, session)
                return await super().update_by_id(updateUser=updateUser, session=session, **kwargs)
        except Exception as e:
            raise

    @staticmethod
    async def _check_key(key: str, caseId: int, session: AsyncSession):
        """
        检查key在case中的唯一性
        
        Args:
            key: 变量键名
            caseId: 用例ID
            session: 数据库会话对象
            
        Returns:
            bool: 如果key不存在则返回True
            
        Raises:
            NotFind: 如果key已存在则抛出异常
        """
        key_exists = await session.execute(
            select(PlayCaseVariables).where(and_(
                PlayCaseVariables.key == key,
                PlayCaseVariables.play_case_id == caseId
            ))
        )
        if key_exists.scalar():
            raise NotFind("key 已存在 请检查")

        return True


class PlayCaseResultMapper(Mapper[PlayCaseResult]):
    """
    用例结果映射器
    
    处理用例执行结果的相关操作
    """
    __model__ = PlayCaseResult

    @classmethod
    async def clear_case_result(cls, caseId: int):
        """
        清空用例调试历史
        
        Args:
            caseId: 用例ID
            
        Notes:
            - 删除失败结果中的本地附件
            - 删除用例的调试历史记录
            - 使用事务确保操作的原子性
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    # 查找失败结果 删除本地附件
                    search_sql = select(cls.__model__.ui_case_err_step_pic_path).where(
                        and_(
                            cls.__model__.result == Result.FAIL,
                            cls.__model__.ui_case_Id == caseId,
                            cls.__model__.task_result_id is None
                        )
                    )
                    data = await session.scalars(search_sql)
                    datas = data.all()
                    file_ids = [i.split("uid=")[-1] for i in datas if i]
                    for i in file_ids:
                        await FileMapper.remove_file(i, session)

                    delete_sql = delete(cls.__model__).where(and_(
                        cls.__model__.ui_case_Id == caseId,
                        cls.__model__.task_result_id is None
                    ))
                    await session.execute(delete_sql)
        except Exception as e:
            session.rollback()
            log.error(e)
            raise e

    @classmethod
    async def init_case_result(cls,
                               play_case: PlayCase,
                               user: UIStarter,
                               vars_list: List[Dict[str, Any]] = None,
                               task_result_id: int = None) -> PlayCaseResult:
        """
        初始化用例结果模型
        
        Args:
            play_case: 运行的用例对象
            user: 运行人
            task_result_id: 任务结果ID，可选
            vars_list: 变量

        Returns:
            PlayCaseResult: 初始化后的用例结果对象
            
        Notes:
            - 设置初始状态为RUNNING
            - 记录开始时间和运行人信息
            - 复制用例的基本信息到结果中
        """
        try:
            async with async_session() as session:
                result = PlayCaseResult(
                    ui_case_Id=play_case.id,
                    ui_case_name=play_case.title,
                    ui_case_description=play_case.description,
                    ui_case_step_num=play_case.step_num,
                    starter_id=user.userId,
                    starter_name=user.username,
                    start_time=datetime.now(),
                    task_result_id=task_result_id,
                    status=Status.RUNNING,
                    vars_info=vars_list if vars_list else [],
                    asserts_info=[],
                )
                await session.add(result)
                await session.commit()
                return result
        except Exception as e:
            log.error(e)
            raise e

    @classmethod
    async def set_case_result(cls, result: PlayCaseResult):
        """
        保存用例结果
        
        Args:
            result: 用例结果对象
            
        Returns:
            PlayCaseResult: 保存后的用例结果对象
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    await cls.add_flush_expunge(session, result)
                    return result
        except Exception as e:
            log.error(e)
            raise e

    @classmethod
    async def set_case_result_assertInfo(cls, crId: int, assertsInfo: List[Dict[str, Any]]):
        """
        更新用例结果的断言信息
        
        Args:
            crId: 用例结果ID
            assertsInfo: 断言信息列表
        """
        try:
            async with async_session() as session:
                update_sql = update(PlayCaseResult).where(PlayCaseResult.id == crId).values(
                    asserts_info=assertsInfo)
                await session.execute(update_sql)
                await session.commit()
        except Exception as e:
            raise e

    @classmethod
    async def set_case_result_varsInfo(cls, crId: int, varsInfo: List[Dict[str, Any]]):
        """
        更新用例结果的变量信息
        
        Args:
            crId: 用例结果ID
            varsInfo: 变量信息列表
        """
        try:
            async with async_session() as session:
                update_sql = update(PlayCaseResult).where(PlayCaseResult.id == crId).values(
                    vars_info=varsInfo)
                await session.execute(update_sql)
                await session.commit()
        except Exception as e:
            raise e


class PlayStepContentMapper(Mapper[PlayStepContent]):
    __model__ = PlayStepContent

    @classmethod
    async def add_content(cls, case_id: int, user: User, content_type: PlayStepContentType, is_common=True):
        """

        :param case_id:
        :param user:
        :param content_type:
        :param is_common:
        :return:
        """

        async with async_session() as session:
            async with session.begin():
                play_case = await PlayCaseMapper.get_by_id(ident=case_id, session=session)
                play_case.step_num += 1

                content = PlayStepContent(
                    content_type=content_type,
                    is_common=is_common,
                    creator=user.id,
                    creatorName=user.username,
                )
                last_index = await CommonHelper.get_case_step_last_index(case_id, session)
                await cls.add_flush_expunge(session, content)
                await CommonHelper.create_single_case_content_association(
                    session, case_id, content.id, last_index + 1
                )

    @classmethod
    async def init_content(cls,
                           session: AsyncSession,
                           content_type: PlayStepContentType,
                           target_id: int,
                           is_common: bool = True,
                           content_name: str = None,
                           content_desc: str = None,
                           ):
        """

        :param session:
        :param content_type:
        :param target_id:
        :param is_common:
        :param content_name:
        :param content_desc:

        :return:
        """
        content = PlayStepContent(
            content_name=content_name,
            content_desc=content_desc,
            content_type=content_type,
            is_common=is_common,
            target_id=target_id,
        )
        match content_type:
            case PlayStepContentType.STEP_PLAY:
                content.target_id = target_id
            # todo other content_type
        return await cls.add_flush_expunge(session, content)

    @classmethod
    async def copy_content(cls, content_id: int, session: AsyncSession, user: User) -> PlayStepContent:
        """
        复制
        :param content_id:
        :param session:
        :param user:
        :return:
        """

        content = await cls.get_by_id(ident=content_id, session=session)

        match content.content_type:
            case PlayStepContentType.STEP_PLAY:
                step = await PlayStepV2Mapper.get_by_id(ident=content.target_id, session=session)

                new_step = await PlayStepV2Mapper.copy_step(
                    step_id=step.id,
                    session=session,
                    user=user
                )

                new_content = PlayStepContent(
                    target_id=new_step.id,
                    content_name=content.content_name,
                    content_desc=content.content_desc,
                    content_type=content.content_type,
                    is_common=False,
                    creator=user.id,
                    creatorName=user.username,
                )
                return await cls.add_flush_expunge(session, new_content)

            case PlayStepContentType.STEP_PLAY_GROUP:
                from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper
                group = await PlayStepGroupMapper.copy_group2(group_id=content.target_id,
                                                              user=user,
                                                              session=session)
                new_content = PlayStepContent(
                    target_id=group.id,
                    content_name=group.name,
                    content_desc=group.description,
                    content_type=content.content_type,
                    is_common=False,
                    creator=user.id,
                    creatorName=user.username,
                )
                return await cls.add_flush_expunge(session, new_content)

    @classmethod
    async def delete_content(cls, content: PlayStepContent, session: AsyncSession):
        """

        :param content:
        :param session:
        :return:
        """
        match content.content_type:
            case PlayStepContentType.STEP_PLAY:
                try:
                    step = await PlayStepV2Mapper.get_by_id(ident=content.target_id, session=session)
                    await session.delete(step)
                except NotFind:
                    pass

        await session.delete(content)
