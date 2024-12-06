#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceCase# @Software: PyCharm# @Desc:import asynciofrom fastapi import APIRouterfrom fastapi.params import Dependsfrom app.controller import Authenticationfrom app.model.base import Userfrom app.response import Responsefrom app.schema.interface import InsertInterfaceCaseBaseInfoSchema, OptionInterfaceCaseSchema, PageInterfaceCaseSchema, \    AddInterfaceApi2Case, ReorderInterfaceApi2Case, RemoveInterfaceApi2Case, ExecuteInterfaceCaseSchemafrom app.mapper.interface import InterfaceCaseMapperfrom interface.runner import InterFaceRunnerfrom utils import logrouter = APIRouter(prefix="/interface/case", tags=['自动化接口步骤'])@router.post("/insertBaseInfo", description="插入用例基本信息")async def insert_case_base_info(info: InsertInterfaceCaseBaseInfoSchema, creator: User = Depends(    Authentication())):    case = await InterfaceCaseMapper.save(        creatorUser=creator,        **info.dict()    )    return Response.success(case)@router.post("/update", description="修改用例基本信息")async def update_case_base_info(info: OptionInterfaceCaseSchema, updater: User = Depends(    Authentication())):    await InterfaceCaseMapper.update_by_id(        updateUser=updater,        **info.dict()    )    return Response.success()@router.post("/remove", description="删除用例")async def remove_api_case(info: OptionInterfaceCaseSchema, _: User = Depends(    Authentication())):    await InterfaceCaseMapper.delete_by_id(        ident=info.id    )    return Response.success()@router.post("/copy", description="复制用例")async def copy_api_case(info: OptionInterfaceCaseSchema, creator: User = Depends(    Authentication())):    await InterfaceCaseMapper.copy_case(        caseId=info.id,        creator=creator    )    return Response.success()@router.post("/copyApi", description="复制用例中api")async def copy_case_api(info: AddInterfaceApi2Case, copyer: User = Depends(Authentication())):    await InterfaceCaseMapper.copy_case_api(        **info.dict(),        copyer=copyer    )    return Response.success()@router.get("/baseInfo", description="插入用例基本信息")async def insert_case_base_info(info: OptionInterfaceCaseSchema = Depends(), creator: User = Depends(    Authentication())):    case = await InterfaceCaseMapper.get_by_id(ident=info.id)    return Response.success(case)@router.post("/page", description="分页")async def page_api_case(pageInfo: PageInterfaceCaseSchema, _=Depends(Authentication())):    cases = await InterfaceCaseMapper.page_query(**pageInfo.dict(        exclude_unset=True,        exclude_none=True,    ))    return Response.success(cases)@router.post("/addOrderApi", description='添加API')async def add_api_to_apiCase(addInfo: AddInterfaceApi2Case, _=Depends(Authentication())):    await InterfaceCaseMapper.add_api(**addInfo.dict())    return Response.success()@router.get("/query/apis", description="查询关联API")async def query_apis_by_caseId(caseId: int, _=Depends(Authentication())):    apis = await InterfaceCaseMapper.query_interface_by_caseId(caseId=caseId)    return Response.success(apis)@router.post("/remove/api", description="从case里移除api")async def remove_api_form_case(removeInfo: RemoveInterfaceApi2Case, _=Depends(Authentication())):    await InterfaceCaseMapper.remove_api(**removeInfo.dict())    return Response.success()@router.post("/reorder/apis", description="管理API重新排序")async def reorder_apis_by_caseId(orderInfo: ReorderInterfaceApi2Case, _=Depends(Authentication())):    await InterfaceCaseMapper.reorder_apis(**orderInfo.dict())    return Response.success()@router.post("/execute", description="用例执行")async def execute_case_api(case: ExecuteInterfaceCaseSchema, starter: User = Depends(Authentication())):    from interface.io_sender import APISocketSender    io = APISocketSender(starter.uid)    asyncio.create_task(InterFaceRunner(starter=starter,                                        io=io                                        ).run_interCase(caseId=case.caseId))    return Response.success()