#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/20# @Author : cyq# @File : part# @Software: PyCharm# @Desc:from fastapi import APIRouterfrom fastapi.params import Dependsfrom app.controller import Authenticationfrom app.model.base import Userfrom app.response import Responsefrom app.mapper.project.projectPart import ProjectPartMapperfrom app.schema.base import InsertPartSchemafrom app.schema.base.part import DropPartSchema, DeletePartSchemarouter = APIRouter(prefix="/part", tags=["模块"])@router.post("/insert", description='添加模块')async def insert_part(partInfo: InsertPartSchema, creator: User = Depends(Authentication(isAdmin=True))):    await ProjectPartMapper.save(        creatorUser=creator,        **partInfo.dict(            exclude_unset=True        )    )    return Response.success()@router.post("/remove", description='删除')async def remove_part(info: DeletePartSchema, creator: User = Depends(Authentication(isAdmin=True))):    await ProjectPartMapper.remove_part(        info.partId    )    return Response.success()@router.get("/queryTreeByProject", description="查询模块树")async def tree_part(projectId: int, _=Depends(Authentication())):    data = await ProjectPartMapper.query_by(projectID=projectId)    return Response.success(data)@router.get("/query", description="查询所有模块", )async def query_project(_: User = Depends(Authentication(True))):    """    查询所有模块    :return:    """    ps = await ProjectPartMapper.query_all()    return Response.success(ps)@router.get("/queryPartByProjectId")async def query_part_by_project_id(projectId: int, _: User = Depends(Authentication(True))):    """    根据项目id查询所有模块    返回树接口    :param projectId: 项目ID    :return:    """    ps = await ProjectPartMapper.query_by(projectID=projectId)    return Response.success(ps)@router.get("/queryRootPartByProjectId")async def query_root_part_by_project_id(projectId: int, _: User = Depends(Authentication(True))):    """    根据项目id查询root模块    返回树接口    :param projectId: 项目ID    :return:    """    ps = await ProjectPartMapper.query_parent_part_by_projectId(projectId)    return Response.success(ps)@router.post("/drop")async def query_root_part_by_project_id(dropInfo: DropPartSchema, _: User = Depends(Authentication(True))):    """    根据项目id查询root模块    返回树接口    :param dropInfo: 项目ID    :return:    """    await ProjectPartMapper.drop(**dropInfo.dict())    return Response.success()