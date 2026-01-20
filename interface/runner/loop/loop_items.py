#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : loop_items
# @Software: PyCharm
# @Desc: 遍历循环执行器

import asyncio
import json

from app.model.interface import InterfaceAPI
from app.model.base import Env
from app.model.interface.InterfaceCaseStepContent import InterfaceCaseStepContent
from app.model.interface.interfaceResultModel import InterfaceContentResult
from enums import InterfaceExtractTargetVariablesEnum
from .base import LoopExecutor
from interface.writer import InterfaceAPIWriter


class LoopItemsExecutor(LoopExecutor):
    """遍历循环执行器"""
    
    async def execute(
        self,
        loop: InterfaceCaseStepContent,
        api_steps: list[InterfaceAPI],
        env: Env,
        content_result: InterfaceContentResult
    ):
        """
        items 遍历
        
        a = "1,2,3,4"
        b = [1,2,3,4]
        c = "{{a}},b,c,e"
        """
        try:
            items = json.loads(loop.loop_items)
        except json.JSONDecodeError:
            items = [item.strip() for item in loop.loop_items.split(',') if item.strip()]
        
        ALL_SUCCESS = True
        
        if items:
            total_apis = len(api_steps)
            item_key = loop.loop_item_key
            
            for item in items:
                for index, interface in enumerate(api_steps, start=1):
                    await self.starter.send(
                        f"✍️✍️  {'-' * 20} 执行数组循环步骤 [{item_key}:{item}] {index}/{total_apis}: "
                        f"{interface.name} {'-' * 20}"
                    )
                    
                    result, api_success = await self.interface_executor.execute(
                        interface=interface,
                        env=env,
                        temp_vars={
                            "key": item_key,
                            InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.LOOP,
                            "value": item
                        }
                    )
                    
                    await InterfaceAPIWriter.write_interface_result(
                        interface_loop_result_id=content_result.id,
                        **result
                    )
                    
                    if api_success is False:
                        ALL_SUCCESS = False
                    
                    if loop.loop_interval > 0:
                        await asyncio.sleep(loop.loop_interval)
        
        content_result.content_result = ALL_SUCCESS
        await InterfaceAPIWriter.set_content_finally_result(content_result)
