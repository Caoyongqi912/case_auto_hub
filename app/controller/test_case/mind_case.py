from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.test_case.mindcaseMapper import MindCaseMapper
from app.model.base import User
from app.response import Response
from app.schema.hub.testCaseSchema import InsertMindCaseSchema, UpdateMindCaseSchema, QueryMindCaseSchema

router = APIRouter(prefix="/hub/mindCase", tags=['用例'])


@router.post("/insert", description="添加脑图")
async def insert_case(data: InsertMindCaseSchema, user: User = Depends(Authentication())):
    """
    添加脑图

    - 按计划维度：传 plan_id（推荐，主入口）
    - 按需求维度：传 requirement_id（保留兼容老入口）
    """
    if not data.plan_id and not data.requirement_id:
        from app.exception import CommonError
        raise CommonError("plan_id 与 requirement_id 至少传一个")
    payload = data.model_dump(exclude_unset=True)
    data = await MindCaseMapper.save(
        creator_user=user,
        **payload
    )
    return Response.success(data)


@router.post("/update", description="修改脑图")
async def update_case(data: UpdateMindCaseSchema, user: User = Depends(Authentication())):
    data = await MindCaseMapper.update_by_id(
        update_user=user,
        **data.model_dump(exclude_none=True)
    )
    return Response.success(data)


@router.get("/detail", description="获取脑图详情")
async def case_detail(
    plan_id: int = None,
    requirement_id: int = None,
    _: User = Depends(Authentication()),
):
    """
    获取脑图详情

    - 同时传 plan_id + requirement_id 时 plan_id 优先
    - 仅传一个时按其维度查
    """
    query = QueryMindCaseSchema(plan_id=plan_id, requirement_id=requirement_id)
    if not query.plan_id and not query.requirement_id:
        from app.exception import CommonError
        raise CommonError("plan_id 与 requirement_id 至少传一个")
    data = await MindCaseMapper.get_by_plan_or_requirement(
        plan_id=query.plan_id,
        requirement_id=query.requirement_id,
    )
    return Response.success(data)
