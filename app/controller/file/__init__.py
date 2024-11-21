#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/10# @Author : cyq# @File : __init__.py# @Software: PyCharm# @Desc:from fastapi import APIRouter, Responsefrom app.mapper.file import FileMapperrouter = APIRouter(prefix="/file", tags=["文件管理"])@router.get("/ui_case/uid={uid}")async def get_ui_case_file(uid: str):    file = await FileMapper.get_by_uid(uid)    return Response(        content=open_file(file.filePath),        media_type=file.fileType    )def open_file(filepath):    with open(filepath, "rb") as f:        image = f.read()        return image