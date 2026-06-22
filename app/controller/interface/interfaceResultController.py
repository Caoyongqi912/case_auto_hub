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
import json
from common import rc
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


# queryStepResult 使用 Redis 5s 缓存加速，写步骤时主动清除缓存。
# 本地内存缓存无法跨 uvicorn worker 共享，Redis 已在项目中使用。
STEP_RESULT_CACHE_PREFIX = "result:steps:"
STEP_RESULT_CACHE_TTL = 5  # 5 second, enough for one UI interaction cycle, not too long for stale data


async def _invalidate_step_result_cache(case_result_id: int) -> None:
    """Write path: clear the cache for this case_result_id. Best-effort."""
    try:
        if rc.r is None:
            await rc.init_pool()
        await rc.r.delete(f"{STEP_RESULT_CACHE_PREFIX}{case_result_id}")
    except Exception:
        log.exception(f"clear step result cache failed: case_result_id={case_result_id}")


@router.get("/queryStepResult", description="接口结果字段查询")
async def query_step_results(case_result_id: int, _=Depends(Authentication())):
    """查询 case 所有 step 结果 (Redis 5s 缓存 + 写时 invalidation)."""
    cache_key = f"{STEP_RESULT_CACHE_PREFIX}{case_result_id}"
    try:
        if rc.r is None:
            await rc.init_pool()
        cached = await rc.r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        log.exception(f"step result cache read failed: case_result_id={case_result_id}")

    data = await InterfaceContentStepResultMapper.query_steps_result(case_result_id)
    log.debug(data)
    out = Response.success(data)

    try:
        if rc.r is None:
            await rc.init_pool()
        await rc.r.set(cache_key, json.dumps(out), ex=STEP_RESULT_CACHE_TTL)
    except Exception:
        log.exception(f"step result cache write failed: case_result_id={case_result_id}")

    return out





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