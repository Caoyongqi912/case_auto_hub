#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/9
# @Author : cyq
# @File : init_case_config
# @Software: PyCharm
# @Desc: 初始化用例枚举配置默认数据
from utils import log

# ========== 默认用例配置数据 ==========
case_config_defaults = [
    # ---------- 用例状态 CASE_STATUS ----------
    {
        "config_key": "CASE_STATUS",
        "label": "待测试",
        "value": "0",
        "color": "#918f8f",
        "description": "待测试",
        "sort": 0,
        "enabled": True,
    },
    {
        "config_key": "CASE_STATUS",
        "label": "成功",
        "value": "1",
        "color": "#52c41a",
        "description": "用例通过",
        "sort": 1,
        "enabled": True,
    },
    {
        "config_key": "CASE_STATUS",
        "label": "失败",
        "value": "2",
        "color": "#ff0000",
        "description": "用例失败",
        "sort": 2,
        "enabled": True,
    },
    {
        "config_key": "CASE_STATUS",
        "label": "跳过",
        "value": "3",
        "color": "#faad14",
        "description": "用例跳过",
        "sort": 3,
        "enabled": True,
    },
    {
        "config_key": "CASE_STATUS",
        "label": "阻塞",
        "value": "4",
        "color": "#722ed1",
        "description": "用例阻塞",
        "sort": 4,
        "enabled": True,
    },

    # ---------- 评审状态 REVIEW_STATUS ----------
    {
        "config_key": "REVIEW_STATUS",
        "label": "待评审",
        "value": "0",
        "color": "#fadb14",
        "description": "待评审",
        "sort": 0,
        "enabled": True,
    },
    {
        "config_key": "REVIEW_STATUS",
        "label": "已评审",
        "value": "1",
        "color": "#52c41a",
        "description": "已评审通过",
        "sort": 1,
        "enabled": True,
    },
    {
        "config_key": "REVIEW_STATUS",
        "label": "评审未通过",
        "value": "2",
        "color": "#ff4d4f",
        "description": "评审未通过",
        "sort": 2,
        "enabled": True,
    },

    # ---------- 用例等级 CASE_LEVEL ----------
    {
        "config_key": "CASE_LEVEL",
        "label": "P0",
        "value": "P0",
        "color": "#990a0a",
        "description": "P0 - 致命/阻断级别",
        "sort": 0,
        "enabled": True,
    },
    {
        "config_key": "CASE_LEVEL",
        "label": "P1",
        "value": "P1",
        "color": "#f5222d",
        "description": "P1 - 严重级别",
        "sort": 1,
        "enabled": True,
    },
    {
        "config_key": "CASE_LEVEL",
        "label": "P2",
        "value": "P2",
        "color": "#fa8c16",
        "description": "P2 - 一般级别",
        "sort": 2,
        "enabled": True,
    },
    {
        "config_key": "CASE_LEVEL",
        "label": "P3",
        "value": "P3",
        "color": "#fadb14",
        "description": "P3 - 轻微/优化建议",
        "sort": 3,
        "enabled": True,
    },

    # ---------- 用例类型 CASE_TYPE ----------
    {
        "config_key": "CASE_TYPE",
        "label": "功能测试",
        "value": "GN",
        "color": "#1677ff",
        "description": "功能测试用例",
        "sort": 0,
        "enabled": True,
    },
    {
        "config_key": "CASE_TYPE",
        "label": "接口测试",
        "value": "JK",
        "color": "#13c2c2",
        "description": "接口测试用例",
        "sort": 1,
        "enabled": True,
    },
    {
        "config_key": "CASE_TYPE",
        "label": "性能测试",
        "value": "XN",
        "color": "#722ed1",
        "description": "性能测试用例",
        "sort": 2,
        "enabled": True,
    },
    {
        "config_key": "CASE_TYPE",
        "label": "安全测试",
        "value": "AQ",
        "color": "#eb2f96",
        "description": "安全测试用例",
        "sort": 3,
        "enabled": True,
    },
    {
        "config_key": "CASE_TYPE",
        "label": "兼容性测试",
        "value": "JR",
        "color": "#fa8c16",
        "description": "兼容性测试用例",
        "sort": 4,
        "enabled": True,
    },
    {
        "config_key": "CASE_TYPE",
        "label": "回归测试",
        "value": "HG",
        "color": "#52c41a",
        "description": "回归测试用例",
        "sort": 5,
        "enabled": True,
    },
    {
        "config_key": "CASE_TYPE",
        "label": "UI自动化",
        "value": "UI",
        "color": "#2f54eb",
        "description": "UI自动化测试用例",
        "sort": 6,
        "enabled": True,
    },

    # ---------- 用例优先级 CASE_PRIORITY ----------
    {
        "config_key": "CASE_PRIORITY",
        "label": "高",
        "value": "HIGH",
        "color": "#f5222d",
        "description": "高优先级",
        "sort": 0,
        "enabled": True,
    },
    {
        "config_key": "CASE_PRIORITY",
        "label": "中",
        "value": "MEDIUM",
        "color": "#faad14",
        "description": "中优先级",
        "sort": 1,
        "enabled": True,
    },
    {
        "config_key": "CASE_PRIORITY",
        "label": "低",
        "value": "LOW",
        "color": "#52c41a",
        "description": "低优先级",
        "sort": 2,
        "enabled": True,
    },
]


async def init_case_config():
    """
    初始化用例枚举配置默认数据

    仅在 case_config 表为空时执行导入，避免重复初始化。
    """
    from app.mapper.test_case.caseConfigMapper import CaseConfigMapper

    if await CaseConfigMapper.query_all():
        log.info("case_config 已存在数据，跳过初始化")
        return

    await CaseConfigMapper.init_case_configs(case_config_defaults)
    log.info("init_case_config success: 已导入 %d 条默认配置", len(case_config_defaults))
