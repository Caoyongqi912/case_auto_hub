#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/14# @Author : cyq# @File : config# @Software: PyCharm# @Desc:from fastapi import APIRouterfrom fastapi.params import Dependsfrom app.controller import Authenticationfrom app.mapper import Mapperfrom app.mapper.project.dbConfigMapper import DbConfigMapperfrom app.model.base import Userfrom app.response import Responsefrom app.schema.base import InsertDBConfigSchema, PageDBConfigSchema, SetByDBConfigIdSchemafrom app.schema.base.dbConfigSchema import TryDBConfigSchemafrom common.mysqlClient import logrouter = APIRouter(prefix="/project/config", tags=["项目配置"])DB_Exclude = {"db_username", "db_password", "db_port", "db_host",}@router.get("/queryTB", description="查询db表")async def query_db():    data = await Mapper.tables()    return Response.success(data)@router.post("/testConnect", description="查询db表")async def test_connect(dbInfo: InsertDBConfigSchema, _: User = Depends(Authentication())):    await DbConfigMapper.test_connect(**dbInfo.model_dump(exclude_none=True))    return Response.success()@router.post("/try", description="调用")async def try_db_script(dbInfo: TryDBConfigSchema, u: User = Depends(Authentication())):    data = await DbConfigMapper.try_script(**dbInfo.model_dump(),user=u)    return Response.success(data)@router.post("/insertDB", description="配置配置")async def insert_db(dbInfo: InsertDBConfigSchema, cr: User = Depends(Authentication())):    db = await  DbConfigMapper.save(        creatorUser=cr,        **dbInfo.model_dump()    )    return Response.success(db)@router.post("/updateDB", description="配置配置")async def updateDB(dbInfo: SetByDBConfigIdSchema, cr: User = Depends(Authentication())):    db = await  DbConfigMapper.update_by_uid(        updateUser=cr,        **dbInfo.model_dump(exclude_none=True, exclude_unset=True)    )    return Response.success(db)@router.post("/removeDB", description="配置配置")async def removeDB(dbInfo: SetByDBConfigIdSchema, _: User = Depends(Authentication())):    await  DbConfigMapper.delete_by_uid(dbInfo.uid)    return Response.success()@router.post("/pageDB", description="配置配置")async def page_db(dbInfo: PageDBConfigSchema, cr: User = Depends(Authentication())):    db = await  DbConfigMapper.page_query(**dbInfo.model_dump(exclude_none=True))    return Response.success(db, exclude=DB_Exclude)@router.get("/queryDB", description="配置配置")async def query_DB(_: User = Depends(Authentication())):    db = await  DbConfigMapper.query_all()    return Response.success(db, exclude=DB_Exclude)@router.get("/infoDB", description="配置信息")async def get_db(uid: str, _: User = Depends(Authentication())):    db = await  DbConfigMapper.get_by_uid(uid)    return Response.success(db)