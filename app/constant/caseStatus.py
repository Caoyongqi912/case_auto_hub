#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/18
# @Author : cyq
# @File : caseStatus
# @Software: PyCharm
# @Desc: 用例状态 (CASE_STATUS) hardcode 常量.

"""
用例状态枚举被刻意 hardcode, 不再走 case_config 表.

理由:
  1. value/label 与业务逻辑强绑定 (聚合判定 / dynamic log 文案),
     让 admin 改 value 会破坏 step→case 聚合判定逻辑.
  2. 一轮/二轮 step 状态共用同一份枚举, 状态机变更涉及面广,
     收口到代码层避免配置漂移.
  3. value 改用英文短词 ("pass" / "fail" / ...) 而非历史 "0" "1",
     排查日志 / 抓 trace 时更可读.

新增/修改状态需要改这里 + 同步检查所有 _LABEL_OF / 聚合逻辑是否还成立.
"""

from dataclasses import dataclass
from typing import Dict, List


# config_key: 与 case_config 表保持一致, 让 query_case_config 接口能路由到
#   同一个 key 返回 hardcode, 前端 useCaseEnumConfig('CASE_STATUS') 无感切换.
CASE_STATUS_KEY = "CASE_STATUS"


@dataclass(frozen=True)
class CaseStatusItem:
    """单个用例状态 hardcode 项, 字段对齐 CaseConfig 模型."""
    value: str
    label: str
    color: str
    sort: int


# 5 个 hardcode 状态. 顺序即 sort 升序, 调换位置 = 业务变更.
BUILTIN_CASE_STATUS: List[CaseStatusItem] = (
    CaseStatusItem(value="ready", label="待测试", color="#918f8f", sort=0),
    CaseStatusItem(value="pass",  label="成功",   color="#52c41a", sort=1),
    CaseStatusItem(value="fail",  label="失败",   color="#ff0000", sort=2),
    CaseStatusItem(value="skip",  label="跳过",   color="#faad14", sort=3),
    CaseStatusItem(value="block", label="阻塞",   color="#722ed1", sort=4),
)


# value -> label. 给统计/渲染/导出等"翻 label"场景用.
BUILTIN_CASE_STATUS_LABEL_MAP: Dict[str, str] = {
    item.value: item.label for item in BUILTIN_CASE_STATUS
}


def is_valid_case_status(value: str) -> bool:
    """value 是否在 hardcode 枚举内. 入参校验 / DB 旧数据迁移判定."""
    return value in BUILTIN_CASE_STATUS_LABEL_MAP
