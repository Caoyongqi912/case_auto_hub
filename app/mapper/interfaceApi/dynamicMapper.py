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

ARRAY_FIELD_KEYS: set[str] = {
    "interface_params",
    "interface_headers",
    "interface_before_params",
}

SCRIPT_SQL_FIELD_KEYS: set[str] = {
    "interface_before_script",
    "interface_after_script",
}

ASSERT_EXTRACT_FIELD_KEYS: set[str] = {
    "interface_asserts",
    "interface_extracts",
}

NAME_FIELD_MAP: Dict[str, str] = {
    "interface_params": "请求参数",
    "interface_headers": "请求头",
    "interface_before_params": "请求前置参数",
    "interface_before_script": "请求前置脚本",
    "interface_after_script": "请求后置脚本",
    "interface_before_sql": "请求前置SQL",
    "interface_asserts": "请求断言",
    "interface_extracts": "响应变量提取",
}


def transform_value(field_key: str, value: Any, value_mappings: Dict[str, Dict]) -> str:
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


def _get_item_name(item: Dict[str, Any], field_key: str) -> str:
    if field_key in ("interface_params", "interface_headers", "interface_before_params"):
        return item.get("key", item.get("id", "未知"))
    if field_key in ("interface_asserts", "interface_extracts"):
        name = item.get("assert_name") or item.get("key") or item.get("name")
        return name or str(item.get("id", "未知"))
    return str(item.get("id", "未知"))


def _diff_array_field(
        old_list: List[Dict],
        new_list: List[Dict],
        field_key: str
) -> List[str]:
    diffs = []
    old_ids = {item.get("id") for item in old_list if item.get("id") is not None}
    new_ids = {item.get("id") for item in new_list if item.get("id") is not None}

    field_name = NAME_FIELD_MAP.get(field_key, field_key)

    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids

    old_dict = {item.get("id"): item for item in old_list if item.get("id") is not None}
    new_dict = {item.get("id"): item for item in new_list if item.get("id") is not None}

    for item_id in added_ids:
        item = new_dict.get(item_id)
        if item:
            name = _get_item_name(item, field_key)
            diffs.append(f"{field_name} 新增 {name}")

    for item_id in removed_ids:
        item = old_dict.get(item_id)
        if item:
            name = _get_item_name(item, field_key)
            diffs.append(f"{field_name} 删除 {name}")

    for item_id in old_ids & new_ids:
        old_item = old_dict.get(item_id)
        new_item = new_dict.get(item_id)
        if old_item and new_item:
            item_diffs = _diff_dict_items(old_item, new_item, field_key)
            if item_diffs:
                name = _get_item_name(new_item, field_key)
                for diff in item_diffs:
                    diffs.append(f"{field_name} 修改 {name}: {diff}")

    return diffs


def _diff_dict_items(old: Dict[str, Any], new: Dict[str, Any], parent_key: str) -> List[str]:
    diffs = []
    all_keys = set(old.keys()) | set(new.keys())
    ignore_keys = {"id"}
    relevant_keys = all_keys - ignore_keys

    for key in relevant_keys:
        old_value = old.get(key)
        new_value = new.get(key)
        if old_value == new_value:
            continue
        field_name = key
        old_display = str(old_value) if old_value is not None else "空"
        new_display = str(new_value) if new_value is not None else "空"
        diffs.append(f"{field_name}: {old_display} → {new_display}")

    return diffs


def _diff_script_sql_field(
        old_value: Any,
        new_value: Any,
        field_key: str
) -> List[str]:
    diffs = []
    field_name = NAME_FIELD_MAP.get(field_key, field_key)

    old_str = old_value.strip() if old_value else ""
    new_str = new_value.strip() if new_value else ""

    if old_str and not new_str:
        diffs.append(f"{field_name} 已清空")
    elif not old_str and new_str:
        diffs.append(f"{field_name} 已添加内容")
    elif old_str != new_str:
        diffs.append(f"{field_name} 已修改")

    return diffs


def _diff_assert_extract_field(
        old_list: List[Dict],
        new_list: List[Dict],
        field_key: str
) -> List[str]:
    diffs = []
    field_name = NAME_FIELD_MAP.get(field_key, field_key)

    old_ids = {item.get("id") for item in old_list if item.get("id") is not None}
    new_ids = {item.get("id") for item in new_list if item.get("id") is not None}

    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids

    old_dict = {item.get("id"): item for item in old_list if item.get("id") is not None}
    new_dict = {item.get("id"): item for item in new_list if item.get("id") is not None}

    for item_id in added_ids:
        item = new_dict.get(item_id)
        if item:
            name = _get_item_name(item, field_key)
            diffs.append(f"{field_name} 新增 {name}")

    for item_id in removed_ids:
        item = old_dict.get(item_id)
        if item:
            name = _get_item_name(item, field_key)
            diffs.append(f"{field_name} 删除 {name}")

    for item_id in old_ids & new_ids:
        old_item = old_dict.get(item_id)
        new_item = new_dict.get(item_id)
        if old_item and new_item:
            item_diffs = _diff_dict_items(old_item, new_item, field_key)
            if item_diffs:
                name = _get_item_name(new_item, field_key)
                for diff in item_diffs:
                    diffs.append(f"{field_name} 修改 {name}: {diff}")

    return diffs


class InterfaceDynamicMapper(Mapper[InterfaceDynamic]):
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

    @classmethod
    def _diff_dict(cls, old: Dict[str, Any], new: Dict[str, Any]) -> str | None:
        all_keys = set(old.keys()) | set(new.keys())
        relevant_keys = all_keys - IGNORE_KEYS
        diff_args = []

        for key in relevant_keys:
            old_value = old.get(key)
            new_value = new.get(key)

            if old_value == new_value:
                continue

            if key in ARRAY_FIELD_KEYS:
                if isinstance(old_value, list) and isinstance(new_value, list):
                    array_diffs = _diff_array_field(old_value, new_value, key)
                    diff_args.extend(array_diffs)
                continue

            if key in SCRIPT_SQL_FIELD_KEYS:
                script_diffs = _diff_script_sql_field(old_value, new_value, key)
                diff_args.extend(script_diffs)
                continue

            if key in ASSERT_EXTRACT_FIELD_KEYS:
                if isinstance(old_value, list) and isinstance(new_value, list):
                    assert_diffs = _diff_assert_extract_field(old_value, new_value, key)
                    diff_args.extend(assert_diffs)
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
        try:
            async with async_session() as session:
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


class InterfaceCaseDynamicMapper(Mapper[InterfaceCaseDynamic]):
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
    def _diff_dict(cls, old: Dict[str, Any], new: Dict[str, Any]) -> str | None:
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
        try:
            async with async_session() as session:
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

    @classmethod
    async def append_dynamic_detail(
            cls,
            case_id: int,
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
            log.error(f'{cls.__name__}.append_dynamic_detail error: {e}')
            raise


class InterfaceTaskDynamicMapper(Mapper[InterfaceTaskDynamic]):
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

    @classmethod
    def _diff_dict(cls, old: Dict[str, Any], new: Dict[str, Any]) -> str | None:
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
    async def new_dynamic(
            cls,
            entity_name: str,
            entity_id: int,
            user: User,
            session: AsyncSession
    ):
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
