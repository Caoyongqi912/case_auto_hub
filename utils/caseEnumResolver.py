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
