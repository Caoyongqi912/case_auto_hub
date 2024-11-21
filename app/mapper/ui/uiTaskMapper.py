#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : uiTaskMapper# @Software: PyCharm# @Desc:import jsonfrom typing import Typefrom app.exception import NotFindfrom app.mapper.project import ProjectMapperfrom app.mapper.project.projectPart import ProjectPartMapperfrom app.model import async_sessionfrom sqlalchemy import select, update, case, func, and_, insert, deletefrom app.model.ui import UICaseModel, UITaskModel, case_task_Table, UICaseTaskResultBaseModelfrom app.model.base import CasePart,Userfrom app.mapper import Mapper, pages, Tfrom enums.CaseEnum import Statusfrom utils import logclass UITaskMapper(Mapper):    __model__ = UITaskModel    @classmethod    async def delete_by_uid(cls, uid: str):        try:            from app.scheduler import Scheduler            Scheduler.removeTaskJob(uid)            return await super().delete_by_uid(uid)        except Exception as e:            raise e    @classmethod    async def update_by_uid(cls: Type[T], **kwargs):        """        通过uid更新        自动关闭  关闭开关        更新aps        :param kwargs:        """        uid = kwargs.pop("uid")        try:            async with async_session() as session:                async with session.begin():                    task = await cls.get_by_uid(uid, session)                    # 更新用户                    updater: int = kwargs.get("updater", None)                    if updater:                        exe = await session.execute(                            select(User).where(User.id == updater)                        )                        user = exe.scalar()                        if user:                            task.updater = user.id                            task.updaterName = user.username                    update_fields = {k: v for k, v in kwargs.items() if k in                                     UITaskModel.__table__.columns}                    for field, value in update_fields.items():                        setattr(task, field, value)                    await session.flush()                    from app.scheduler import Scheduler                    # 如果修改isAuto 为关闭 则删除定时任务                    if task.isAuto is False:                        task.switch = False                        Scheduler.removeTaskJob(task.uid)                    else:                        # 如果开启 则创建或者回复任务                        Scheduler.editTaskJob(task)        except Exception as e:            raise e    @classmethod    async def page_ui_cases(cls, taskId: str, current: int, pageSize: int, **kwargs):        """        所属用例分页        :param taskId: 任务        :param current:        :param pageSize:        :param kwargs: 查询条件        :return:        """        try:            sort = json.loads(kwargs.pop("sort", None))        except TypeError as e:            sort = None            log.error(f"Error parsing sort {e}")        kwargs = {k: v for k, v in kwargs.items() if v != ""}        log.info(f"search info  = {kwargs}")        try:            async with async_session() as session:                task: UITaskModel = await cls.get_by_uid(uid=taskId, session=session)                query = (                    select(UICaseModel)                    .join(case_task_Table)                    .where(case_task_Table.c.ui_task_id == task.id)                )                # 使用 filter() 进行过滤，只考虑 UICaseModel 的属性                filters = [getattr(UICaseModel, key) == value for key, value in kwargs.items() if                           hasattr(UICaseModel, key)]                if filters:                    query = query.filter(*filters)                total_query = select(func.count()).select_from(query)                total = (await session.execute(total_query)).scalar()                # 进行排序                if sort:                    for k, v in sort.items():                        if v == "descend":                            cases = query.order_by(getattr(UICaseModel, k).desc())                        else:                            cases = query.order_by(getattr(UICaseModel, k).asc())                else:                    cases = query.order_by(UICaseModel.create_time)                # 执行主查询                exe = await session.execute(cases)                cases = exe.scalars().all()                results = {                    "items": cases,                    "pageInfo": {                        "total": total,                        "pages": pages(total, pageSize),                        "page": current,                        "limit": pageSize                    }                }                return results        except Exception as e:            raise e    @classmethod    async def addUICases(cls, taskUid: str, caseIdList: list[int]):        """        添加用例到task        :param taskUid:        :param caseIdList:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    task: UITaskModel = await cls.get_by_uid(uid=taskUid, session=session)                    # 检查现有的 UI Case IDs                    existing_cases_query = select(case_task_Table.c.ui_case_id).where(                        case_task_Table.c.ui_task_id == task.id                    )                    existing_cases = await session.execute(existing_cases_query)                    existing_case_ids = {row[0] for row in existing_cases}                    # 批量插入用例                    new_cases = [                        {                            'ui_task_id': task.id,                            'ui_case_id': caseId,                            'case_order': index                        }                        for index, caseId in enumerate(caseIdList, start=1)                        if caseId not in existing_case_ids                    ]                    if new_cases:                        await session.execute(insert(case_task_Table).values(new_cases))                        task.ui_case_num += len(new_cases)  # 更新已添加的用例数量                    await session.commit()        except Exception as e:            raise e    @classmethod    async def removeUICase(cls, taskId: int, caseId: int):        """        移除用例        重新计算数量        :param taskId:        :param caseId:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    task: UITaskModel = await cls.get_by_id(ident=taskId, session=session)                    sql = delete(case_task_Table).where(                        and_(                            case_task_Table.c.ui_task_id == taskId,                            case_task_Table.c.ui_case_id == caseId                        )                    )                    await session.execute(sql)                    # 计算剩余用例数量                    count_stmt = select(func.count()).select_from(case_task_Table).where(                        case_task_Table.c.ui_task_id == taskId                    )                    total = (await session.execute(count_stmt)).scalar()                    task.ui_case_num = total                    await session.commit()        except Exception as e:            raise e    @classmethod    async def save(cls, **kwargs) -> UITaskModel:        """        添加task        :param kwargs:NewTaskSchema        :return:UITaskModel        """        try:            projectId = kwargs.get("projectId")            casePartId = kwargs.get("casePartId")            title = kwargs.get("title")            creator = kwargs.get("creator")            async with async_session() as session:                async with session.begin():                    await ProjectPartMapper.get_by_id(ident=casePartId, session=session, desc="部门")                    await ProjectMapper.get_by_id(ident=projectId, session=session, desc="项目")                    user = await cls.get_creator(creatorId=creator, session=session)                    kwargs['creatorName'] = user.username                    ex = await UITaskMapper.get_by(session=session, **{"title": title})                    if ex:                        raise NotFind("任务名称重复")                    model = UITaskMapper.__model__(**kwargs)                    model.switch = model.isAuto                    session.add(model)                    await session.flush()                    session.expunge(model)                    return model        except Exception as e:            await session.rollback()            raise e    @staticmethod    async def get_status_by_partId(partId: int, st: str, et: str):        """        通过root part 查询执行情况        :param partId:        :param st        :param et        :return:        """        try:            async with async_session() as session:                sql = select(                    func.sum(case((UICaseTaskResultBaseModel.result == "SUCCESS", 1), else_=0)).label(                        "SUCCESS"),                    func.sum(case((UICaseTaskResultBaseModel.result == "FAIL", 1), else_=0)).label(                        "FAIL"),                    func.count('*').label("TOTAL"),                    UICaseTaskResultBaseModel.runDay                ).join(                    UITaskModel,                    UITaskModel.id == UICaseTaskResultBaseModel.taskId,                ).join(                    CasePart,                    CasePart.id == UITaskModel.casePartId,                ).where(                    and_(                        CasePart.id == partId,                        UICaseTaskResultBaseModel.runDay >= st,                        UICaseTaskResultBaseModel.runDay <= et                    )                ).group_by(                    UICaseTaskResultBaseModel.runDay                )                result = await session.execute(sql)                raw_data = result.fetchall()                # 将查询结果转换为字典列表                data_dicts = [                    {                        "SUCCESS": row.SUCCESS,                        "FAIL": row.FAIL,                        "TOTAL": row.TOTAL,                        "runDay": row.runDay.strftime("%Y-%m-%d")                    }                    for row in raw_data                ]                return data_dicts        except Exception as e:            raise e    @staticmethod    async def query_cases_by_task_id(taskId: int):        try:            async with async_session() as session:                sql = select(UICaseModel).join(                    case_task_Table,                    case_task_Table.c.ui_case_id == UICaseModel.id                ).where(                    case_task_Table.c.ui_task_id == taskId                ).order_by(case_task_Table.c.case_order)                cases = await session.execute(sql)                return cases.scalars().all()        except Exception as e:            raise e    @staticmethod    async def set_task_status(taskId: int, status: Status):        """        task 设置运行状态        :param taskId:        :param status: RUNNING WAIT        :return:        """        try:            async with async_session() as session:                async with session.begin():                    sql = update(UITaskModel).where(UITaskModel.id == taskId).values(status=status)                    await session.execute(sql)        except Exception as e:            raise e