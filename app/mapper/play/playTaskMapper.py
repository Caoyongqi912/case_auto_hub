#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/2
# @Author : cyq
# @File : playTaskMapper
# @Software: PyCharm
# @Desc:
from typing import List

from sqlalchemy import select, insert, update, and_, delete
from sqlalchemy.sql.functions import count

from app.mapper import Mapper
from app.model.playUI import PlayTask, PlayTaskResult, PlayCase, PlayTaskCasesAssociation
from enums import TaskStatus
from croe.play.starter import UIStarter
from utils import log


class PlayTaskMapper(Mapper[PlayTask]):
    __model__ = PlayTask

    @classmethod
    async def query_auto_tasks(cls) -> List[PlayTask]:
        """
        查询所有定时任务。

        使用 session_scope() 自动管理 session 生命周期（只读查询）。
        """
        try:
            # 统一使用 session_scope() 替代直接 async_session()
            async with cls.session_scope() as session:
                tasks = await session.scalars(select(PlayTask).where(PlayTask.is_auto is True))
                return tasks.all()
        except Exception as e:
            log.error(e)
            raise e

    @classmethod
    async def remove_task(cls, taskId: int, scheduler):
        """
        删除任务。

        使用 transaction() 自动管理 session 和事务边界。
        """
        try:
            # 统一使用 transaction() 替代 async_session() + manual commit
            # 自动创建 session + begin，退出时自动 commit/rollback
            async with cls.transaction() as session:
                task = await cls.get_by_id(ident=taskId, session=session)
                await scheduler.remove_job(task.uid)
                await session.execute(delete(PlayTask).where(PlayTask.id == taskId))
        except Exception as e:
            raise e

    @classmethod
    async def query_case(cls, taskId: int) -> List[PlayCase]:
        """
        查询任务关联的用例列表。

        使用 session_scope() 自动管理 session 生命周期（只读查询）。

        Args:
            taskId: 任务 ID

        Returns:
            List[PlayCase]: 用例列表（按 case_order 排序）
        """
        try:
            # 统一使用 session_scope() 替代直接 async_session()
            async with cls.session_scope() as session:
                cases = await session.scalars(
                    select(PlayCase).join(
                        PlayTaskCasesAssociation,
                        PlayTaskCasesAssociation.play_case_id == PlayCase.id
                    ).where(
                        PlayTaskCasesAssociation.play_task_id == taskId
                    ).order_by(
                        PlayTaskCasesAssociation.case_order
                    )
                )
                return cases.all()
        except Exception as e:
            raise e

    @classmethod
    async def association_cases(cls, taskId: int, caseIdList: list[int]):
        """
        批量添加用例到任务。

        使用 transaction() 自动管理 session 和事务边界。

        Args:
            taskId: 任务 ID
            caseIdList: 用例 ID 列表
        """
        try:
            # 统一使用 transaction() 替代 async_session() + session.begin()
            # 自动创建 session + begin，异常时自动 rollback
            async with cls.transaction() as session:
                task = await cls.get_by_id(ident=taskId, session=session)
                # 检查现有的 UI Case IDs
                existing_cases = await session.execute(select(PlayTaskCasesAssociation.play_case_id).where(
                    PlayTaskCasesAssociation.play_task_id == taskId
                ))
                existing_case_ids = {row[0] for row in existing_cases}
                sql = (
                    select(PlayTaskCasesAssociation.case_order).where(
                        PlayTaskCasesAssociation.play_task_id == taskId
                    ).order_by(PlayTaskCasesAssociation.case_order.desc()).limit(1)
                )
                result = await session.execute(sql)
                last_step_order = result.scalar()  # Fetch the first (and only) result
                last_step_order or 0
                # 批量插入用例
                new_cases = [
                    {
                        'play_task_id': taskId,
                        'play_case_id': caseId,
                        'case_order': index
                    }
                    for index, caseId in enumerate(caseIdList, start=last_case_index + 1)
                    if caseId not in existing_case_ids
                ]
                if new_cases:
                    result = await session.execute(insert(PlayTaskCasesAssociation).values(new_cases))
                    task.play_case_num += result.rowcount  # 更新已添加的用例数量
        except Exception as e:
            raise e

    @classmethod
    async def reorder_association_case(cls, taskId: int, caseIdList: list[int]):
        """
        重新排序任务关联的用例。

        使用 transaction() 自动管理 session 和事务边界。
        """
        try:
            # 统一使用 transaction() 替代 async_session() + manual commit
            async with cls.transaction() as session:
                for index, caseId in enumerate(caseIdList, start=1):
                    await session.execute(update(PlayTaskCasesAssociation).where(
                        and_(
                            PlayTaskCasesAssociation.play_case_id == caseId,
                            PlayTaskCasesAssociation.play_task_id == taskId
                        )

                    ).values(case_order=index))
        except Exception as e:
            raise e

    @classmethod
    async def remove_association_case(cls, taskId: int, caseId: int):
        """
        移除任务关联的用例，并重新计算用例数量。

        使用 transaction() 自动管理 session 和事务边界。

        Args:
            taskId: 任务 ID
            caseId: 用例 ID
        """
        try:
            # 统一使用 transaction() 替代 async_session() + session.begin()
            async with cls.transaction() as session:
                task: PlayTask = await cls.get_by_id(ident=taskId, session=session)
                # 删除关联
                await session.execute(delete(PlayTaskCasesAssociation).where(
                    and_(
                        PlayTaskCasesAssociation.play_task_id == taskId,
                        PlayTaskCasesAssociation.play_case_id == caseId
                    )
                ))
                # # 重新排序
                # await reorder_case
                # 更新用例数量
                data = await session.execute(
                    select(count('*')).where(PlayTaskCasesAssociation.play_task_id == taskId)
                )
                task.ui_case_num = data.scalar()
        except Exception as e:
            raise e

    @classmethod
    async def set_task_status(cls, taskId: int, status: str):
        """
        设置任务状态。

        使用 transaction() 自动管理 session 和事务边界。

        Args:
            taskId: 任务 ID
            status: 新状态
        """
        try:
            # 统一使用 transaction() 替代 async_session() + manual commit
            async with cls.transaction() as session:
                await session.execute(update(cls.__model__).where(
                    cls.__model__.id == taskId
                ).values(
                    status=status
                ))
        except Exception as e:
            raise e


class PlayTaskResultMapper(Mapper[PlayTaskResult]):
    __model__ = PlayTaskResult

    @classmethod
    async def init_task_result(cls, task: PlayTask, case_total_num: int, runner: UIStarter) -> PlayTaskResult:
        """
        初始化任务基础结果模型。

        使用 transaction() 自动管理 session 和事务边界，
        创建结果记录后 flush 以生成主键，然后 expunge 分离模型。

        参数:
            task: PlayTask 实例
            case_total_num: 用例总数
            runner: UIStarter 实例

        返回:
            PlayTaskResult: 初始化后的任务基础结果模型实例
        """
        try:
            # 统一使用 transaction() 替代 async_session() + manual commit
            # 自动创建 session + begin，退出时自动 commit
            async with cls.transaction() as session:
                result = PlayTaskResult(
                    task_id=task.id,
                    task_name=task.title,
                    task_uid=task.uid,
                    status=TaskStatus.RUNNING,
                    starter_name=runner.username,
                    project_id=task.project_id,
                    module_id=task.module_id,
                    total_number=case_total_num
                )
                session.add(result)
                await session.flush()
                # 刷新会话，将更改同步到数据库（生成主键）并分离模型
                await cls.flush_expunge(session, result)
                return result
        except Exception as e:
            raise e

    @classmethod
    async def set_result(cls, result: PlayTaskResult):
        """
        保存任务结果。

        使用 transaction() 自动管理 session 和事务边界。
        """
        try:
            # 统一使用 transaction() 替代 async_session() + manual commit
            async with cls.transaction() as session:
                session.add(result)
                await session.flush()
        except Exception as e:
            raise e

    @classmethod
    async def clear_result(cls, taskId: int):
        """
        清空指定任务的所有结果记录。

        使用 transaction() 自动管理 session 和事务边界。

        Args:
            taskId: 任务 ID
        """
        try:
            # 统一使用 transaction() 替代 async_session() + manual commit
            async with cls.transaction() as session:
                await session.execute(delete(PlayTaskResult).where(PlayTaskResult.task_id == taskId))
        except Exception as e:
            raise e
