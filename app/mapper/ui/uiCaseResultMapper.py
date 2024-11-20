#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/9# @Author : cyq# @File : uiCaseResultMapper# @Software: PyCharm# @Desc:from datetime import datetimefrom typing import Any, List, Dictfrom model import async_sessionfrom sqlalchemy import update, deletefrom model.ui import UICaseModel, UITaskModel, UICaseTaskResultBaseModel, UIResultModelfrom model.base.user import Userfrom app.mapper import Mapperfrom utils import logfrom enums.CaseEnum import Statusfrom datetime import dateclass UICaseResultMapper(Mapper):    __model__ = UIResultModel    @staticmethod    async def clear_case_result(caseId: int):        try:            async with async_session() as session:                delete_sql = delete(UIResultModel).filter_by(ui_case_Id=caseId)                await session.execute(delete_sql)                await session.commit()        except Exception as e:            session.rollback()            log.error(e)            raise e    @staticmethod    async def init_case_result_model(case: UICaseModel,                                     user: User = None,                                     baseId: int = None) -> UIResultModel:        """        初始化用例结果模型        :param case: 运行case        :param user: 运行人        :param baseId:        :return:        """        try:            async with async_session() as session:                result = UIResultModel(                    ui_case_Id=case.id,                    ui_case_name=case.title,                    ui_case_desc=case.desc,                    ui_case_step_num=case.step_num,                    starterId=user.id if user else 9999,                    starterName=user.username if user else "ROBOT",                    startTime=datetime.now(),                    ui_case_base_id=baseId,                )                session.add(result)                await session.commit()                session.expunge(result)                return result        except Exception as e:            log.error(e)            raise e    @staticmethod    async def set_case_result(result: UIResultModel):        try:            async with async_session() as session:                session.add(result)                await session.commit()        except Exception as e:            log.error(e)            raise e    @staticmethod    async def set_case_result_assertInfo(crId: int, assertsInfo: List[Dict[str, Any]]):        try:            async with async_session() as session:                update_sql = update(UIResultModel).where(UIResultModel.id == crId).values(assertsInfo=assertsInfo)                await session.execute(update_sql)                await session.commit()        except Exception as e:            raise eclass UICaseTaskResultBaseMapper(Mapper):    __model__ = UICaseTaskResultBaseModel    @staticmethod    async def init_task_base_result_model(totalNumber: int,                                          task: UITaskModel,                                          user: User = None):        try:            async with async_session() as session:                base_result = UICaseTaskResultBaseModel()                base_result.status = Status.RUNNING                base_result.totalNumber = totalNumber                base_result.taskId = task.id                base_result.taskUid = task.uid                base_result.taskName = task.title                base_result.runDay = date.today()                if user:                    base_result.startBy = 1                    base_result.starterName = user.username                    base_result.starterId = user.id                else:                    base_result.startBy = 2                    base_result.starterName = "ROBOT"                session.add(base_result)                await session.commit()                session.expunge(base_result)                return base_result        except Exception as e:            log.error(e)            raise e    @staticmethod    async def set_base_result(result: UICaseTaskResultBaseModel):        try:            async with async_session() as session:                session.add(result)                await session.commit()        except Exception as e:            log.error(e)            raise e