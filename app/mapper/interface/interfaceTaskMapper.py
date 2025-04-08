#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceTaskMapper# @Software: PyCharm# @Desc:from typing import List, Sequencefrom sqlalchemy import select, insert, exists, delete, update, bindparam, and_from sqlalchemy.ext.asyncio import AsyncSessionfrom app.mapper import Mapperfrom app.model import async_sessionfrom app.model.interface import InterfaceTask, case_task_association, InterFaceCaseModel, InterfaceModel, \    api_task_associationfrom utils import MyLogurufrom utils.wrapper_ import session_transactionlog = MyLoguru().get_logger()class InterfaceTaskMapper(Mapper):    __model__ = InterfaceTask    @classmethod    async def set_is_auto(cls, is_auto: bool, taskId: int) -> InterfaceTask:        """开关任务"""        try:            async with async_session() as session:                async with session.begin():                    task = await cls.get_by_id(ident=taskId, session=session)                    await cls.update_cls(task, session, is_auto=is_auto)                    return task        except Exception as e:            raise e    @classmethod    async def query_case(cls, taskId: int) -> List[InterFaceCaseModel]:        """查询所有用例"""        try:            async with async_session() as session:                cases = await session.scalars(                    select(InterFaceCaseModel).join(                        case_task_association,                        InterFaceCaseModel.id == case_task_association.c.inter_case_id                    ).where(                        case_task_association.c.task_id == bindparam('task_id', taskId)                    ).order_by(                        case_task_association.c.step_order                    )                )                return cases.all()        except Exception as e:            raise e    @classmethod    async def query_apis(cls, taskId: int) -> List[InterfaceModel]:        """        查询关联所有api        """        try:            async with async_session() as session:                cases = await session.scalars(                    select(InterfaceModel).join(                        api_task_association,                        InterfaceModel.id == api_task_association.c.api_id                    ).where(                        api_task_association.c.task_id == taskId                    ).order_by(                        api_task_association.c.step_order                    )                )                return cases.all()        except Exception as e:            raise e    @classmethod    async def association_apis(cls, taskId: int, apiIds: List[int]) -> bool | None:        """        关联用例 与任务        :param taskId:        :param apiIds:        :return:        """        try:            _exists = False            async with async_session() as session:                async with session.begin():                    if not apiIds:                        return                    task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)                    last_case_index = await InterfaceTaskMapper.get_api_last_index(session=session, taskId=taskId)                    for index, apiId in enumerate(apiIds, start=last_case_index + 1):                        if not await cls.verify_apiId(session, taskId, apiId):                            _exists = True                            continue                        else:                            task.total_apis_num += 1                            await session.execute((insert(api_task_association).values(                                dict(                                    task_id=taskId,                                    api_id=apiId,                                    step_order=index                                )                            )))                    return _exists        except Exception as e:            raise e    @classmethod    async def association_cases(cls, taskId: int, caseIds: List[int]) -> bool | None:        """        关联用例 与任务        如果已关联 pass        :param taskId:        :param caseIds:        :return:        """        try:            _exists = False            async with async_session() as session:                async with session.begin():                    if not caseIds:                        return                    task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)                    last_case_index = await InterfaceTaskMapper.get_case_last_index(session=session, taskId=taskId)                    for index, caseId in enumerate(caseIds, start=last_case_index + 1):                        if not await cls.verify_caseId(session, taskId, caseId):                            _exists = True                            continue                        task.total_cases_num += 1                        await session.execute((insert(case_task_association).values(                            dict(                                task_id=taskId,                                inter_case_id=caseId,                                step_order=index                            )                        )))                    return _exists        except Exception as e:            raise e    @staticmethod    async def verify_caseId(session: AsyncSession, taskId: int, caseId: int):        """校验caseId 是否再关联中"""        try:            query = exists(select(1).where(                and_(                    case_task_association.c.task_id == taskId,                    case_task_association.c.inter_case_id == caseId                )            )).select()            return not await session.scalar(query)        except Exception as e:            raise e    @staticmethod    async def verify_apiId(session: AsyncSession, taskId: int, api_id: int):        """校验apiId 是否再关联中"""        try:            query = exists(select(1).where(                and_(api_task_association.c.task_id == taskId,                     api_task_association.c.api_id == api_id)            )).select()            return not await session.scalar(query)        except Exception as e:            raise e    @classmethod    async def remove_association_case(cls, taskId: int, caseId: int):        """        接触关联        :param taskId:        :param caseId:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)                    # 删除关联表数据                    await session.execute(case_task_association.delete().where(                        case_task_association.c.inter_case_id == caseId,                        case_task_association.c.task_id == taskId                    ))                    # 重新排序                    stmt = await session.scalars(                        select(InterFaceCaseModel).join(                            case_task_association,                            InterFaceCaseModel.id == case_task_association.c.inter_case_id                        ).where(                            case_task_association.c.task_id == taskId,                        ).order_by(                            case_task_association.c.step_order                        )                    )                    cases = stmt.all()                    task.total_cases_num = len(cases)                    for index, case in enumerate(cases, start=1):                        sql = case_task_association.update().where(                            and_(                                case_task_association.c.task_id == task.id,                                case_task_association.c.inter_case_id == case.id                            )                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    @session_transaction    async def remove_association_api(cls, taskId: int, apiId: int, session: AsyncSession = None):        """        解除关联        :param taskId:        :param apiId:        :param session        :return:        """        try:            task: InterfaceTask = await cls.get_by_id(ident=taskId, session=session)            # 删除关联表数据            await session.execute(api_task_association.delete().where(                api_task_association.c.api_id == apiId,                api_task_association.c.task_id == taskId            ))            # 重新排序            apis = await session.execute(                select(InterfaceModel).join(                    api_task_association,                    InterfaceModel.id == api_task_association.c.api_id                ).where(                    api_task_association.c.task_id == taskId,                ).order_by(                    api_task_association.c.step_order                )            )            apis = apis.scalars().all()            task.total_apis_num = len(apis)            for index, api in enumerate(apis, start=1):                sql = api_task_association.update().where(                    and_(                        api_task_association.c.api_id == api.id,                        api_task_association.c.task_id == taskId                    )                ).values(step_order=index)                await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def reorder_cases(cls, taskId: int, caseIds: List[int]):        """        重新排序关联        :param taskId:        :param caseIds:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    for index, caseId in enumerate(caseIds, start=1):                        sql = case_task_association.update().where(                            and_(                                case_task_association.c.inter_case_id == caseId                                , case_task_association.c.task_id == taskId                            )                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def reorder_apis(cls, taskId: int, apiIds: List[int]):        """        重新排序关联        :param taskId:        :param apiIds:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    for index, apiId in enumerate(apiIds, start=1):                        sql = api_task_association.update().where(                            and_(                                api_task_association.c.api_id == apiId,                                api_task_association.c.task_id == taskId                            )                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @staticmethod    async def get_case_last_index(session: AsyncSession, taskId: int) -> int:        stmt = select(case_task_association.c.step_order).where(            case_task_association.c.task_id == taskId        ).order_by(case_task_association.c.step_order.desc()).limit(1)        try:            result = await session.execute(stmt)            last_step_order = result.scalar()  # 获取第一个结果            # 如果查询结果为 None，则返回 0；否则返回查询到的值            return last_step_order if last_step_order is not None else 0        except Exception as e:            raise e    @staticmethod    async def get_api_last_index(session: AsyncSession, taskId: int) -> int:        try:            sql = (                select(api_task_association.c.step_order).where(                    api_task_association.c.task_id == taskId                ).order_by(api_task_association.c.step_order.desc()).limit(1)            )            log.debug(sql)            result = await session.execute(sql)            last_step_order = result.scalar()  # Fetch the first (and only) result            return last_step_order or 0        except Exception as e:            raise e    @staticmethod    async def set_task_when_api_remove(session: AsyncSession, apiId: int):        """        当 api删除        重新排序与计算数量        :param session:        :param apiId:        :return:        """        try:            stmt = await session.scalars(select(InterfaceTask.id).join(                api_task_association,                api_task_association.c.task_id == InterfaceTask.id            ).where(                api_task_association.c.api_id == apiId            ))            task_ids: Sequence[InterfaceTask] = stmt.all()            await session.execute(                update(InterfaceTask).where(                    InterfaceTask.id.in_(task_ids)                ).values(                    total_apis_num=InterfaceTask.total_apis_num - 1                )            )            await session.execute(                delete(api_task_association).where(                    api_task_association.c.api_id == apiId                )            )        except Exception as e:            raise e    @staticmethod    async def set_task_when_case_remove(session: AsyncSession, caseId: int):        """        当 case 删除，删除关联        重新排序与计算数量        :param session:        :param caseId:        :return:        """        try:            stmt = await session.scalars(select(InterfaceTask).join(                case_task_association,                case_task_association.c.task_id == InterfaceTask.id            ).where(                case_task_association.c.inter_case_id == caseId            ))            tasks: Sequence[InterfaceTask] = stmt.all()            # 批量更新任务的 total_cases_num            task_ids = [task.id for task in tasks]            await session.execute(                update(InterfaceTask)                .where(InterfaceTask.id.in_(task_ids))                .values(total_cases_num=InterfaceTask.total_cases_num - 1)            )            # 删除关联            await session.execute(                delete(case_task_association).where(                    case_task_association.c.inter_case_id == caseId                )            )            log.info(f"Successfully removed associations for caseId {caseId} and updated related tasks.")        except Exception as e:            raise e    @classmethod    async def query_auto_task(cls):        """        获取自动开启的任务        """        try:            async with async_session() as session:                stmt = select(InterfaceTask).where(                    InterfaceTask.is_auto == True,                )                await session.scalars(stmt).all()        except Exception as e:            raise e    @classmethod    async def remove_task(cls, taskId: int):        """        级联删除        :param taskId:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    task = await cls.get_by_id(taskId, session)                    await session.execute(                        delete(api_task_association).where(                            api_task_association.c.task_id == taskId                        )                    )                    await session.execute(                        delete(case_task_association).where(                            case_task_association.c.task_id == taskId                        )                    )                    await session.delete(task)        except Exception as e:            raise e