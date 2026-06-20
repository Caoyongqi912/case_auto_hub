#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/10
# @Author : cyq
# @File : fileMapper
# @Software: PyCharm
# @Desc:
from typing import Union

from config import Config
from fastapi import UploadFile
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.mapper import Mapper
from app.model.base import FileModel, User
from utils import log


class FileMapper(Mapper[FileModel]):
    __model__ = FileModel

    @classmethod
    async def remove_file(cls, uid: str, session: AsyncSession = None):
        """
        删除本地文件
        """
        path = None
        try:
            async with cls.session_scope(session=session) as session:
                async with session.begin():
                    file = await cls.get_by_uid(uid.strip(), session=session, raise_error=False)
                    if file:
                        path = file.file_path
                        await session.delete(file)
            # DB commit 后再删物理文件，避免 DB 回滚但文件已丢
            if path:
                from utils.fileManager import FileManager
                FileManager.delFile(path)
                log.debug(f"删除 {path}")
        except Exception as e:
            raise
    @classmethod
    async def insert_file(cls, filePath: Union[str], fileName: str) -> FileModel:
        try:
            async with cls.transaction() as session:
                file = FileModel(
                    file_type="image/jpeg",
                    file_path=filePath,
                    file_name=fileName
                )
                await cls.add_flush_expunge(session, file)
                return file
        except Exception as e:
            log.exception(f"error: {e}")
            raise
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
            raise
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
            raise
    @classmethod
    async def save_avatar(cls,avatar: UploadFile,user:User):
        from utils.fileManager import FileManager

        try:
            async with cls.transaction() as session:
                avatar_path = user.avatar.split("uid=")[-1]
                await cls.remove_file(avatar_path, session)


                file_name,file_path = await FileManager.save_avatar(avatar)

                new_avatar = await cls.save(
                    session=session,
                    creator_user=user,
                    file_name=file_name,
                    file_path=file_path,
                    file_type=avatar.content_type
                )
                await session.execute(
                    update(User).where(User.id == user.id).values(avatar=Config.FILE_AVATAR_PATH + new_avatar.uid)
                )
        except Exception as e:
            raise