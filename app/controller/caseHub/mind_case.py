from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.caseHub.mindcaseMapper import MindCaseMapper
from app.model.base import User
from app.response import Response
from app.schema.hub.testCaseSchema import InsertMindCaseSchema

router = APIRouter(prefix="/hub/mindCase", tags=['用例'])


@router.post("/insert", description="添加用例")
async def insert_case(data: InsertMindCaseSchema, user: User = Depends(Authentication())):
    data = await MindCaseMapper.save(
        creator_user=user,
        **data.model_dump()
    )
    return Response.success(data)


@router.get("/detail", description="添加用例")
async def case_detail(case_id: int, _: User = Depends(Authentication())):
    data = await MindCaseMapper.get_by_id(case_id)
    return Response.success(data)
