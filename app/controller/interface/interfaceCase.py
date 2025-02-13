#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceCase# @Software: PyCharm# @Desc:import asynciofrom fastapi import APIRouterfrom fastapi.params import Dependsfrom app.mapper.interface.interfaceVarsMapper import InterfaceVarsMapperfrom interface.io_sender import APISocketSenderfrom app.schema.base.vars import *from app.controller import Authenticationfrom app.model.base import Userfrom app.response import Responsefrom app.schema.interface import InsertInterfaceCaseBaseInfoSchema, OptionInterfaceCaseSchema, PageInterfaceCaseSchema, \    AddInterfaceApi2Case, ReorderInterfaceApi2Case, RemoveInterfaceApi2Case, ExecuteInterfaceCaseSchema, \    AddInterfaceCaseCommonAPISchema, AddInterfaceCaseCommonGROUPSchemafrom app.mapper.interface import InterfaceCaseMapperfrom interface.runner import InterFaceRunnerfrom interface.starter import Starterfrom utils import logrouter = APIRouter(prefix="/interface/case", tags=['自动化接口步骤'])@router.post("/insertBaseInfo", description="插入用例基本信息")async def insert_case_base_info(info: InsertInterfaceCaseBaseInfoSchema, creator: User = Depends(    Authentication())):    case = await InterfaceCaseMapper.save(        creatorUser=creator,        **info.dict()    )    return Response.success(case)@router.post("/update", description="修改用例基本信息")async def update_case_base_info(info: OptionInterfaceCaseSchema, updater: User = Depends(    Authentication())):    await InterfaceCaseMapper.update_by_id(        updateUser=updater,        **info.dict()    )    return Response.success()@router.post("/remove", description="删除用例")async def remove_api_case(info: OptionInterfaceCaseSchema, _: User = Depends(    Authentication())):    await InterfaceCaseMapper.delete_by_id(        ident=info.id    )    return Response.success()@router.post("/copy", description="复制用例")async def copy_api_case(info: OptionInterfaceCaseSchema, creator: User = Depends(    Authentication())):    await InterfaceCaseMapper.copy_case(        caseId=info.id,        creator=creator    )    return Response.success()@router.post("/copyApi", description="复制用例中api")async def copy_case_api(info: AddInterfaceApi2Case, copyer: User = Depends(Authentication())):    await InterfaceCaseMapper.copy_case_api(        **info.dict(),        copyer=copyer    )    return Response.success()@router.post("/selectApis", description="选择添加公共API")async def select_common_apis(apis: AddInterfaceCaseCommonAPISchema, _=Depends(Authentication())):    await InterfaceCaseMapper.add_common_apis(**apis.dict())    return Response.success()@router.post("/selectGroups", description="选择添加公共API GROUP")async def select_groups(info: AddInterfaceCaseCommonGROUPSchema, _=Depends(Authentication())):    await InterfaceCaseMapper.add_group_step(**info.dict())    return Response.success()@router.get("/baseInfo", description="插入用例基本信息")async def insert_case_base_info(info: OptionInterfaceCaseSchema = Depends(), creator: User = Depends(    Authentication())):    case = await InterfaceCaseMapper.get_by_id(ident=info.id)    return Response.success(case)@router.post("/page", description="分页")async def page_api_case(pageInfo: PageInterfaceCaseSchema, _=Depends(Authentication())):    cases = await InterfaceCaseMapper.page_query(**pageInfo.dict(        exclude_unset=True,        exclude_none=True,    ))    return Response.success(cases)@router.post("/addOrderApi", description='添加API')async def add_api_to_apiCase(addInfo: AddInterfaceApi2Case, _=Depends(Authentication())):    await InterfaceCaseMapper.add_api(**addInfo.dict())    return Response.success()@router.get("/query/apis", description="查询关联API")async def query_apis_by_caseId(caseId: int, _=Depends(Authentication())):    apis = await InterfaceCaseMapper.query_interface_by_caseId(caseId=caseId)    return Response.success(apis)@router.post("/remove/api", description="从case里移除api")async def remove_api_form_case(removeInfo: RemoveInterfaceApi2Case, _=Depends(Authentication())):    await InterfaceCaseMapper.remove_api(**removeInfo.dict())    return Response.success()@router.post("/reorder/apis", description="管理API重新排序")async def reorder_apis_by_caseId(orderInfo: ReorderInterfaceApi2Case, _=Depends(Authentication())):    await InterfaceCaseMapper.reorder_apis(**orderInfo.dict())    return Response.success()@router.post("/execute/io", description="用例执行")async def execute_case_api(case: ExecuteInterfaceCaseSchema, starter: User = Depends(Authentication())):    io = APISocketSender(starter.uid)    _starter = Starter(starter)    asyncio.create_task(InterFaceRunner(starter=_starter,                                        io=io                                        ).run_interCase(interfaceCaseId=case.caseId))    return Response.success()@router.post("/execute/back", description="用例执行")async def execute_case_api(case: ExecuteInterfaceCaseSchema, starter: User = Depends(Authentication())):    io = APISocketSender()    _starter = Starter(starter)    asyncio.create_task(InterFaceRunner(starter=_starter,                                        io=io,                                        ).run_interCase(interfaceCaseId=case.caseId))    return Response.success()@router.post('/vars/add', description='添加变量')async def add_vars(varInfo: AddVarsSchema, cr: User = Depends(Authentication())):    log.debug(varInfo)    await InterfaceVarsMapper.insert(user=cr,                                     **varInfo.dict(exclude_none=True, exclude_unset=True))    return Response.success()@router.post('/vars/update', description='修改变量')async def add_vars(varInfo: UpdateVarsSchema, cr: User = Depends(Authentication())):    await InterfaceVarsMapper.update_by_uid(updateUser=cr, **varInfo.dict(exclude_none=True,                                                                          exclude_unset=True))    return Response.success()@router.post('/vars/remove', description='删除变量')async def add_vars(varInfo: DeleteVarsSchema, _: User = Depends(Authentication())):    await InterfaceVarsMapper.delete_by_uid(**varInfo.dict())    return Response.success()@router.post('/vars/page', description='查询变量')async def page_vars(varsInfo: PageVarsSchema, _: User = Depends(Authentication())):    datas = await InterfaceVarsMapper.page_query(**varsInfo.dict())    return Response.success(datas)