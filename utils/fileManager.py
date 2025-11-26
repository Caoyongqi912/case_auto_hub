import csv
import os
from typing import AnyStr, NoReturn, List, Dict, Any
from fastapi import UploadFile
from app.mapper.file import FileMapper
from app.model.base import User
from common.locust_client.perf_file import PerfPath
from config import Config
from utils import GenerateTools, log
from file import current_dir as file_path
from queue import Queue
import aiofiles

AVATAR = os.path.join(file_path, "avatar")
API_DATA = os.path.join(file_path, "api_data")


def verify_dir(_path: str):
    if not os.path.exists(_path):
        os.makedirs(_path)


class FileManager:
    # 头像

    @staticmethod
    async def save_data_file(file: UploadFile, interfaceId: str):
        """
        接口请求form 附件保存
        """
        verify_dir(API_DATA)
        fileName = f"{interfaceId}_{file.filename}"
        filePath = os.path.join(API_DATA, fileName)
        async with aiofiles.open(filePath, "wb") as buffer:
            await buffer.write(await file.read())
        return fileName

    @staticmethod
    async def save_perf_file(file: UploadFile, interfaceId: str):
        """
        接口性能参数文件
        """
        fileName = f"{interfaceId}_{file.filename}"
        filePath = os.path.join(PerfPath, fileName)
        async with aiofiles.open(filePath, "wb") as buffer:
            await buffer.write(await file.read())
        return fileName

    @staticmethod
    async def save_avatar(file: UploadFile, user: User):
        """
        头像存本地
        路径存file table
        url 存user
        更新
        删除本地原来
        删除file table
        重新存
        """
        verify_dir(AVATAR)
        if user.avatar:
            await FileMapper.remove_file(user.avatar.split("uid=")[-1])

        fileName = GenerateTools.uid()
        fileType = file.content_type
        filePath = os.path.join(AVATAR, fileName)
        async with aiofiles.open(filePath, "wb") as buffer:
            await buffer.write(await file.read())

        file_model = await FileMapper.save(**dict(
            fileType=fileType,
            filePath=filePath,
            fileName=fileName
        ))
        avatar_PATH = Config.FILE_AVATAR_PATH + file_model.uid
        from app.mapper.user import UserMapper
        await UserMapper.set_avatar(avatar_PATH, user)

    @staticmethod
    def delFile(path: AnyStr):
        """
        delAvatar
        :param path: 绝对路径
        :return:
        """
        if os.path.exists(path):
            os.remove(path)

    @staticmethod
    async def reader(path: str):
        async with  aiofiles.open(path, "rb") as f:
            return await f.read()

    @staticmethod
    def file_reader_for_perf(fileName: str, q: bool = False) -> Queue[Dict[str, Any]] | List[Dict[str, str]]:
        """
        读取CSV格式的文本文件并转换为字典列表

        示例输入文件内容：
        username,password
        admin,123
        hah,222

        返回：
        [{'username': 'admin', 'password': '123'}, {'username': 'hah', 'password': '222'}]

        Args:
            fileName: 文件路径
            q:是否返回queue

        Returns:
            包含字典的列表，每个字典代表一行数据
        """
        data = []

        try:
            filePath = os.path.join(PerfPath, fileName)
            with open(filePath, "r", encoding="utf-8") as f:
                # 使用csv模块更安全地处理CSV文件
                reader = csv.DictReader(f)
                if q:
                    data = Queue()
                    for row in reader:
                        data.put(row)
                else:
                    data = [row for row in reader]

        except FileNotFoundError:
            raise FileNotFoundError(f"文件 {fileName} 不存在")
        except Exception as e:
            raise Exception(f"读取文件时出错: {str(e)}")

        return data
