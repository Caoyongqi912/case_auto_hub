#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/4
# @Author : cyq
# @File : caseEnumResolver
# @Software: PyCharm
# @Desc: 用例枚举配置 (case_config) → 解析器注入数据 的轻量加载器

import asyncio
from typing import Dict, Optional, List

from app.mapper.test_case.caseConfigMapper import CaseConfigMapper
from utils.aioFileReader import CaseEnumConfig

LEVEL_CONFIG_KEY = "CASE_LEVEL"
TYPE_CONFIG_KEY = "CASE_TYPE"
PLATFORM_CONFIG_KEY = "PLATFORM"


async def load_case_enum_config() -> CaseEnumConfig:
    """
    并行加载 CASE_LEVEL / CASE_TYPE / PLATFORM 配置, 构造 CaseEnumConfig.

    - level_map / type_map / platform_map 为空时仍返回 (让解析器按"非空校验"放行, 不强依赖枚举配置存在)
    - 新规: 三个 default_* 全部 None. 必填字段 (等级) 在解析层走 explicit 校验, 不再 silent 回退;
      可选字段 (类型/适用端) 空值时也保持 None, 由调用方按需注入, 不会"自动填第一个配置".
    """
    try:
        level_configs, type_configs, platform_configs = await asyncio.gather(
            CaseConfigMapper.query_by_key(LEVEL_CONFIG_KEY),
            CaseConfigMapper.query_by_key(TYPE_CONFIG_KEY),
            CaseConfigMapper.query_by_key(PLATFORM_CONFIG_KEY),
        )
    except Exception as err:
        # 配置加载失败不阻塞整条上传路径; 解析器拿到空 map 会按行报错
        from utils import log
        log.error(f"load_case_enum_config error: {err}")
        return CaseEnumConfig()

    level_map = {c.label: c.value for c in level_configs if c.label}
    type_map = {c.label: c.value for c in type_configs if c.label}
    platform_map = {c.label: c.value for c in platform_configs if c.label}

    return CaseEnumConfig(
        level_map=level_map,
        type_map=type_map,
        platform_map=platform_map,
        default_level=None,
        default_type=None,
        default_platform=None,
    )


async def load_case_enum_label_map() -> Dict[str, str]:
    """
    加载 case_config 中 CASE_LEVEL / CASE_TYPE / PLATFORM 的 value -> label 反向映射.

    用于导出时把 DB 存的 value (如 "GN" / "PC") 翻成 label (如 "功能" / "PC端") 写进
    Excel, 与用户上传模板时的认知一致. 三个 config_key 都进同一 dict, 跨 key
    value 撞了 (业务上 PLATFORM.PC vs CASE_LEVEL.PC 不会撞, 但不排除运营误配)
    时后注册的覆盖前一个. 真要避免可以拆成嵌套 dict, 改 ExportCaseService 一起动.

    失败/无数据时返回空 dict, 调用方按"无映射" 处理 (label_map.get(value, value) 回退原值).
    """
    try:
        level_configs, type_configs, platform_configs = await asyncio.gather(
            CaseConfigMapper.query_by_key(LEVEL_CONFIG_KEY),
            CaseConfigMapper.query_by_key(TYPE_CONFIG_KEY),
            CaseConfigMapper.query_by_key(PLATFORM_CONFIG_KEY),
        )
    except Exception as err:
        from utils import log
        log.error(f"load_case_enum_label_map error: {err}")
        return {}

    label_map: Dict[str, str] = {}
    for cfg in list(level_configs) + list(type_configs) + list(platform_configs):
        if cfg.value and cfg.label:
            label_map[cfg.value] = cfg.label
    return label_map


async def load_case_enum_label_lists() -> Dict[str, List[str]]:
    """
    返回每个 config_key 对应的有序 label 列表 (按 sort 升序, 过滤 disabled=0).

    给导出 Excel 的下拉框 DataValidation 用. 之所以不与 load_case_enum_label_map
    合并返回, 是因为 DataValidation 需要**完整有序**的选项列表 (用户下拉看到的文字),
    而 label_map 是 value->label 的反向映射 (写回 Excel 时把 DB 存的 value 翻成 label),
    两者用途不一样, 分两个函数让调用方按需取, 不强制每次都拉全量.

    返回结构示例:
        {
            "CASE_LEVEL": ["P0-最高", "P1-高", "P2-中", "P3-低"],
            "CASE_TYPE":  ["功能测试", "冒烟", "回归", "其他"],
            "PLATFORM":   ["PC", "H5", "Android", "iOS"],
        }

    失败/无数据时返回空 dict, 调用方按 config_key 取, 缺 key 时用空列表 (DataValidation
    拿空列表就直接跳过该列下拉, 不报错).
    """
    try:
        level_configs, type_configs, platform_configs = await asyncio.gather(
            CaseConfigMapper.query_by_key(LEVEL_CONFIG_KEY),
            CaseConfigMapper.query_by_key(TYPE_CONFIG_KEY),
            CaseConfigMapper.query_by_key(PLATFORM_CONFIG_KEY),
        )
    except Exception as err:
        from utils import log
        log.error(f"load_case_enum_label_lists error: {err}")
        return {}

    def _labels(configs) -> List[str]:
        # mapper.query_by_key 已按 sort asc, id asc 排好序.
        # 过滤 enabled=0 (停用) 与空 label.
        return [c.label for c in configs if c.label and getattr(c, 'enabled', 1) != 0]

    return {
        LEVEL_CONFIG_KEY: _labels(level_configs),
        TYPE_CONFIG_KEY: _labels(type_configs),
        PLATFORM_CONFIG_KEY: _labels(platform_configs),
    }
    return result


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
    把 Excel "所属分组" 列解析为 Module.id (find-or-create).

    - 空值返回 None (调用方走兜底 module_id)
    - 拆解路径, 调 ModuleMapper.find_or_create_path 逐级 find-or-create, 返回叶子 id
    - 任意异常被吞掉返回 None, 不阻塞整批导入 (路径脏数据不影响其他行)

    业务约定: 仅用于"系统已建好目录"的场景; 对"必须先存在才允许导入"的硬门禁,
    请改用 find_group_path, 后者只查不建, 缺失即返回 None.

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


async def find_group_path(project_id, raw_group_path, module_type=CASE_MODULE_TYPE):
    """
    把 Excel "所属分组" 列校验为已存在的 Module.id (只查不建).

    与 resolve_group_path 的关键区别:
    - 本函数**不会**在 module 表上新建任何节点
    - 路径任一级缺失即返回 None, 由调用方决定是整批拒绝还是跳过坏行
    - 用于"系统必须先有这个目录才允许导入"的硬门禁校验

    :param project_id: 项目 ID
    :param raw_group_path: 原始字符串
    :param module_type: 模块类型, 默认用例 (ModuleEnum.CASE = 10)
    :return: 已存在的叶子 Module.id; 路径为空/缺失/异常均返回 None
    """
    titles = _split_group_path(raw_group_path)
    if not titles:
        return None

    try:
        from app.mapper.project.moduleMapper import ModuleMapper
        return await ModuleMapper.find_path(
            project_id=project_id,
            title_path=titles,
            module_type=module_type,
        )
    except Exception:
        from utils import log
        log.opt(exception=True).error(
            f"find_group_path failed: project_id={project_id}, "
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
