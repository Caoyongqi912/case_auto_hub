from fastapi import APIRouter, Depends

from app.controller import Authentication
from app.mapper.project.moduleMapper import ModuleMapper
from app.model.base import User
from app.response import Response
from app.schema.base.module import InsertModuleSchema, UpdateModuleSchema, RemoveModuleSchema, DropModuleSchema

router = APIRouter(prefix="/module", tags=["模块"])


@router.post("/insert", description='添加模块')
async def insert_module(partInfo: InsertModuleSchema, creator: User = Depends(Authentication(isAdmin=True))):
    await ModuleMapper.save(
        creator_user=creator,
        **partInfo.model_dump()
    )
    return Response.success()


@router.post("/update", description='编辑')
async def update_module(partInfo: UpdateModuleSchema, ur: User = Depends(Authentication(isAdmin=True))):
    await ModuleMapper.update_by_id(
        updateUser=ur,
        **partInfo.model_dump()
    )
    return Response.success()


@router.post("/remove", description='删除')
async def remove_module(partInfo: RemoveModuleSchema, ur: User = Depends(Authentication(isAdmin=True))):
    await ModuleMapper.remove_module(partInfo.moduleId)
    return Response.success()


@router.post("/drop", description='删除')
async def drop_module(moduleInfo: DropModuleSchema, ur: User = Depends(Authentication(isAdmin=True))):
    await ModuleMapper.drop(**moduleInfo.model_dump())
    return Response.success()


@router.get("/queryTreeByProject", description="查询模块树")
async def tree_module(project_id: int, module_type: int, _=Depends(Authentication())):
    data = await ModuleMapper.query_tree_by(project_id=project_id, module_type=module_type)
    return Response.success(data)
