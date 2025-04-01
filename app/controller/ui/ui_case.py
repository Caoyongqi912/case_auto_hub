#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : ui_case# @Software: PyCharm# @Desc:import asynciofrom http.client import responsesfrom app.controller import Authenticationfrom app.mapper.ui.uiCaseResultMapper import UICaseResultMapperfrom fastapi import APIRouter, Dependsfrom app.response import Responsefrom app.mapper.ui.uiCaseMapper import *from app.mapper.ui.uiCaseVariableMapper import UICaseVariableMapperfrom app.schema.ui import *from play.player import Playerfrom asyncio import create_taskfrom play.starter import UIStarterrouter = APIRouter(prefix="/ui/case", tags=['自动化用例'])@router.post("/add", description="新增用例基本信息")async def add_case(case: AddUICaseBaseSchema, cr: User = Depends(Authentication())):    case = await UICaseMapper.save(        creatorUser=cr,        **case.model_dump())    return Response.success(case)@router.post("/copy", description="复制用例")async def copy_case(copyInfo: OPTUICaseBaseSchema, cr: User = Depends(Authentication())):    case = await UICaseMapper.copy_case(        caseId=copyInfo.caseId, cr=cr)    return Response.success(case)@router.post("/edit", description="修改用例基本信息")async def edit_case(case: EditUICaseBaseSchema, ur: User = Depends(Authentication())):    case = await UICaseMapper.update_by_id(        updateUser=ur,        **case.model_dump())    return Response.success(case)@router.get("/detail", description="用例基本信息")async def case_detail(case: OPTUICaseBaseSchema = Depends(), _: User = Depends(Authentication())):    case = await UICaseMapper.get_by_id(case.caseId)    return Response.success(case)@router.post("/remove", description="删除用例")async def case_detail(case: OPTUICaseBaseSchema, _: User = Depends(Authentication())):    await UICaseMapper.delete_by_id(case.caseId)    return Response.success()@router.get("/query", description="查询用例")async def query_cases(_: User = Depends(Authentication())):    """    查询所有用例    """    cases = await UICaseMapper.query_all()    return Response.success(cases)@router.post("/page", description="分页查询")async def page_cases(search: UICasePage, _: User = Depends(Authentication())):    """    分页查询    :param search:    :param _:    :return:    """    data = await UICaseMapper.page_by_module(**search.model_dump(exclude_none=True,                                                           exclude_unset=True))    return Response.success(data)@router.get("/step/page", description="用例步骤分页查询")async def page_steps(search: PageUICaseStep = Depends()):    """    分页查询    :param search:    :return:    """    data = await UICaseStepMapper.page_query(**search.model_dump(exclude_none=True, exclude_unset=True))    return Response.success(data)@router.get("/step/query", description="用例步骤列表")async def query_steps(id: int):    """    query_steps    :return:    """    data = await UICaseStepMapper.query_steps_by_caseId(caseId=id)    return Response.success(data)@router.post("/result/page", description="用例结果分页查询")async def page_case_result(search: PageUIResultSchema, _: User = Depends(Authentication())):    """    分页查询    :param search:    :param _    :return:    """    data = await UICaseResultMapper.page_query(**search.model_dump(exclude_none=True, exclude_unset=True))    return Response.success(data)@router.get("/result/clear", description="清空调试历史")async def clear_result(caseId: int, _: User = Depends(Authentication())):    await UICaseResultMapper.clear_case_result(caseId=caseId)    return Response.success()@router.get("/result/detail", description="用例结果详情")async def get_case_result(uid: str, _: User = Depends(Authentication())):    result = await UICaseResultMapper.get_by_uid(uid)    return Response.success(result)@router.post("/variable/add", description="添加前置变量")async def add_extract(var: InsertUICaseVariable):    """    添加前置变量    """    await UICaseVariableMapper.insert(**var.model_dump())    return Response.success()@router.get("/variable/page", description="通过caseId查询")async def query_extract(pageInfo: UIVariablesPage = Depends()):    """    通过caseId查询    """    data = await UICaseVariableMapper.page_query(**pageInfo.model_dump(exclude_none=True))    return Response.success(data)@router.post("/variable/delete", description="删除前置变量")async def query_extract(body: GetOrDeleteUICaeVariable):    """    通过caseId查询    """    await UICaseVariableMapper.delete_by_uid(uid=body.uid)    return Response.success()@router.post("/variable/update", description="更新前置变量")async def update_extract(variable: UpdateUICaseVariable):    """    更新变量    """    await UICaseVariableMapper.update_by_uid(**variable.model_dump(exclude_none=True))    return Response.success()@router.post("/choice/common/steps", description="关联公共步骤 引用添加")async def add_common_step(steps: ChoiceUICaseBaseSchema, _: User = Depends(Authentication())):    """    引用添加    """    await UICaseMapper.add_choices(**steps.model_dump())    return Response.success()@router.post("/copy/common/steps", description="关联公共步骤 复制添加")async def copy_common_step(steps: ChoiceUICaseBaseSchema, _: User = Depends(Authentication())):    """    复制添加    """    await UICaseMapper.add_copy(**steps.model_dump())    return Response.success()@router.post('/execute/io', description='io执行')async def execute_io(info: ExecuteUICaseSchema, sr: User = Depends(Authentication())):    create_task(Player(UIStarter(sr)).run_case(info.caseId))    return Response.success()@router.post("/execute/back", description='后台执行')async def execute_back(info: ExecuteUICaseSchema, sr: User = Depends(Authentication())):    create_task(Player(UIStarter(sr)).run_case(info.caseId))    return Response.success()