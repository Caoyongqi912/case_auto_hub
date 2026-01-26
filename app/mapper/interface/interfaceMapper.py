#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/11/20
# @Author : cyq
# @File : interfaceMapper
# @Software: PyCharm
# @Desc: 接口相关的Mapper实现
import asyncio
import os
from typing import List, Dict, Any, Optional

from sqlalchemy import select, insert, and_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.mapper.interface.interfaceGroupMapper import InterfaceGroupMapper
from app.mapper.project.moduleMapper import ModuleMapper
from app.model import async_session
from app.model.base import User
from app.model.base.module import Module
from app.model.interface import InterfaceModel, InterFaceCaseModel
from app.model.interface.InterfaceCaseStepContent import InterfaceCondition, InterfaceCaseStepContent
from app.model.interface.association import ConditionAPIAssociation, InterfaceCaseStepContentAssociation
from app.model.interface.interfaceScriptDescModel import InterfaceScriptDesc
from enums import ModuleEnum
from enums.CaseEnum import CaseStepContentType
from croe.interface.recoder import Record
from utils import MyLoguru
from utils.fileManager import API_DATA


log = MyLoguru().get_logger()


class LastIndexHelper:
    """索引查询辅助类"""

    @staticmethod
    async def get_condition_apis_last_index(api_id: int, session: AsyncSession) -> int:
        """
        查询条件子步骤最后的索引
        :param api_id: API ID
        :param session: 会话对象
        :return: 最后索引值
        """
        stmt = select(ConditionAPIAssociation.step_order).where(
            ConditionAPIAssociation.api_id == api_id
        ).order_by(
            ConditionAPIAssociation.step_order.desc()
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar() or 0


class FileManager:
    """文件管理辅助类"""

    @staticmethod
    def remove_api_files(api: InterfaceModel):
        """
        删除API相关的文件
        :param api: API模型实例
        """
        api_datas = api.data
        if api_datas and api.body_type == 2:
            for data in api_datas:
                if data.get("value") and f"{api.uid}_" in data.get("value"):
                    filepath = os.path.join(API_DATA, data.get('value'))
                    # 确保文件存在并可读
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        log.info(f"删除文件成功: {filepath}")

    @staticmethod
    def update_api_files(api: InterfaceModel):
        """
        更新API相关的文件
        :param api: API模型实例
        """
        api_datas = api.data

        if api_datas and api.body_type == 2:
            for data in api_datas:
                value = data.get("value")
                if value and f"{api.uid}_" in value:
                    filepath = os.path.join(API_DATA, value)
                    # 校验路径是否合法
                    if not os.path.abspath(filepath).startswith(os.path.abspath(API_DATA)):
                        log.error(f"非法路径尝试: {filepath}")
                        continue

                    try:
                        # 确保文件存在并可读
                        if os.path.exists(filepath) and os.path.isfile(filepath):
                            os.remove(filepath)
                            log.info(f"删除文件成功: {filepath}")
                    except Exception as e:
                        log.error(f"删除文件失败: {filepath}, 错误信息: {e}")

        elif not api_datas:
            # 如果 data 为空，删除以 api.uid_* 开头的目录
            try:
                if not os.path.exists(API_DATA):
                    return
                for dir_name in os.listdir(API_DATA):
                    if dir_name.startswith(f"{api.uid}_"):
                        dir_path = os.path.join(API_DATA, dir_name)
                        if os.path.isdir(dir_path):
                            os.rmdir(dir_path)  # 删除空目录
                            log.info(f"删除目录成功: {dir_path}")
            except Exception as e:
                log.error(f"删除目录失败: {e}")

        else:
            # 如果 data 不存在，删除对应的目录
            target_dir = os.path.join(API_DATA, f"{api.uid}_*")
            if not os.path.exists(target_dir):
                return
            if os.path.exists(target_dir) and os.path.isdir(target_dir):
                try:
                    os.rmdir(target_dir)
                    log.info(f"删除目录成功: {target_dir}")
                except Exception as e:
                    log.error(f"删除目录失败: {target_dir}, 错误信息: {e}")


class AssociationHelper:
    """关联操作辅助类"""

    @staticmethod
    async def create_condition_api_association(
        session: AsyncSession,
        condition_id: int,
        interface_id_list: List[int]
    ):
        """
        创建条件与API的关联
        :param session: 会话对象
        :param condition_id: 条件ID
        :param interface_id_list: 接口ID列表
        """
        last_index = await LastIndexHelper.get_condition_apis_last_index(condition_id, session)
        values = [
            {
                "condition_id": condition_id,
                "api_id": interface_id,
                "step_order": index
            } for index, interface_id in enumerate(interface_id_list, start=last_index + 1)
        ]

        if values:
            await session.execute(
                insert(ConditionAPIAssociation).values(values)
            )


class InterfaceMapper(Mapper[InterfaceModel]):
    """接口Mapper"""
    __model__ = InterfaceModel

    @classmethod
    async def update_interface(cls, user: User, **kwargs) -> InterfaceModel:
        """
        更新API
        :param user: 更新人
        :param kwargs: 更新参数
        :return: 更新后的API实例
        """
        async with async_session() as session:
            api = await cls.update_by_id(session=session, updateUser=user, **kwargs)
            log.info(f'update_interface {api}')

            from .interfaceCaseMapper import InterfaceCaseStepContentMapper
            contents = await InterfaceCaseStepContentMapper.query_by(
                session=session,
                target_id=api.id,
                content_type=CaseStepContentType.STEP_API)

            if contents:
                for content in contents:
                    content.content_name = api.name
                    content.content_desc = api.method
                    await InterfaceCaseStepContentMapper.add_flush_expunge(session, content)
                await session.commit()

            return api

    @classmethod
    async def empty_api(cls, module_id: int, project_id: int, user: User, session: AsyncSession) -> InterfaceModel:
        """
        创建一个空API
        :param module_id: 模块ID
        :param project_id: 项目ID
        :param user: 创建人
        :param session: 会话对象
        :return: API实例
        """
        api = cls.__model__(
            name="API名称",
            description="API描述",
            status="DEBUG",
            level="P2",
            url="/",
            method="GET",
            body_type=0,
            is_common=0,
            module_id=module_id,
            project_id=project_id,
            creator=user.id,
            creatorName=user.username
        )
        return await cls.add_flush_expunge(session=session, model=api)

    @classmethod
    async def query_association_case(cls, api_id: int) -> List[InterFaceCaseModel]:
        """
        反向查询管理的CASE
        :param api_id: API ID
        :return: 关联的用例列表
        """
        try:
            async with async_session() as session:
                stmt = select(InterFaceCaseModel).join(
                    InterfaceCaseStepContentAssociation,
                    InterFaceCaseModel.id == InterfaceCaseStepContentAssociation.interface_case_id
                ).join(
                    InterfaceCaseStepContent,
                    InterfaceCaseStepContent.id == InterfaceCaseStepContentAssociation.interface_case_content_id
                ).where(
                    and_(
                        InterfaceCaseStepContent.target_id == api_id,
                        InterfaceCaseStepContent.content_type == CaseStepContentType.STEP_API
                    )
                )
                result = await session.scalars(stmt)
                return result.all()
        except Exception as e:
            log.error(e)
            raise

    @classmethod
    async def copy_to_module(cls, inter_id: int, project_id: int, module_id: int, user: User) -> InterfaceModel:
        """
        复制API到指定模块
        :param inter_id: API ID
        :param project_id: 项目ID
        :param module_id: 模块ID
        :param user: 创建人
        :return: 复制后的API实例
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    copyInter = await cls.copy_api(apiId=inter_id, creator=user, session=session, is_common=True)
                    copyInter.project_id = project_id
                    copyInter.module_id = module_id
                    copyInter = await cls.add_flush_expunge(session=session, model=copyInter)
                    log.info(copyInter)
                    return copyInter
        except Exception as e:
            raise

    @classmethod
    async def set_interfaces_modules(cls, module_id: int, interfaces: List[int]):
        """
        设置接口所属模块
        :param module_id: 模块ID
        :param interfaces: 接口ID列表
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    if interfaces:
                        stmt = update(InterfaceModel).where(
                            InterfaceModel.id.in_(interfaces)
                        ).values(module_id=module_id)
                        await session.execute(stmt)
        except Exception as e:
            raise

    @classmethod
    async def upload(cls, apis: List[Dict[str, Any]], project_id: str, module_id: str, env_id: str, creator: User):
        """
        批量上传API数据并插入到数据库
        :param apis: API数据列表
        :param project_id: 项目ID
        :param module_id: 父级Module ID
        :param env_id: 环境ID
        :param creator: 创建者用户对象
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    # 提取并插入Module
                    module_names = [api.pop("module") for api in apis]
                    module_map = {}
                    for name in set(module_names):
                        module_id = await cls.insert_module(name, session, int(module_id), int(project_id), creator)
                        module_map[name] = module_id

                    # 插入API数据
                    api_tasks = [
                        cls.insert_inter_with_semaphore(session,
                                                        int(project_id),
                                                        int(env_id),
                                                        module_map[module_names[index]], creator, api["data"])
                        for index, api in enumerate(apis)
                    ]
                    await asyncio.gather(*api_tasks, return_exceptions=True)
        except Exception as e:
            log.error(f"Error in upload method: {e}")
            raise

    @staticmethod
    async def insert_inter_with_semaphore(
            session: AsyncSession, project_id: int, env_id: int, module_id: int, creator: User,
            data: List[Dict[str, Any]]
    ):
        """
        插入API数据到数据库
        :param session: 数据库会话
        :param project_id: 项目ID
        :param env_id: 环境ID
        :param module_id: 模块ID
        :param creator: 创建者用户对象
        :param data: API数据列表
        """
        try:
            for api_data in data:
                api_data.update({
                    "project_id": project_id,
                    "env_id": env_id,
                    "module_id": module_id,
                    "creator": creator.id,
                    "creatorName": creator.username,
                    "status": "DEBUG",
                    "level": "P1",
                })
                api = InterfaceModel(**api_data)
                session.add(api)
        except Exception as e:
            log.error(f"Error in insert_inter_with_semaphore: {e}")
            raise

    @staticmethod
    async def insert_module(
            module_name: str, session: AsyncSession, parent_id: int, project_id: int, creator: User
    ) -> int:
        """
        插入模块
        :param module_name: 模块名称
        :param session: 数据库会话
        :param parent_id: 父级模块ID
        :param project_id: 项目ID
        :param creator: 创建者用户对象
        :return: 插入的模块ID
        """
        try:
            # 获取父级Module和子module是否存在
            parent_module = await ModuleMapper.get_by_id(parent_id, session)
            _exist = await session.execute(
                select(Module).where(
                    and_(
                        Module.project_id == parent_id,
                        Module.title == module_name,
                        Module.module_type == ModuleEnum.API
                    )
                )
            )
            existing_module: Module = _exist.scalar_one_or_none()
            if existing_module and module_name == existing_module.title:
                log.debug(f"子部门 '{module_name}' 已存在")
                return existing_module.id

            # 创建新的部门
            child_module = Module(
                title=module_name,
                project_id=project_id,
                parent_id=parent_module.id,
                creator=creator.id,
                creatorName=creator.username
            )
            session.add(child_module)
            await session.flush()
            return child_module.id
        except Exception as e:
            log.error(f"Error in child_module : {e}")
            raise

    @classmethod
    async def remove(cls, interId: int):
        """
        删除api接口
        关联删除处理：
        - api task association
        - api group association
        - api case association
        - api file
        :param interId: API ID
        """
        try:
            async with async_session() as session:
                async with session.begin():
                    api: InterfaceModel = await cls.get_by_id(interId, session)
                    FileManager.remove_api_files(api)

                    from .interfaceTaskMapper import InterfaceTaskMapper
                    await InterfaceTaskMapper.set_task_when_api_remove(session, interId)
                    await InterfaceGroupMapper.set_group_when_api_remove(session, interId)
                    # await InterfaceCaseMapper.set_case_when_api_remove(session, interId)

                    await session.delete(api)
                    await session.flush()
        except Exception as e:
            raise

    @staticmethod
    async def copy_record_2_api(recordId: str, creator: User) -> Dict[str, Any]:
        """
        录制转API
        :param recordId: 录制ID
        :param creator: 创建人
        :return: API参数字典
        """
        try:
            recordInfos = await Record.query_record(creator.uid)
            if not recordInfos:
                raise Exception("未查询到录制信息")

            for record in recordInfos:
                if record.get("uid") == recordId:
                    return {
                        "env_id": -1,
                        "url": record['url'],
                        "desc": record['url'],
                        "method": record['method'],
                        "headers": record['headers'],
                        "params": record['params'],
                        "data": record['data'],
                        "body": record['body'],
                        "body_type": record['body_type']
                    }

            raise Exception("未找到指定的录制信息")
        except Exception as e:
            raise

    @classmethod
    async def save_record(cls, creatorUser: User, recordId: str, **kwargs) -> InterfaceModel:
        """
        录制转API
        :param creatorUser: 创建人
        :param recordId: 录制ID
        :param kwargs: 额外参数
        :return: 创建的API实例
        """
        try:
            record = await cls.copy_record_2_api(recordId, creatorUser)
            kwargs.update(record)
            return await cls.save(creator_user=creatorUser, **kwargs)
        except Exception:
            raise

    @classmethod
    async def copy_api(cls, apiId: int, creator: User, session: AsyncSession = None,
                       is_copy_name: bool = False, is_common: bool = False) -> InterfaceModel:
        """
        复制API
        :param apiId: 待复制API
        :param creator: 创建人
        :param session: 会话对象
        :param is_copy_name: 复制api name 是否+标识（副本） 默认FALSE
        :param is_common: 复制api common
        :return: 复制后的API实例
        """
        try:
            # 封装为一个内部函数，减少重复代码
            async def copy_api_logic(logic_session: AsyncSession):
                target_api = await cls.get_by_id(ident=apiId, session=logic_session)
                target_api_map = target_api.copy_map()
                if not is_copy_name:
                    target_api_map['name'] = target_api_map['name'] + "(副本)"
                new_api = cls.__model__(
                    **target_api_map,
                )
                new_api.creator = creator.id
                new_api.creatorName = creator.username
                new_api.is_common = is_common
                return await cls.add_flush_expunge(logic_session, new_api)

            # 使用一个session上下文管理器，如果没有传入session则创建一个
            if session is None:
                async with async_session() as session:
                    async with session.begin():
                        return await copy_api_logic(session)
            else:
                # 如果传入了session，直接使用它
                return await copy_api_logic(session)

        except Exception as e:
            raise


class InterfaceScriptMapper(Mapper[InterfaceScriptDesc]):
    """接口脚本Mapper"""
    __model__ = InterfaceScriptDesc


class InterfaceFuncMapper(Mapper[InterfaceScriptDesc]):
    """接口函数Mapper"""
    __model__ = InterfaceScriptDesc


class InterfaceConditionMapper(Mapper[InterfaceCondition]):
    """接口条件Mapper"""
    __model__ = InterfaceCondition

    @classmethod
    async def add_empty_condition(cls, session: AsyncSession, user: User) -> InterfaceCondition:
        """
        初始化一个空条件
        :param session: 会话对象
        :param user: 创建人
        :return: 条件实例
        """
        condition = InterfaceCondition(
            creator=user.id,
            creatorName=user.username,
        )
        return await cls.add_flush_expunge(
            session,
            condition,
        )

    @classmethod
    async def query_condition_apis_by_content_id(cls, content_condition_id: int) -> List[InterfaceModel]:
        """
        通过代理API查询到condition，再通过关联表查询子步骤
        :param content_condition_id: 条件内容ID
        :return: 接口列表
        """
        async with async_session() as session:
            condition: InterfaceCondition = await cls.get_by_id(ident=content_condition_id, session=session)

            stmt = select(InterfaceModel).join(ConditionAPIAssociation).where(
                ConditionAPIAssociation.condition_id == condition.id,
                InterfaceModel.id == ConditionAPIAssociation.api_id
            ).order_by(
                ConditionAPIAssociation.step_order
            )
            result = await session.scalars(stmt)
            return result.all()

    @classmethod
    async def remove_condition(cls, condition_id: int, session: AsyncSession):
        """
        移除条件
        :param condition_id: 条件ID
        :param session: 会话对象
        """
        # 删除API所有关联
        await session.execute(
            delete(InterfaceCondition).where(
                InterfaceCondition.id == condition_id
            )
        )

    @classmethod
    async def association_apis(cls, condition_id: int, interface_id_list: List[int]):
        """
        条件添加子API
        :param condition_id: 条件ID
        :param interface_id_list: 接口ID列表
        """
        async with async_session() as session:
            async with session.begin():
                await AssociationHelper.create_condition_api_association(
                    session, condition_id, interface_id_list
                )
                await session.commit()

    @classmethod
    async def remove_association_api(cls, condition_id: int, interface_id: int):
        """
        解除关联
        :param condition_id: 条件ID
        :param interface_id: 接口ID
        """
        async with async_session() as session:
            await session.execute(
                delete(ConditionAPIAssociation).where(
                    and_(
                        ConditionAPIAssociation.condition_id == condition_id,
                        ConditionAPIAssociation.api_id == interface_id
                    )
                )
            )
            await session.commit()

    @classmethod
    async def reorder_condition_apis(cls, condition_id: int, interface_id_list: List[int]):
        """
        子步骤重新排序
        :param condition_id: 条件ID
        :param interface_id_list: 接口ID列表
        """
        async with async_session() as session:
            # 先删除该条件下的所有关联
            await session.execute(
                delete(ConditionAPIAssociation).where(
                    ConditionAPIAssociation.condition_id == condition_id
                )
            )

            values = []
            for index, interface_id in enumerate(interface_id_list, start=1):
                values.append({
                    "condition_id": condition_id,
                    "api_id": interface_id,
                    "step_order": index
                })

            if values:
                await session.execute(
                    insert(ConditionAPIAssociation).values(values)
                )

            await session.commit()
