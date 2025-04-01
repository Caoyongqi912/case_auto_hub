#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/1/2# @Author : cyq# @File : interfaceRecord# @Software: PyCharm# @Desc:from binascii import a2b_uufrom fastapi import APIRouter, Depends, Requestfrom app.controller import Authenticationfrom app.mapper.interface import InterfaceMapper, InterfaceCaseMapperfrom app.response import Responsefrom app.schema.interface import RecordingSchemafrom app.schema.interface.interfaceApiSchema import SaveRecordSchema, SaveRecordToCaseSchemafrom interface.recoder import Recordfrom utils import MyLoguruLOG = MyLoguru().get_logger()router = APIRouter(prefix="/interfaceRecord", tags=['自动化接口步骤'])@router.post("/start/recording")async def start_recording(req: Request, recordInfo: RecordingSchema, auth=Depends(Authentication())):    key_name = f"{req.client.host}"    await Record.start_record(key_name=key_name,                              recordInfo={"uid": auth.uid, **recordInfo.model_dump()})    return Response.success()@router.post("/clear/recording")async def clear_recording(req: Request, auth=Depends(Authentication())):    await Record.clear_record(ip=req.client.host, uid=auth.uid)    return Response.success()@router.get("/query/record", description="获取录制")async def query_record(auth=Depends(Authentication())):    """查询录制"""    from config import Config    if Config.Record_Proxy:        data = await Record.query_record(auth.uid)        return Response.success(data)    else:        return Response.success(data=[])@router.post("/record/save2api", description="保存录制到api")async def save_record_to_api(inter: SaveRecordSchema, auth=Depends(Authentication())):    """保存录制"""    await InterfaceMapper.save_record(        creatorUser=auth,        **inter.model_dump()    )    return Response.success()@router.post("/record/save2case", description="保存录制到case")async def append_record_to_case(inter: SaveRecordToCaseSchema, auth=Depends(Authentication())):    """保存录制"""    await InterfaceCaseMapper.append_record(        creatorUser=auth,        **inter.model_dump()    )    return Response.success()@router.post("/record/deduplication", description="删除录制")async def deduplication_record(auth=Depends(Authentication())):    """录制去重复"""    await Record.deduplication(auth.uid)    return Response.success()