#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/11/20
# @Author : cyq
# @File : interfaceResult
# @Software: PyCharm
# @Desc:

from fastapi import APIRouter
from fastapi.params import Depends

from app.controller import Authentication
from app.response import Response
from app.mapper.interfaceApi.interfaceResultMapper import InterfaceResultMapper, InterfaceTaskResultMapper, \
    InterfaceCaseResultMapper, InterfaceContentStepResultMapper
from app.schema.api.interfaceResultSchema import PageInterfaceCaseResultSchema, PageInterfaceResultSchema, \
    PageInterfaceTaskResultSchema, QueryCaseStepResultSchema
from utils import log

router = APIRouter(prefix="/interfaceResult", tags=['自动化接口接结果'])


@router.post("/pageCaseResult", description="用例case结果分页")
async def case_interface_page_results_page(page_info: PageInterfaceCaseResultSchema, _=Depends(Authentication)):
    data = await InterfaceCaseResultMapper.page_query(**page_info.model_dump(
        exclude_none=True,
        exclude_unset=True,
    ))
    return Response.success(data)


@router.get("/removeCaseResults", description="删除单个用例结果")
async def remove_case_result(case_id: int, _=Depends(Authentication())):
    await InterfaceCaseResultMapper.delete_by(interface_case_id=case_id)
    return Response.success()


@router.get("/detail/{result_id}", description="获取结果详情")
async def interface_detail(result_id: int, _=Depends(Authentication())):
    detail = await InterfaceCaseResultMapper.get_by_id(result_id)
    return Response.success(detail)


@router.get("/queryStepResult", description="接口结果字段查询")
async def query_step_results(case_result_id: int, _=Depends(Authentication())):
    data = await InterfaceContentStepResultMapper.query_steps_result(case_result_id)
    log.debug(data)
    return Response.success(data)





# ===== task result =====
@router.post('/task/pageResults',description="任务结果分页查询")
async def page_task_result(page_info: PageInterfaceTaskResultSchema, _=Depends(Authentication())):
    data = await InterfaceTaskResultMapper.page_query(**page_info.model_dump(
        exclude_none=True,
        exclude_unset=True,
    ))

    return Response.success(data)


@router.get('/task/removeResults',description="任务结果分页查询")
async def remove_task_result(task_id: int, _=Depends(Authentication())):
    await InterfaceTaskResultMapper.delete_by(task_id=task_id)
    return Response.success()


@router.get('/task/resultDetail',description="任务结果分页查询")
async def get_task_result(task_result_id: int, _=Depends(Authentication())):
    data = await InterfaceTaskResultMapper.get_by_id(ident=task_result_id)
    return Response.success(data)


@router.post('/task/interface/pageResult',description='查询任务关联api结果')
async def page_task_interface_results(page_info: PageInterfaceResultSchema, _=Depends(Authentication())):
    data = await InterfaceResultMapper.page_query(**page_info.model_dump(
        exclude_none=True,
        exclude_unset=True,
    ))
    return Response.success(data)



@router.post("/queryBy", description="接口结果字段查询")
async def query_interface_api_result(queryBy, _=Depends(Authentication())):
    results = await InterfaceResultMapper.query_by(**queryBy.model_dump(
        exclude_unset=True,
        exclude_none=True,
    ))
    return Response.success(results)





@router.get("/task/removeResult", description="删除结果")
async def remove_task_result(result_id:int, _=Depends(Authentication())):
    await InterfaceTaskResultMapper.delete_by_id(ident=result_id)
    return Response.success()