#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceMapper
# @Software: PyCharm
# @Desc: 接口 Mapper - 处理接口的 CRUD 操作

import asyncio
import os
from typing import List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.mapper.project.moduleMapper import ModuleMapper
from app.model.base import User
from app.model.base.module import Module
from app.model.interfaceAPIModel.interfaceModel import Interface
from app.mapper.interfaceApi.dynamicMapper import InterfaceDynamicMapper
from enums import ModuleEnum, InterfaceRequestTBodyTypeEnum
from utils import log
from utils.fileManager import API_DATA

__all__ = [
    "InterfaceMapper"
]



class InterfaceMapper(Mapper[Interface]):
    """
    接口 Mapper
    
    提供接口的增删改查、复制、批量导入等功能
    """
    __model__ = Interface

    @classmethod
    async def create_interface(cls, user: User, **kwargs) -> Interface:
        """
        创建接口

        Args:
            user: 创建用户
            **kwargs: 接口属性

        Returns:
            Interface: 创建的接口实例
        """
        try:
            async with cls.transaction() as session:
                interface = await cls.save(
                    creator_user=user,
                    session=session,
                    **kwargs
                )
                await InterfaceDynamicMapper.new_dynamic(
                    entity_name=interface.interface_name,
                    entity_id=interface.id,
                    session=session,
                    user=user
                )
                return interface
        except Exception as e:
            log.error(f"create_interface error: {e}")
            raise

    @classmethod
    async def update_interface(cls, user: User, interface_id: int, **kwargs) -> Interface:
        """
        更新接口

        Args:
            user: 更新用户
            interface_id: 接口 ID
            **kwargs: 更新属性

        Returns:
            Interface: 更新后的接口实例
        """
        try:
            async with cls.transaction() as session:
                old_interface = await cls.get_by_id(ident=interface_id, session=session)
                new_interface = await cls.update_by_id(
                    session=session,
                    update_user=user,
                    **kwargs
                )
                await InterfaceDynamicMapper.append_dynamic(
                    entity_id=interface_id,
                    user=user,
                    old_info=old_interface.to_dict(),
                    new_info=new_interface.to_dict(),
                    session=session
                )
                return new_interface
        except Exception as e:
            log.error(f"update_interface error: {e}")
            raise

    @classmethod
    async def association_empty_interface(
        cls,
        module_id: int,
        project_id: int,
        user: User,
        session: AsyncSession
    ) -> Interface:
        """
        创建空白接口模板

        Args:
            module_id: 模块 ID
            project_id: 项目 ID
            user: 创建用户
            session: 数据库会话

        Returns:
            Interface: 空白接口实例
        """
        interface = cls.__model__(
            interface_name="API名称",
            interface_desc="API描述",
            interface_status="DEBUG",
            interface_level="P2",
            interface_url="/",
            interface_method="GET",
            interface_body_type=0,
            is_common=0,
            module_id=module_id,
            project_id=project_id,
            creator=user.id,
            creatorName=user.username
        )
        return await cls.add_flush_expunge(session=session, model=interface)

    @classmethod
    async def remove_interface(cls, interface_id: int) -> None:
        """
        删除接口

        异步删除关联文件，不阻塞主流程

        Args:
            interface_id: 接口 ID
        """
        try:
            async with cls.transaction() as session:
                interface = await cls.get_by_id(ident=interface_id, session=session)
                
                # 异步执行文件清理，不阻塞数据库操作
                async_remove_files(interface)
                
                await session.delete(interface)
        except Exception as e:
            log.error(f"remove_interface error: {e}")
            raise



    @classmethod
    async def remove_self_interface(cls,interface_id:int)->bool:
        """
        删除接口关联的文件

        Args:
            interface_id: 接口 ID

        Returns:
            bool: 是否删除成功
        """
        try:
            interface = await InterfaceMapper.get_by_id(
            ident=interface_id, session=session
        )
            if not interface:
                return False

            if interface.is_common:
                return False

            await session.delete(interface)
            return True
        except Exception as e:
            log.error(f"remove_self_interface error: {e}")
            raise
    
    @classmethod
    async def copy_interface(
        cls,
        interface_id: int,
        user: User,
        copy_name: bool = False,
        is_common: bool = False
    ) -> Interface:
        """
        复制接口

        Args:
            interface_id: 源接口 ID
            user: 操作用户
            copy_name: 是否复制名称（False 则添加"副本"后缀）
            is_common: 是否设为公共接口

        Returns:
            Interface: 复制后的接口实例
        """
        try:
            async with cls.transaction() as session:
                target_api = await cls.get_by_id(ident=interface_id, session=session)
                target_api_map = target_api.copy_map()
                
                if not copy_name:
                    target_api_map['interface_name'] = f"{target_api_map['interface_name']}(副本)"
                
                new_interface = cls.__model__(**target_api_map)
                new_interface.creator = user.id
                new_interface.creatorName = user.username
                new_interface.is_common = is_common
                
                return await cls.add_flush_expunge(session, new_interface)
        except Exception as e:
            log.error(f"copy_interface error: {e}")
            raise

    
    
    @classmethod
    async def copy_interface_with_entity(
        cls,
        interface: Interface,
        user: User,
        copy_name: bool = False,
        is_common: bool = False
    ) -> Interface:
        """
        复制接口

        Args:
            interface_id: 源接口 ID
            user: 操作用户
            copy_name: 是否复制名称（False 则添加"副本"后缀）
            is_common: 是否设为公共接口

        Returns:
            Interface: 复制后的接口实例
        """
        try:
            target_api_map = interface.copy_map()
            
            if not copy_name:
                target_api_map['interface_name'] = f"{target_api_map['interface_name']}(副本)"
            
            new_interface = cls.__model__(**target_api_map)
            new_interface.creator = user.id
            new_interface.creatorName = user.username
            new_interface.is_common = is_common
            
            return await cls.add_flush_expunge(session, new_interface)
        except Exception as e:
            log.error(f"copy_interface_with_entity error: {e}")
            raise


    # ==================== 批量导入 ====================

    @classmethod
    async def upload(
        cls,
        apis: List[Dict[str, Any]],
        project_id: str,
        module_id: str,
        env_id: str,
        creator: User
    ) -> None:
        """
        批量上传接口

        Args:
            apis: 接口数据列表
            project_id: 项目 ID
            module_id: 父模块 ID
            env_id: 环境 ID
            creator: 创建者
        """
        try:
            async with cls.transaction() as session:
                module_names = [api.pop("module") for api in apis]
                module_map = {}
                
                for name in set(module_names):
                    mid = await cls._get_or_create_module(
                        name, session, int(module_id), int(project_id), creator
                    )
                    module_map[name] = mid
                
                tasks = [
                    cls._batch_insert_apis(
                        session, int(project_id), int(env_id),
                        module_map[module_names[idx]], creator, api["data"]
                    )
                    for idx, api in enumerate(apis)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log.error(f"upload error: {e}")
            raise

    @classmethod
    async def _batch_insert_apis(
        cls,
        session: AsyncSession,
        project_id: int,
        env_id: int,
        module_id: int,
        creator: User,
        data: List[Dict[str, Any]]
    ) -> None:
        """
        批量插入接口数据

        Args:
            session: 数据库会话
            project_id: 项目 ID
            env_id: 环境 ID
            module_id: 模块 ID
            creator: 创建者
            data: 接口数据列表
        """
        try:
            for api_data in data:
                api_data.update({
                    "project_id": project_id,
                    "env_id": env_id,
                    "module_id": module_id,
                    "creator": creator.id,
                    "creatorName": creator.username,
                    "interface_status": "DEBUG",
                    "interface_level": "P1",
                })
                session.add(Interface(**api_data))
        except Exception as e:
            log.error(f"_batch_insert_apis error: {e}")
            raise

    @classmethod
    async def _get_or_create_module(
        cls,
        module_name: str,
        session: AsyncSession,
        parent_id: int,
        project_id: int,
        creator: User
    ) -> int:
        """
        获取或创建模块

        Args:
            module_name: 模块名称
            session: 数据库会话
            parent_id: 父模块 ID
            project_id: 项目 ID
            creator: 创建者

        Returns:
            int: 模块 ID
        """
        try:
            result = await session.execute(
                select(Module).where(
                    and_(
                        Module.project_id == parent_id,
                        Module.title == module_name,
                        Module.module_type == ModuleEnum.API
                    )
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing and module_name == existing.title:
                log.debug(f"模块 '{module_name}' 已存在")
                return existing.id
            
            new_module = Module(
                title=module_name,
                project_id=project_id,
                parent_id=parent_id,
                creator=creator.id,
                creatorName=creator.username
            )
            session.add(new_module)
            await session.flush()
            return new_module.id
        except Exception as e:
            log.error(f"_get_or_create_module error: {e}")
            raise


class FileManager:
    """
    文件管理器
    
    处理接口关联文件的上传、删除等操作
    """

    @staticmethod
    def remove_api_files_safely(interface: Interface) -> None:
        """
        安全删除接口关联文件（忽略所有异常）

        Args:
            interface: 接口实例
        """
        try:
            FileManager._remove_files(interface)
        except Exception as e:
            log.warning(f"删除接口文件失败 (interface_id={interface.id}): {e}")

    @staticmethod
    def remove_api_files(interface: Interface) -> None:
        """
        删除接口关联文件

        Args:
            interface: 接口实例
        """
        FileManager._remove_files(interface)

    @staticmethod
    def _remove_files(interface: Interface) -> None:
        """
        执行文件删除逻辑

        Args:
            interface: 接口实例
        """
        api_datas = interface.interface_data
        uid_prefix = f"{interface.uid}_"
        
        if api_datas and interface.interface_body_type == InterfaceRequestTBodyTypeEnum.Data:
            for data in api_datas:
                value = data.get("value")
                if value and uid_prefix in value:
                    FileManager._safe_remove_file(value)
        
        FileManager._cleanup_uid_directories(uid_prefix)

    @staticmethod
    def update_api_files(interface: Interface) -> None:
        """
        更新接口关联文件（先删除旧文件）

        Args:
            interface: 接口实例
        """
        api_datas = interface.interface_data
        uid_prefix = f"{interface.uid}_"
        
        if api_datas and interface.interface_body_type == InterfaceRequestTBodyTypeEnum.Data:
            for data in api_datas:
                value = data.get("value")
                if value and uid_prefix in value:
                    FileManager._safe_remove_file(value)
        else:
            FileManager._cleanup_uid_directories(uid_prefix)

    @staticmethod
    def _safe_remove_file(filename: str) -> bool:
        """
        安全删除文件

        Args:
            filename: 文件名

        Returns:
            bool: 是否删除成功
        """
        filepath = os.path.join(API_DATA, filename)
        
        if not os.path.abspath(filepath).startswith(os.path.abspath(API_DATA)):
            log.warning(f"非法路径尝试: {filepath}")
            return False
        
        try:
            if os.path.exists(filepath) and os.path.isfile(filepath):
                os.remove(filepath)
                log.info(f"删除文件成功: {filepath}")
                return True
        except Exception as e:
            log.error(f"删除文件失败: {filepath}, {e}")
        
        return False

    @staticmethod
    def _cleanup_uid_directories(uid_prefix: str) -> None:
        """
        清理以指定前缀开头的目录

        Args:
            uid_prefix: UID 前缀
        """
        if not os.path.exists(API_DATA):
            return
        
        try:
            for dir_name in os.listdir(API_DATA):
                if dir_name.startswith(uid_prefix):
                    dir_path = os.path.join(API_DATA, dir_name)
                    if os.path.isdir(dir_path):
                        os.rmdir(dir_path)
                        log.info(f"删除目录成功: {dir_path}")
        except Exception as e:
            log.error(f"清理目录失败: {e}")


def async_remove_files( interface: Interface) -> None:
    """
    异步清理接口关联文件（后台任务）

    使用 ThreadPoolHelper 执行文件删除，不阻塞主流程

    Args:
        interface: 接口实例
    """
    from utils.threadPool import ThreadPoolHelper

    # 文件清理线程池
    _file_cleaner = ThreadPoolHelper(workers=4)
    loop = asyncio.get_event_loop()
    _file_cleaner.run_in_exe(loop, FileManager.remove_api_files_safely, interface)