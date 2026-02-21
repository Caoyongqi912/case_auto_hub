#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/2/3
# @Author : cyq
# @File : playResultMapper
# @Software: PyCharm
# @Desc:

from app.model import async_session
from app.model.playUI.PlayResult import PlayStepContentResult
from app.mapper import Mapper
from utils import log


class PlayContentResultMapper(Mapper[PlayStepContentResult]):
    __model__ = PlayStepContentResult

    @classmethod
    async def set_result(cls, result: PlayStepContentResult):
        try:
            async with async_session() as session:
                async with session.begin():
                    await cls.add_flush_expunge(session, result)
        except Exception as e:
            log.error(e)
            raise e


    @classmethod
    async def save_result_batch(cls, content_results: dict) -> int:
        """
        批量插入带父子关系的结果
        
        Args:
            content_results: 嵌套结构字典
                {step_index: {"result": parent_result, "children": [child1, child2, ...]}}
        
        Returns:
            int: 插入的总数量
        """
        total_count = 0
        try:
            sorted_indices = sorted(content_results.keys())
            async with async_session() as session:
                async with session.begin():
                    for idx in sorted_indices:
                        item = content_results[idx]
                        parent_result = item["result"]
                        children = item["children"]
           
                        # 1. 插入父步骤
                        session.add(parent_result)
                        await session.flush()  # flush 获得 id
                        total_count += 1
                        
                        # 2. 如果有子步骤，设置 parent_result_id 后插入
                        if children:
                            for child in children:
                                child.parent_result_id = parent_result.id
                            session.add_all(children)
                            total_count += len(children)
                    
            log.info(f"[PlayContentResultMapper] Batch inserted {total_count} results with parent relationships")
            return total_count
        except Exception as e:
            log.error(f"[PlayContentResultMapper] Error saving results with children: {e}")
            raise
