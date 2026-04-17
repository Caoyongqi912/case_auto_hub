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
async def case_interface_page_results_page(pageinfo: PageInterfaceCaseResultSchema, _=Depends(Authentication)):
    data = await InterfaceCaseResultMapper.page_query(**pageinfo.model_dump(
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


@router.post("/queryBy", description="接口结果字段查询")
async def query_interface_api_result(queryBy, _=Depends(Authentication())):
    results = await InterfaceResultMapper.query_by(**queryBy.model_dump(
        exclude_unset=True,
        exclude_none=True,
    ))
    return Response.success(results)


@router.get("/queryByCaseResultId", description="接口结果字段查询")
async def query_interface_api_result_by_case_result(caseResultId: int, _=Depends(Authentication())):
    return Response.success()


@router.post("/case/queryBy", description="查询用例结果")
async def case_interface_api_results(byInfo, _=Depends(Authentication())):
    return Response.success()


@router.get("/case/detail/{uid}", description="查询用例结果")
async def case_interface_api_result(uid: int, _=Depends(Authentication())):
    return Response.success()


@router.post("/case/removeAll", description="删除全部用例结果")
async def remove_all_case_interface_api_result(result, _=Depends(Authentication())):
    return Response.success()


@router.post("/inter/page", description="用例api结果分页")
async def api_interface_page_results_page(pageinfo, _=Depends(Authentication)):
    return Response.success()


@router.get("/task/resultDetail", description="任务详情")
async def get_task_detail_result(result=Depends(), _=Depends(Authentication())):
    return Response.success()


@router.post("/task/removeAll", description="删除全部用例结果")
async def remove_all_case_interface_api_result(result, _=Depends(Authentication())):
    return Response.success()
