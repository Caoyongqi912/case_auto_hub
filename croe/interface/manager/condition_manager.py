#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : condition_manager
# @Software: PyCharm
# @Desc: 条件管理器模块

from typing import Any, Tuple, TYPE_CHECKING

from app.model.interface.InterfaceCaseStepContent import InterfaceCondition
from croe.a_manager import VariableManager
from utils.assertsUtil import MyAsserts
from utils.io_sender import SocketSender
from enums.CaseEnum import operatorMap

if TYPE_CHECKING:
    pass


class ConditionManager:
    """条件管理器，用于执行条件判断"""

    key: Any
    value: Any
    operator: int
    condition: InterfaceCondition

    def __init__(self, variable: VariableManager) -> None:
        """
        初始化条件管理器

        Args:
            variable: 变量管理器实例
        """
        self.variable = variable

    async def invoke(
        self,
        condition: InterfaceCondition,
        io: SocketSender
    ) -> Tuple[bool, dict]:
        """
        执行条件判断

        Args:
            condition: 条件配置对象
            io: 消息发送器

        Returns:
            Tuple[是否通过, 条件数据字典]
        """
        self.condition = condition
        self.key = await self.variable.trans(condition.condition_key)
        self.value = await self.variable.trans(condition.condition_value)
        self.operator = condition.condition_operator

        await io.send(
            f"条件判断 >>  变量 {condition.condition_key}  AKA {self.key} "
            f"{operatorMap[self.operator]} value {self.value}"
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
    def doc(self) -> str:
        """
        获取条件文档描述

        Returns:
            条件描述字符串
        """
        return (
            f"判断：IF {self.condition.condition_key}  "
            f"{operatorMap[self.operator]} {self.value}"
        )
