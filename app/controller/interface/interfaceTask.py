#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceTask# @Software: PyCharm# @Desc:import asynciofrom fastapi import APIRouter, Dependsfrom app.mapper.interface import InterfaceTaskMapper, InterfaceTaskResultMapperfrom app.controller import Authenticationfrom app.model.base import Userfrom app.response import Responsefrom app.scheduler import Schedulerfrom app.schema.interface import InsertInterfaceCaseTaskSchema, PageInterfaceCaseTaskSchema, \    OptionInterfaceCaseTaskSchema, AssocCasesSchema, RemoveAssocCasesSchema, AssocApisSchema, RemoveAssocApisSchema, \    GetByTaskId, PageInterfaceTaskResultSchema, RemoveInterfaceTaskResultDetailSchema, SetTaskAutofrom enums import StarterEnumfrom interface.io_sender import APISocketSenderfrom interface.starter import Starterfrom interface.taskRunner import TaskRunnerfrom utils import logrouter = APIRouter(prefix="/interface/task", tags=['自动化接口步骤'])@router.post('/insertTask', description="创建任务")async def insertTask(taskInfo: InsertInterfaceCaseTaskSchema, creator: User = Depends(Authentication())):    task = await InterfaceTaskMapper.save(        creatorUser=creator,        **taskInfo.dict(            exclude_unset=True,            exclude_none=True        )    )    if task.is_auto:        Scheduler.addApiTaskJob(task)    return Response.success(task)@router.post("/updateTask", description="修改")async def updateTask(update: OptionInterfaceCaseTaskSchema, updater: User = Depends(Authentication())):    task = await InterfaceTaskMapper.update_by_id(        updateUser=updater,        **update.dict(exclude_unset=True,                      exclude_none=True)    )    if task.is_auto:        Scheduler.editAPiTaskJob(task)    else:        Scheduler.pause(task.uid)    return Response.success()@router.get("/detail", description="任务详情")async def get_task_detail(task: OptionInterfaceCaseTaskSchema = Depends(), _: User = Depends(Authentication())):    task = await InterfaceTaskMapper.get_by_id(ident=task.id)    return Response.success(task)@router.post("/setAuto", description="任务自动化设置")async def get_task_detail(task: SetTaskAuto, _: User = Depends(Authentication())):    task = await InterfaceTaskMapper.set_is_auto(**task.dict())    if task.is_auto:        Scheduler.editAPiTaskJob(task)    else:        Scheduler.pause(task.uid)    return Response.success()@router.get("/nextRunTime", description="任务自动化设置")async def get_task_nextRunTime(taskUid: str, _: User = Depends(Authentication())):    t = Scheduler.job_next_run_time(taskUid)    return Response.success(t)@router.post("/removeTask", description='删除任务')async def removeTask(task: OptionInterfaceCaseTaskSchema, _: User = Depends(Authentication())):    await InterfaceTaskMapper.delete_by_id(ident=task.id)    return Response.success()@router.post("/page", description="任务分页")async def pageTask(pageInfo: PageInterfaceCaseTaskSchema, _=Depends(Authentication())):    tasks = await InterfaceTaskMapper.page_query(**pageInfo.dict(        exclude_unset=True,        exclude_none=True    ))    return Response.success(tasks)@router.post("/association/cases", description="关联用例")async def association_cases(info: AssocCasesSchema, _: User = Depends(Authentication())):    exist_ = await InterfaceTaskMapper.association_cases(**info.dict())    return Response.success(exist_)@router.post("/association/apis", description="关联apis")async def association_cases(info: AssocApisSchema, _: User = Depends(Authentication())):    await InterfaceTaskMapper.association_apis(**info.dict())    return Response.success()@router.post("/remove/association/cases", description="移除关联")async def association_case(info: RemoveAssocCasesSchema, _: User = Depends(Authentication())):    await InterfaceTaskMapper.remove_association_case(**info.dict())    return Response.success()@router.post("/remove/association/apis", description="移除api关联")async def association_case(info: RemoveAssocApisSchema, _: User = Depends(Authentication())):    await InterfaceTaskMapper.remove_association_api(**info.dict())    return Response.success()@router.get("/query/cases", description="查询关联用例")async def query_cases(info: GetByTaskId = Depends(), _: User = Depends(Authentication())):    cases = await InterfaceTaskMapper.query_case(info.taskId)    return Response.success(cases)@router.get("/query/apis", description="查询关联api用例")async def query_cases(info: GetByTaskId = Depends(), _: User = Depends(Authentication())):    apis = await InterfaceTaskMapper.query_apis(info.taskId)    return Response.success(apis)@router.post("/reorder/cases", description="重排用例")async def query_cases(info: AssocCasesSchema, _: User = Depends(Authentication())):    cases = await InterfaceTaskMapper.reorder_cases(**info.dict())    return Response.success(cases)@router.post("/reorder/apis", description="重排用例")async def query_cases(info: AssocApisSchema, _: User = Depends(Authentication())):    apis = await InterfaceTaskMapper.reorder_apis(**info.dict())    return Response.success(apis)@router.post('/execute', description="手动运行Task")async def executed_task(task: GetByTaskId, starter: User = Depends(Authentication())):    io = APISocketSender(starter.uid)    _starter = Starter(startBy=starter)    asyncio.create_task(TaskRunner(_starter, io).runTask(        taskId=task.taskId    ))    return Response.success()@router.post('/executeByJenkins', description="手动运行Task")async def executed_task(task: GetByTaskId):    io = APISocketSender()    _starter = Starter(startBy=StarterEnum.Jenkins)    asyncio.create_task(TaskRunner(io=io,                                   starter=_starter).runTask(        taskId=task.taskId    ))    return Response.success()@router.get("/resultInfo", description="任务结果info")async def result_info(info: GetByTaskId = Depends(), _: User = Depends(Authentication())):    info = await InterfaceTaskResultMapper.get_by_id(info.taskId)    return Response.success(info)@router.post("/queryResults", description="查询结果")async def query_task_results(info: PageInterfaceTaskResultSchema, _: User = Depends(Authentication())):    results = await InterfaceTaskResultMapper.page_query(**info.dict(        exclude_unset=True,        exclude_none=True    ))    return Response.success(results)@router.post("/removeResult", description='移除任务结果')async def remove_task_result(result: RemoveInterfaceTaskResultDetailSchema, _: User = Depends(Authentication())):    await InterfaceTaskResultMapper.delete_by_id(result.resultId)    return Response.success()