#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/10
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc:
import os.path
import aiofiles

from fastapi import APIRouter, Form, UploadFile, File, Depends, Response as FastResponse
from pydantic import BaseModel, Field

from utils.fileManager import FileManager
from app.controller import Authentication
from app.mapper.file import FileMapper, fileMapper
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.model.base import User
from app.response import Response
from croe.interface.upload_file import FileReader

router = APIRouter(prefix="/file", tags=["文件管理"])


@router.get("/ui_case/uid={uid}")
async def get_ui_case_file(uid: str):
    return await render_response(uid)


@router.get("/avatar/uid={uid}")
async def get_ui_case_file(uid: str):
    return await render_response(uid)


@router.post("/interface/upload", description="上传")
async def upload_api(valueType: str = Form(...),  # 用 Form 来接受表单参数
                     project_id: str = Form(...),
                     module_id: str = Form(...),
                     env_id: str = Form(...),
                     api_file: UploadFile = File(...),  # 上传文件,
                     cr: User = Depends(Authentication())):
    """
    根据附件 上传 录入接口
    创建 目录
    创建 interface
    :param valueType:
    :param project_id:
    :param module_id:
    :param env_id:
    :param api_file:
    :param cr:
    :return:
    """
    content = await FileReader.readUploadFile(valueType, api_file)
    await InterfaceMapper.upload(project_id=project_id,
                                 module_id=module_id,
                                 env_id=env_id,
                                 creator=cr,
                                 apis=content)
    return Response.success(content)


@router.post("/interface/data/upload", description="上传")
async def upload_api_data(
        interfaceId: str = Form(...),
        data_file: UploadFile | None = File(None),  # 上传文件,
        _: User = Depends(Authentication())):
    if data_file is None:
        return Response.error("请上传文件")
    fileName = await FileMapper.insert_api_data_file(file=data_file, interface_uid=interfaceId)
    return Response.success(fileName)


class RemoveFile(BaseModel):
    file_id: str = Field(..., description="删除键")


@router.post("/interface/data/remove", description="上传")
async def upload_api_data(
        file: RemoveFile,
        _: User = Depends(Authentication())):
    await FileMapper.delete_api_data_file(file.file_id)
    return Response.success()


async def render_response(uid: str):
    file = await FileMapper.get_by_uid(uid)
    return FastResponse(
        content=await open_file(file.filePath),
        media_type=file.fileType
    )


async def open_file(filepath):
    if os.path.exists(filepath):
        async with  aiofiles.open(filepath, "rb") as f:
            return await f.read()
    return None
