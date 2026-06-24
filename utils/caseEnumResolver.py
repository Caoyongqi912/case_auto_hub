#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/4
# @Author : cyq
# @File : caseEnumResolver
# @Software: PyCharm
# @Desc: 用例枚举配置 (case_config) → 解析器注入数据 的轻量加载器

import asyncio
from typing import Any, Dict, List, Optional, Tuple

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

    返回结构示例 (PLATFORM 走 combo 展开, n=3 时):
        {
            "CASE_LEVEL": ["P0-最高", "P1-高", "P2-中", "P3-低"],
            "CASE_TYPE":  ["功能测试", "冒烟", "回归", "其他"],
            "PLATFORM":   ["AA", "BB", "CC", "AA,BB", "AA,CC", "BB,CC", "AA,BB,CC"],
        }

    PLATFORM 特殊: 走 generate_platform_combo_labels 把单值 label 集合展开成
    所有 2^n - 1 个非空子集 (含单值与多值组合), 让用户**从下拉直接选**而不用手输.
    其他 key (LEVEL / TYPE) 业务上都是单值, 保持原样.

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

    # PLATFORM 走 combo 展开: build label->value 给 generator 用.
    platform_map = {
        c.label: c.value
        for c in platform_configs
        if c.label and getattr(c, 'enabled', 1) != 0
    }

    return {
        LEVEL_CONFIG_KEY: _labels(level_configs),
        TYPE_CONFIG_KEY: _labels(type_configs),
        PLATFORM_CONFIG_KEY: generate_platform_combo_labels(platform_map),
    }


# ----------------------------------------------------------------------------
# Platform 多值: 适用端 (case_platform) 支持逗号分隔多选
# ----------------------------------------------------------------------------
# 适用端存储/导出格式: 用半角逗号拼接, 顺序按用户输入/输出顺序保留, 自动去重.
# 例: "PC,WJAPP" / "PC" 都合法, "PC, PC" / ",PC," / "PC,,WJAPP" 都规整为 "PC,WJAPP".
# Combo 容量上限. 超过这个数 (2^N - 1) 时不再生成多值组合, 退化为单值下拉
# + 提示用户手输逗号分隔. 原因: 2^10 = 1024, 2^15 = 32768, DataValidation
# list 实际打开/滚动体验会急剧恶化, 用户也基本选不过来.
PLATFORM_COMBO_MAX_LABELS = 8


def generate_platform_combo_labels(platform_map: Dict[str, str]) -> List[str]:
    """
    把 platform 的 label 集合展开成 2^N - 1 个非空子集 label 串, 给 DataValidation
    当下拉源. 让用户**从下拉里直接选**单值/多值, 不需要手输逗号.

    :param platform_map: label -> value 映射 (通常来自 case_config PLATFORM)
    :return: 长度升序的 combo label 串列表.
        n=1: ["AA"]
        n=3: ["AA", "BB", "CC", "AA,BB", "AA,CC", "BB,CC", "AA,BB,CC"]
        n>8: 退化为 ["AA", "BB", ...] (只返单值, 让用户手输多值用逗号)
              实际不会发生, 业务上 PLATFORM 一般 <= 7 个, 2^7=128 还 OK.

    顺序约定:
        - 长度升序 (单值在前, 多值在后, 跟"先选基础再选组合"的认知一致)
        - 同长度内字典序 (跟 sorted 行为一致, dropdown 显示稳定)
        - 用半角逗号拼接, 跟 PLATFORM_VALUE_SEPARATOR 对齐
    """
    from itertools import combinations

    labels = sorted(platform_map.keys())
    n = len(labels)
    if n == 0:
        return []
    if n > PLATFORM_COMBO_MAX_LABELS:
        # 选项数 2^N - 1 > 255, 退化为单值下拉, 提示用户手输多值
        return labels
    out: List[str] = []
    for k in range(1, n + 1):
        for subset in combinations(labels, k):
            out.append(PLATFORM_VALUE_SEPARATOR.join(subset))
    return out


PLATFORM_VALUE_SEPARATOR = ","


def split_platform_value(stored: Optional[str]) -> List[str]:
    """
    把 DB 存的 value 串 ("PC,WJAPP") 拆成有序 list, 去空白 + 去空 + 保序去重.
    空 / None 返回 [].
    """
    if not stored:
        return []
    seen: set = set()
    out: List[str] = []
    for raw in str(stored).split(PLATFORM_VALUE_SEPARATOR):
        s = raw.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def join_platform_value(values: List[str]) -> str:
    """
    反向: list -> "PC,WJAPP". 跳过空 / 全空白元素, 跟 split 对称.
    全空返回 "".
    """
    parts = [v.strip() for v in values if v and str(v).strip()]
    return PLATFORM_VALUE_SEPARATOR.join(parts)


def format_platform_value_for_export(
    stored: Optional[str],
    label_map: Dict[str, str],
) -> Optional[str]:
    """
    导出: 把 DB 存的 value 串 ("PC,WJAPP") 翻成给用户看的 label 串 ("PC端,WJAPP端").

    - 单值 / 多值同款, 都走 split_platform_value
    - 缺失 label 时回退原 value (跟单值时 label_map.get(v, v) 语义一致, 避免运营
      新加枚举还没补 label_map 时把 cell 写空)
    - 空值返回 None (上游不写 cell)
    """
    values = split_platform_value(stored)
    if not values:
        return stored if stored else None
    labels = [label_map.get(v, v) for v in values]
    return join_platform_value(labels)


def parse_platform_cell_to_value(
    raw: Any,
    platform_map: Dict[str, str],
    display_name: str = "适用端",
) -> "tuple[Optional[str], Optional[Dict[str, str]]]":
    """
    导入: 把 Excel cell 文本 (label, 可逗号多选) 解析成 DB 存的 value 串.

    :param raw: cell 原始值 (str / None / float-NaN / 其它可 str() 化的类型)
    :param platform_map: case_config PLATFORM 的 label -> value 映射
    :param display_name: 报错时显示的中文列名
    :return: (joined_value, error_dict_or_None)
        - joined_value: 校验通过后的 value 串, 多选用逗号拼接 ("PC,WJAPP");
          空值返回 None (留给上游必填检查)
        - error_dict: 校验失败时返回 {"field": ..., "message": ...},
          列出所有非法 label (便于前端一次性高亮)

    行为约定:
        - 空 / 全空白 / ",,," -> (None, None) -> 上游报 "不能为空"
        - 单选 / 多选都支持, 多选按 cell 出现顺序, 重复 label 去重 ("PC端,PC端" -> "PC")
        - 任意 label 不在 platform_map -> 整条 raise, 不做 partial save
        - platform_map 为空 (preview-only / 配置未加载) -> 不查 enum, 仅 trim + join,
          跟 M1 用例等级 else 分支语义对齐
    """
    if raw is None:
        return None, None
    # pandas NaN 兼容: float('nan') 转 str 是 "nan", 直接判掉
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None, None

    parts = [p.strip() for p in s.split(PLATFORM_VALUE_SEPARATOR)]
    parts = [p for p in parts if p]
    if not parts:
        return None, None

    if not platform_map:
        return join_platform_value(parts), None

    bad = [p for p in parts if p not in platform_map]
    if bad:
        valid = ", ".join(sorted(platform_map.keys()))
        bad_str = ", ".join(f"'{b}'" for b in bad)
        return None, {
            "field": display_name,
            "message": f"{display_name} {bad_str} 不在可选范围内: {valid}",
        }

    # 校验通过: label -> value, 保输入顺序 + 去重
    seen: set = set()
    out: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(platform_map[p])
    return join_platform_value(out), None


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
