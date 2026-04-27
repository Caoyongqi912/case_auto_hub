#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/10
# @Author : cyq
# @File : fileMapper
# @Software: PyCharm
# @Desc:
from typing import Union

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.mapper import Mapper
from app.model.base import FileModel
from app.model import async_session
from utils import log


class FileMapper(Mapper[FileModel]):
    __model__ = FileModel

    @classmethod
    async def remove_file(cls, uid: str, session: AsyncSession = None):
        """
        删除本地文件
        """
        try:
            # 说明是 clear_case_result  传递过来的 不判断是否存在
            if session:
                file = await cls.get_by_uid(uid.strip(), session=session, raise_error=False)

            else:
                async with async_session() as session:
                    async with session.begin():
                        log.debug(f"删除文件 {uid}")
                        file = await cls.get_by_uid(uid.strip(), session=session)
            if file:
                path = file.file_path
                await session.delete(file)
                from utils.fileManager import FileManager
                FileManager.delFile(path)
                log.debug(f"删除 {path}")
        except Exception as e:
            raise e

    @classmethod
    async def insert_file(cls, filePath: Union[str], fileName: str) -> FileModel:
        try:
            async with async_session() as session:
                async with session.begin():
                    file = FileModel(
                        file_type="image/jpeg",
                        file_path=filePath,
                        file_name=fileName
                    )
                    await cls.add_flush_expunge(session, file)
                    return file
        except Exception as e:
            log.error(e)
            raise e

    @classmethod
    async def insert_api_data_file(cls, file: UploadFile, interface_uid: str):
        try:
            from utils.fileManager import FileManager

            file_name, file_path = await FileManager.save_data_file(file, interface_uid)
            async with cls.transaction() as session:
                file = FileModel(
                    file_type=file.content_type,
                    file_path=file_path,
                    file_name=file_name,
                    interface_uid=interface_uid
                )
                await cls.add_flush_expunge(session, file)
                return file
        except Exception as e:
            raise e

    @classmethod
    async def delete_api_data_file(cls, uid: str):
        from utils.fileManager import FileManager

        try:
            async with cls.transaction() as session:
                file = await cls.get_by_uid(uid.strip(), session=session, raise_error=False)
                file_path = file.file_path
                await session.delete(file)
                FileManager.delFile(file_path)
        except Exception as e:
            raise e