#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/4
# @Author : cyq
# @File : caseEnumResolver
# @Software: PyCharm
# @Desc: 用例枚举配置 (case_config) → 解析器注入数据 的轻量加载器

import asyncio
from typing import Dict, Optional, Tuple

from app.mapper.test_case.caseConfigMapper import CaseConfigMapper
from utils.aioFileReader import CaseEnumConfig, DEFAULT_LEVEL_VALUE

# case_config 表中我们关心的两个分组
LEVEL_CONFIG_KEY = "CASE_LEVEL"
TYPE_CONFIG_KEY = "CASE_TYPE"


async def load_case_enum_config() -> CaseEnumConfig:
    """
    并行加载 CASE_LEVEL / CASE_TYPE 配置, 构造 CaseEnumConfig.

    - level_map / type_map 为空时仍返回 (让解析器按"非空校验"放行, 不强依赖枚举配置存在)
    - default_type 取 type 配置中 sort 最小且 enabled 的 value
    """
    try:
        level_configs, type_configs = await asyncio.gather(
            CaseConfigMapper.query_by_key(LEVEL_CONFIG_KEY),
            CaseConfigMapper.query_by_key(TYPE_CONFIG_KEY),
        )
    except Exception as err:
        # 配置加载失败不阻塞整条上传路径; 解析器拿到空 map 会按行报错
        from utils import log
        log.error("load_case_enum_config error: %s", err)
        return CaseEnumConfig()

    level_map = {c.label: c.value for c in level_configs if c.label}
    type_map = {c.label: c.value for c in type_configs if c.label}

    default_type: Optional[str] = None
    if type_configs:
        # query_by_key 已按 sort asc, id asc 排好序
        default_type = type_configs[0].value

    return CaseEnumConfig(
        level_map=level_map,
        type_map=type_map,
        default_level=DEFAULT_LEVEL_VALUE,
        default_type=default_type,
    )


# ----------------------------------------------------------------------------
# UploadModuleResolver: Excel "所属分组" 字符串 → module_id
# ----------------------------------------------------------------------------
# 分隔符按出现顺序匹配 (任一命中即用). 常见写法都覆盖, 包含全角符号.
GROUP_PATH_SEPARATORS = ("/", "→", ">", "＞", "|", "｜", "-")

# 用例模块的 module_type, 避免循环导入在调用方 import ModuleEnum
CASE_MODULE_TYPE = 10  # ModuleEnum.CASE


def _split_group_path(raw):
    """
    把 Excel 单元格中的"所属分组"原始字符串拆成 title 路径列表.

    - None / 空串 / 全空白 -> []
    - 命中任一分隔符: 按该分隔符拆, 去空白, 丢空段
    - 没命中分隔符: 整串作为单级路径

    例: "二手/交易/待办流程/PC" -> ["二手", "交易", "待办流程", "PC"]
        "根 > 子 > 孙"            -> ["根", "子", "孙"]
        "单层"                    -> ["单层"]
    """
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    for sep in GROUP_PATH_SEPARATORS:
        if sep in s:
            parts = [p.strip() for p in s.split(sep)]
            return [p for p in parts if p]
    return [s]


async def resolve_group_path(project_id, raw_group_path, user, module_type=CASE_MODULE_TYPE):
    """
    把 Excel "所属分组" 列解析为 Module.id.

    - 空值返回 None (调用方走兜底 module_id)
    - 拆解路径, 调 ModuleMapper.find_or_create_path 逐级 find-or-create, 返回叶子 id
    - 任意异常被吞掉返回 None, 不阻塞整批导入 (路径脏数据不影响其他行)

    :param project_id: 项目 ID
    :param raw_group_path: 原始字符串
    :param user: 创建人 (find_or_create_path 需要)
    :param module_type: 模块类型, 默认用例 (ModuleEnum.CASE = 10)
    :return: 叶子 Module.id, 解析失败返回 None
    """
    titles = _split_group_path(raw_group_path)
    if not titles:
        return None

    try:
        from app.mapper.project.moduleMapper import ModuleMapper
        leaf = await ModuleMapper.find_or_create_path(
            project_id=project_id,
            title_path=titles,
            module_type=module_type,
            user=user,
        )
        return leaf.id
    except Exception:
        # exception=True 让 loguru 输出完整 stacktrace, 方便定位
        from utils import log
        log.opt(exception=True).error(
            f"resolve_group_path failed: project_id={project_id}, "
            f"raw={raw_group_path!r}, titles={titles}"
        )
        return None


# ----------------------------------------------------------------------------
# UploadPlanModuleResolver: Excel "所属分组" 字符串 → plan_module_id
# ----------------------------------------------------------------------------
# 与 resolve_group_path 逻辑一致, 唯一区别:
# - 落到 plan_module 表而非 Module 表
# - 通过 (plan_id, parent_id, title) 定位, 不依赖 module_type
# - 由调用方在事务外解析, 避免嵌套事务破坏原子性


async def resolve_plan_group_path(plan_id: int, raw_group_path: str, user: "User"):
    """
    把 Excel "所属分组" 列解析为 plan_module.id.

    - 空值返回 None (调用方走兜底 plan_module_id)
    - 拆解路径, 调 PlanModuleMapper.find_or_create_path 逐级 find-or-create, 返回叶子 id
    - 任意异常被吞掉返回 None, 不阻塞整批导入 (路径脏数据不影响其他行)

    :param plan_id: 计划 ID
    :param raw_group_path: 原始字符串
    :param user: 创建人
    :return: 叶子 plan_module.id, 解析失败返回 None
    """
    titles = _split_group_path(raw_group_path)
    if not titles:
        return None

    try:
        from app.mapper.test_case.planModuleMapper import PlanModuleMapper
        leaf = await PlanModuleMapper.find_or_create_path(
            plan_id=plan_id,
            title_path=titles,
            user=user,
        )
        return leaf.id
    except Exception:
        # exception=True 让 loguru 输出完整 stacktrace, 方便定位
        from utils import log
        log.opt(exception=True).error(
            f"resolve_plan_group_path failed: plan_id={plan_id}, "
            f"raw={raw_group_path!r}, titles={titles}"
        )
        return None
