#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/3/20
# @Author : cyq
# @File : condition_manager
# @Software: PyCharm
# @Desc:
from typing import Any, Protocol
from croe.a_manager import VariableManager
from utils.assertsUtil import MyAsserts
from utils.io_sender import SocketSender
from enums.CaseEnum import operatorMap


class ConditionProtocol(Protocol):
    """条件协议 - 任何具有以下属性的对象都可以使用"""
    condition_key: str
    condition_value: str
    condition_operator: int


class ConditionManager:
    """
    条件判断管理器
    支持任何符合 ConditionProtocol 协议的对象
    """
    key: Any
    value: Any
    operator: int
    condition: ConditionProtocol

    def __init__(self, variable: VariableManager):
        self.variable = variable

    async def invoke(self, condition: ConditionProtocol, io: SocketSender) -> tuple[bool, dict]:
        """
        执行条件判断
        :param condition: 条件对象（需符合 ConditionProtocol 协议）
        :param io: 输出对象
        :return: (是否通过, 判断数据)
        """
        self.condition = condition
        self.key = await self.variable.trans(condition.condition_key)
        self.value = await self.variable.trans(condition.condition_value)
        self.operator = condition.condition_operator

        await io.send(
            f"条件判断 >>  变量 {condition.condition_key}  AKA {self.key} {operatorMap[self.operator]} value {self.value}"
        )

        assert_data = {
            "key": self.key,
            "value": self.value,
            "operator": self.operator,
        }

        try:
            MyAsserts.option(
                assertOpt=self.operator,
                expect=self.value,
                actual=self.key
            )
            assert_data["condition_result"] = True
            return True, assert_data
        except AssertionError as e:
            await io.send(f"条件判断 >> {str(e)}")
            assert_data["condition_result"] = False
            return False, assert_data

    @property
    def doc(self):
        return f"判断：IF {self.condition.condition_key}  {operatorMap[self.operator]} {self.value}"
