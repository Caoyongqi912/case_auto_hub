#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceTaskMapper# @Software: PyCharm# @Desc:from logging import raiseExceptionsfrom typing import List, Any, Sequencefrom sqlalchemy import select, insert, exists,deletefrom sqlalchemy.ext.asyncio import AsyncSessionfrom app.mapper import Mapperfrom app.model import async_sessionfrom app.model.base import Userfrom app.model.interface import InterfaceTask, case_task_association, InterFaceCaseModel, InterfaceModel, \    api_task_associationfrom utils import MyLogurufrom utils.wrapper_ import session_transactionlog = MyLoguru().get_logger()class InterfaceTaskMapper(Mapper):    __model__ = InterfaceTask    @classmethod    async def set_is_auto(cls, is_auto: bool, taskId: int) -> InterfaceTask:        """开关任务"""        try:            async with async_session() as session:                async with session.begin():                    task = await cls.get_by_id(ident=taskId, session=session)                    await cls.update_cls(task, session, is_auto=is_auto)                    return task        except Exception as e:            raise e    @classmethod    async def query_case(cls, taskId: int) -> List[InterFaceCaseModel]:        """查询所有用例"""        try:            async with async_session() as session:                cases = await session.scalars(                    select(InterFaceCaseModel).join(                        case_task_association,                        case_task_association.c.inter_case_id == InterFaceCaseModel.id                    ).where(                        case_task_association.c.task_id == taskId                    ).order_by(                        case_task_association.c.step_order                    )                )                return cases.all()        except Exception as e:            raise e    @classmethod    async def query_apis(cls, taskId: int) -> List[InterfaceModel]:        """        查询关联所有api        """        try:            async with async_session() as session:                cases = await session.scalars(                    select(InterfaceModel).join(                        api_task_association,                        api_task_association.c.api_id == InterfaceModel.id                    ).where(                        api_task_association.c.task_id == taskId                    ).order_by(                        api_task_association.c.step_order                    )                )                return cases.all()        except Exception as e:            raise e    @classmethod    async def association_apis(cls, taskId: int, apiIds: List[int]) -> bool | None:        """        关联用例 与任务        :param taskId:        :param apiIds:        :return:        """        try:            _exists = False            async with async_session() as session:                async with session.begin():                    if not apiIds:                        return                    task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)                    last_case_index = await InterfaceTaskMapper.get_api_last_index(session=session, taskId=taskId)                    for index, apiId in enumerate(apiIds, start=last_case_index + 1):                        if not await cls.verify_apiId(session, taskId, apiId):                            _exists = True                            continue                        else:                            task.total_apis_num += 1                            await session.execute((insert(api_task_association).values(                                dict(                                    task_id=taskId,                                    api_id=apiId,                                    step_order=index                                )                            )))                    return _exists        except Exception as e:            raise e    @classmethod    async def association_cases(cls, taskId: int, caseIds: List[int]) -> bool | None:        """        关联用例 与任务        如果已关联 pass        :param taskId:        :param caseIds:        :return:        """        try:            _exists = False            async with async_session() as session:                async with session.begin():                    if not caseIds:                        return                    task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)                    task.total_cases_num += len(caseIds)                    last_case_index = await InterfaceTaskMapper.get_case_last_index(session=session, taskId=taskId)                    for index, caseId in enumerate(caseIds, start=last_case_index + 1):                        if not await cls.verify_caseId(session, taskId, caseId):                            _exists = True                            continue                        task.total_cases_num += 1                        await session.execute((insert(case_task_association).values(                            dict(                                task_id=taskId,                                inter_case_id=caseId,                                step_order=index                            )                        )))                    return _exists        except Exception as e:            raise e    @staticmethod    async def verify_caseId(session: AsyncSession, taskId: int, caseId: int):        """校验caseId 是否再关联中"""        try:            query = exists(select(1).where(                case_task_association.c.task_id == taskId,                case_task_association.c.inter_case_id == caseId            )).select()            result = await session.scalar(query)            return not result        except Exception as e:            raise e    @staticmethod    async def verify_apiId(session: AsyncSession, taskId: int, api_id: int):        """校验apiId 是否再关联中"""        try:            query = exists(select(1).where(                api_task_association.c.task_id == taskId,                api_task_association.c.api_id == api_id            )).select()            result = await session.scalar(query)            return not result        except Exception as e:            raise e    @classmethod    async def remove_association_case(cls, taskId: int, caseId: int):        """        接触关联        :param taskId:        :param caseId:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)                    # 删除关联表数据                    await session.execute(case_task_association.delete().where(                        case_task_association.c.inter_case_id == caseId,                        case_task_association.c.task_id == taskId                    ))                    # 重新排序                    cases = await session.execute(                        select(InterFaceCaseModel).join(                            case_task_association,                            case_task_association.c.inter_case_id == InterFaceCaseModel.id                        ).where(                            case_task_association.c.task_id == taskId,                        ).order_by(                            case_task_association.c.step_order                        )                    )                    cases = cases.scalars().all()                    task.total_cases_num = len(cases)                    for index, case in enumerate(cases, start=1):                        sql = case_task_association.update().where(                            (case_task_association.c.inter_case_id == case.id) &                            (case_task_association.c.task_id == task.id)                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    @session_transaction    async def remove_association_api(cls, taskId: int, apiId: int, session: AsyncSession = None):        """        解除关联        :param taskId:        :param apiId:        :param session        :return:        """        try:            task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)            # 删除关联表数据            await session.execute(api_task_association.delete().where(                api_task_association.c.api_id == apiId,                api_task_association.c.task_id == taskId            ))            # 重新排序            apis = await session.execute(                select(InterfaceModel).join(                    api_task_association,                    api_task_association.c.api_id == InterfaceModel.id                ).where(                    api_task_association.c.task_id == taskId,                ).order_by(                    api_task_association.c.step_order                )            )            apis = apis.scalars().all()            task.total_apis_num = len(apis)            for index, api in enumerate(apis, start=1):                sql = api_task_association.update().where(                    (api_task_association.c.api_id == api.id) &                    (api_task_association.c.task_id == task.id)                ).values(step_order=index)                await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def reorder_cases(cls, taskId: int, caseIds: List[int]):        """        重新排序关联        :param taskId:        :param caseIds:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    for index, caseId in enumerate(caseIds, start=1):                        sql = case_task_association.update().where(                            (case_task_association.c.inter_case_id == caseId) &                            (case_task_association.c.task_id == taskId)                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def reorder_apis(cls, taskId: int, apiIds: List[int]):        """        重新排序关联        :param taskId:        :param apiIds:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    for index, apiId in enumerate(apiIds, start=1):                        sql = api_task_association.update().where(                            (api_task_association.c.api_id == apiId) &                            (api_task_association.c.task_id == taskId)                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @staticmethod    async def get_case_last_index(session: AsyncSession, taskId: int) -> int:        try:            sql = (                select(case_task_association.c.step_order).where(                    case_task_association.c.task_id == taskId                ).order_by(case_task_association.c.step_order.desc()).limit(1)            )            result = await session.execute(sql)            last_step_order = result.scalar()  # Fetch the first (and only) result            return last_step_order or 0        except Exception as e:            raise e    @staticmethod    async def get_api_last_index(session: AsyncSession, taskId: int) -> int:        try:            sql = (                select(api_task_association.c.step_order).where(                    api_task_association.c.task_id == taskId                ).order_by(api_task_association.c.step_order.desc()).limit(1)            )            log.debug(sql)            result = await session.execute(sql)            last_step_order = result.scalar()  # Fetch the first (and only) result            return last_step_order or 0        except Exception as e:            raise e    @staticmethod    async def set_task_when_api_remove(session: AsyncSession, apiId: int):        """        当 api删除        重新排序与计算数量        :param session:        :param apiId:        :return:        """        try:            query = await session.scalars(select(InterfaceTask).join(                api_task_association,                api_task_association.c.task_id == InterfaceTask.id            ).where(                api_task_association.c.api_id == apiId            ))            tasks: Sequence[InterfaceTask] = query.all()            log.debug(tasks)            if tasks:                for task in tasks:                    task.total_apis_num -= 1        except Exception as e:            raise e    @staticmethod    async def set_task_when_case_remove(session: AsyncSession, caseId: int):        """        当 case 删除        重新排序与计算数量        :param session:        :param caseId:        :return:        """        try:            query = await session.scalars(select(InterfaceTask).join(                case_task_association,                case_task_association.c.task_id == InterfaceTask.id            ).where(                case_task_association.c.inter_case_id == caseId            ))            tasks: Sequence[InterfaceTask] = query.all()            log.debug(tasks)            if tasks:                for task in tasks:                    task.total_cases_num -= 1        except Exception as e:            raise e    @classmethod    async def remove_task(cls, taskId: int):        """        级联删除        :param taskId:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    task = await cls.get_by_id(taskId,session)                    await session.execute(                        delete(api_task_association).where(                            api_task_association.c.task_id == taskId                        )                    )                    await session.execute(                        delete(case_task_association).where(                            case_task_association.c.task_id == taskId                        )                    )                    await session.delete(task)        except Exception as e:            raise e