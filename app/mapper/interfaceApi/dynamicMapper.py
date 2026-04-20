#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/3
# @Author : cyq
# @File : interfaceDynamicMapper
# @Software: PyCharm
# @Desc: 动态记录 Mapper - 记录接口、用例、任务的变更历史

from typing import List, Dict, Any, Type, ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base import User
from app.model.interfaceAPIModel.dynamicModel import (
    InterfaceDynamic,
    InterfaceCaseDynamic,
    InterfaceTaskDynamic
)
from utils import log

IGNORE_KEYS: set[str] = {
    "id", "uid", "create_time", "update_time",
    "creator", "creatorName", "updater", "updaterName"
}


def transform_value(field_key: str, value: Any, value_mappings: Dict[str, Dict]) -> str:
    """
    根据字段类型转换值的显示格式

    Args:
        field_key: 字段名
        value: 字段值
        value_mappings: 值映射字典

    Returns:
        可读的字符串表示
    """
    if value is None:
        return "空"

    if field_key in value_mappings and value in value_mappings[field_key]:
        return value_mappings[field_key][value]

    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            items = []
            for v in value:
                item_strs = [f"{kk}={vv}" for kk, vv in v.items()]
                items.append("{" + ", ".join(item_strs) + "}")
            return "、".join(items) if items else "空"
        return "、".join(str(v) for v in value) if value else "空"

    if isinstance(value, bool):
        return "是" if value else "否"

    return str(value)


class BaseDynamicMapper(Mapper):
    """
    动态记录基类 Mapper

    提供通用的变更记录查询、创建、追加功能
    子类需要定义: __model__, KEY_MAP, VALUE_MAPPINGS, ENTITY_TYPE, FK_FIELD
    """
    __model__: Type
    KEY_MAP: ClassVar[Dict[str, str]] = {}
    VALUE_MAPPINGS: ClassVar[Dict[str, Dict]] = {}
    ENTITY_TYPE: str = ""
    FK_FIELD: str = ""

    @classmethod
    def _diff_dict(cls, old: Dict[str, Any], new: Dict[str, Any]) -> str | None:
        """
        比较两个字典的差异，生成变更描述

        Args:
            old: 变更前的数据
            new: 变更后的数据

        Returns:
            变更描述字符串，如果无变更则返回 None
        """
        all_keys = set(old.keys()) | set(new.keys())
        relevant_keys = all_keys - IGNORE_KEYS
        diff_args = []

        for key in relevant_keys:
            old_value = old.get(key)
            new_value = new.get(key)

            if old_value == new_value:
                continue

            field_name = cls.KEY_MAP.get(key, key)
            old_display = transform_value(key, old_value, cls.VALUE_MAPPINGS)
            new_display = transform_value(key, new_value, cls.VALUE_MAPPINGS)

            if old_value is None:
                diff_args.append(f"{field_name} 新增 {new_display}")
            elif new_value is None:
                diff_args.append(f"{field_name} 从 {old_display} 变更为 空")
            else:
                diff_args.append(f"{field_name} 从 {old_display} 变更为 {new_display}")

        return "\n".join(diff_args) if diff_args else None

    @classmethod
    async def query_dynamic(cls, entity_id: int) -> List:
        """
        查询实体的变更历史

        Args:
            entity_id: 实体 ID

        Returns:
            变更记录列表
        """
        try:
            async with async_session() as session:
                filter_condition = {cls.FK_FIELD: entity_id}
                dynamics = await session.scalars(
                    select(cls.__model__)
                    .where(getattr(cls.__model__, cls.FK_FIELD) == entity_id)
                    .order_by(cls.__model__.create_time.asc())
                )
                return dynamics.all()
        except Exception as e:
            log.error(f'{cls.__name__}.query_dynamic error: {e}')
            raise

    @classmethod
    async def new_dynamic(
            cls,
            entity_name: str,
            entity_id: int,
            user: User,
            session: AsyncSession
    ):
        """
        记录创建实体的动态

        Args:
            entity_name: 实体名称
            entity_id: 实体 ID
            user: 操作用户
            session: 数据库会话
        """
        try:
            await cls.save(
                session=session,
                creator_user=user,
                description=f"{user.username} 创建了{cls.ENTITY_TYPE} {entity_name}",
                **{cls.FK_FIELD: entity_id}
            )
        except Exception as e:
            log.error(f'{cls.__name__}.new_dynamic error: {e}')
            raise

    @classmethod
    async def append_dynamic(
            cls,
            entity_id: int,
            user: User,
            old_info: Dict[str, Any],
            new_info: Dict[str, Any],
            session: AsyncSession
    ):
        """
        记录更新实体的动态

        Args:
            entity_id: 实体 ID
            user: 操作用户
            old_info: 变更前的数据
            new_info: 变更后的数据
            session: 数据库会话
        """
        try:
            log.info(f'{cls.__name__}.append_dynamic old_info: {old_info}')
            log.info(f'{cls.__name__}.append_dynamic new_info: {new_info}')
            diff_info = cls._diff_dict(old_info, new_info)
            log.debug(f"{cls.__name__}.append_dynamic diff_info: {diff_info}")
            if not diff_info:
                return

            model = cls.__model__(
                description=f"{user.username} 更新了{cls.ENTITY_TYPE}:\n{diff_info}",
                creator=user.id,
                creatorName=user.username,
                **{cls.FK_FIELD: entity_id}
            )
            log.debug(f"{cls.__name__}.append_dynamic model: {model}")
            await cls.add_flush_expunge(session=session, model=model)
        except Exception as e:
            log.error(f'{cls.__name__}.append_dynamic error: {e}')
            raise


class InterfaceDynamicMapper(BaseDynamicMapper):
    """
    接口变更记录 Mapper
    """
    __model__ = InterfaceDynamic
    ENTITY_TYPE = "接口"
    FK_FIELD = "interface_id"

    KEY_MAP: ClassVar[Dict[str, str]] = {
        "interface_name": "接口名称",
        "interface_desc": "接口描述",
        "interface_status": "接口状态",
        "interface_level": "接口等级",
        "interface_url": "接口地址",
        "interface_method": "请求类型",
        "interface_params": "请求参数",
        "interface_headers": "请求头",
        "interface_body_type": "请求体类型",
        "interface_raw_type": "Raw类型",
        "interface_auth_type": "认证类型",
        "interface_auth": "认证信息",
        "interface_body": "请求体",
        "interface_data": "表单数据",
        "interface_asserts": "断言配置",
        "interface_extracts": "响应提取",
        "interface_follow_redirects": "是否重定向",
        "interface_connect_timeout": "连接超时时间",
        "interface_response_timeout": "请求超时时间",
        "interface_before_script": "前置脚本",
        "interface_before_db_id": "前置数据库ID",
        "interface_before_sql": "前置SQL",
        "interface_before_sql_extracts": "SQL提取配置",
        "interface_after_script": "后置脚本",
        "interface_before_params": "前置参数",
        "is_common": "是否公共API",
        "env_id": "所属环境",
        "module_id": "所属模块",
        "project_id": "所属项目",
    }

    VALUE_MAPPINGS: ClassVar[Dict[str, Dict]] = {
        "interface_body_type": {0: "无", 1: "raw", 2: "data", 3: "json"},
        "interface_auth_type": {1: "不认证", 2: "认证"},
        "is_common": {0: "否", 1: "是"},
    }


class InterfaceCaseDynamicMapper(BaseDynamicMapper):
    """
    用例变更记录 Mapper
    """
    __model__ = InterfaceCaseDynamic
    ENTITY_TYPE = "业务用例"
    FK_FIELD = "interface_case_id"

    KEY_MAP: ClassVar[Dict[str, str]] = {
        "case_title": "用例标题",
        "case_desc": "用例描述",
        "case_level": "用例等级",
        "case_status": "用例状态",
        "module_id": "所属模块",
        "project_id": "所属项目",
    }

    VALUE_MAPPINGS: ClassVar[Dict[str, Dict]] = {
        "case_level": {"P0": "P0-最高", "P1": "P1-高", "P2": "P2-中", "P3": "P3-低"},
        "case_status": {"DEBUG": "调试中", "READY": "就绪", "ARCHIVED": "已归档"},
    }

    @classmethod
    async def append_dynamic_detail(
            cls,
            case_id:int,
            user: User,
            description: str,
            session: AsyncSession,
    ):
        try:
            model = cls.__model__(
                interface_case_id=case_id,
                description=f"{user.username} {description}",
                creator=user.id,
                creatorName=user.username,
            )
            await cls.add_flush_expunge(session=session, model=model)
        except Exception as e:
            log.error(f'{cls.__name__}.append_dynamic error: {e}')
            raise


class InterfaceTaskDynamicMapper(BaseDynamicMapper):
    """
    任务变更记录 Mapper
    """
    __model__ = InterfaceTaskDynamic
    ENTITY_TYPE = "任务"
    FK_FIELD = "interface_task_id"

    KEY_MAP: ClassVar[Dict[str, str]] = {
        "interface_task_title": "任务标题",
        "interface_task_desc": "任务描述",
        "interface_task_switch": "任务开关",
        "interface_task_status": "任务状态",
        "interface_task_level": "任务等级",
        "interface_task_total_cases_num": "用例数量",
        "interface_task_total_apis_num": "接口数量",
        "module_id": "所属模块",
        "project_id": "所属项目",
    }

    VALUE_MAPPINGS: ClassVar[Dict[str, Dict]] = {
        "interface_task_status": {
            "WAIT": "等待执行",
            "RUNNING": "执行中",
            "SUCCESS": "执行成功",
            "FAILED": "执行失败",
            "STOPPED": "已停止"
        },
        "interface_task_level": {"P0": "P0-最高", "P1": "P1-高", "P2": "P2-中", "P3": "P3-低"},
        "interface_task_switch": {True: "开启", False: "关闭"},
    }
