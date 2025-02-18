#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/14# @Author : cyq# @File : config# @Software: PyCharm# @Desc:from fastapi import APIRouterfrom fastapi.params import Dependsfrom app.controller import Authenticationfrom app.mapper import Mapperfrom app.mapper.project.dbConfigMapper import DbConfigMapperfrom app.model.base import Userfrom app.response import Responsefrom app.schema.base import InsertDBConfigSchema, PageDBConfigSchema, SetByDBConfigIdSchemarouter = APIRouter(prefix="/project/config", tags=["项目配置"])@router.get("/queryTB", description="查询db表")async def query_db():    data = await Mapper.tables()    return Response.success(data)@router.post("/insertDB", description="配置配置")async def insert_db(dbInfo: InsertDBConfigSchema, cr: User = Depends(Authentication())):    db = await  DbConfigMapper.save(        creatorUser=cr,        **dbInfo.dict()    )    return Response.success(db)@router.post("/updateDB", description="配置配置")async def updateDB(dbInfo: SetByDBConfigIdSchema, cr: User = Depends(Authentication())):    db = await  DbConfigMapper.update_by_id(        updateUser=cr,        **dbInfo.dict()    )    return Response.success(db)@router.post("/pageDB", description="配置配置")async def page_db(dbInfo: PageDBConfigSchema, cr: User = Depends(Authentication())):    db = await  DbConfigMapper.page_query(**dbInfo.dict(exclude_none=True))    return Response.success(db)@router.get("/queryDB", description="配置配置")async def query_DB(_: User = Depends(Authentication())):    db = await  DbConfigMapper.query_all()    return Response.success(db)