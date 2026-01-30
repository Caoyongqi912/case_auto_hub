#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
批量结果写入模块

提供批量数据库写入功能，显著提升数据库操作性能。
通过缓冲区和批量提交机制，减少数据库I/O次数。
"""

import time
import asyncio
from typing import List, Dict, Any, Optional
from utils import log


class BatchResultWriter:
    """
    批量结果写入器

    缓冲变量提取和断言结果，达到批量大小或时间间隔后统一写入数据库。
    避免频繁的单条数据库操作，显著提升性能。

    性能目标：将数据库写入时间从20-150秒/100步骤优化到2-15秒/100步骤（提升90-95%）
    """

    def __init__(self, batch_size: int = 50, flush_interval: float = 5.0):
        """
        初始化批量写入器

        Args:
            batch_size: 批量大小，达到此数量时自动刷新
            flush_interval: 刷新时间间隔（秒），超过此时间自动刷新
        """
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._vars_buffer: List[Dict[str, Any]] = []
        self._asserts_buffer: List[Dict[str, Any]] = []
        self._last_flush = time.time()
        self._lock = asyncio.Lock()
        self._total_vars = 0
        self._total_asserts = 0

    async def add_var(
        self,
        case_result,
        step_name: str,
        extract_method: str,
        var_info: Dict[str, Any]
    ) -> None:
        """
        添加变量提取结果到缓冲区

        Args:
            case_result: 用例结果对象
            step_name: 步骤名称
            extract_method: 提取方法
            var_info: 变量信息字典，包含变量名和值
        """
        async with self._lock:
            self._vars_buffer.append({
                "case_result": case_result,
                "step_name": step_name,
                "extract_method": extract_method,
                "var_info": var_info
            })
            await self._check_and_flush(case_result)

    async def add_assert(
        self,
        case_result,
        step_name: str,
        assert_method: str,
        assert_result: bool,
        assert_message: str
    ) -> None:
        """
        添加断言结果到缓冲区

        Args:
            case_result: 用例结果对象
            step_name: 步骤名称
            assert_method: 断言方法
            assert_result: 断言结果（True/False）
            assert_message: 断言消息
        """
        async with self._lock:
            self._asserts_buffer.append({
                "case_result": case_result,
                "step_name": step_name,
                "assert_method": assert_method,
                "assert_result": assert_result,
                "assert_message": assert_message
            })
            await self._check_and_flush(case_result)

    async def _check_and_flush(self, case_result) -> None:
        """
        检查是否需要刷新缓冲区

        当缓冲区大小达到批量大小或距离上次刷新超过时间间隔时，执行刷新。

        Args:
            case_result: 用例结果对象
        """
        total_buffered = len(self._vars_buffer) + len(self._asserts_buffer)
        time_elapsed = time.time() - self._last_flush

        if total_buffered >= self._batch_size or time_elapsed >= self._flush_interval:
            await self._flush(case_result)

    async def _flush(self, case_result) -> None:
        """
        刷新缓冲区，批量写入数据库

        Args:
            case_result: 用例结果对象
        """
        if not self._vars_buffer and not self._asserts_buffer:
            return

        start_time = time.time()

        try:
            # 批量写入变量
            if self._vars_buffer:
                await self._flush_vars(case_result)

            # 批量写入断言
            if self._asserts_buffer:
                await self._flush_asserts(case_result)

            elapsed = time.time() - start_time
            log.info(
                f"[BatchWriter] Flushed {len(self._vars_buffer)} vars and "
                f"{len(self._asserts_buffer)} asserts in {elapsed:.3f}s"
            )

        except Exception as e:
            log.error(f"[BatchWriter] Flush error: {e}")
            raise
        finally:
            # 清空缓冲区
            self._total_vars += len(self._vars_buffer)
            self._total_asserts += len(self._asserts_buffer)
            self._vars_buffer.clear()
            self._asserts_buffer.clear()
            self._last_flush = time.time()

    async def _flush_vars(self, case_result) -> None:
        """
        批量写入变量提取结果

        Args:
            case_result: 用例结果对象
        """
        from app.mapper.play.playResultMapper import PlayResultMapper

        # 构建批量插入数据
        var_records = []
        for item in self._vars_buffer:
            for var_name, var_value in item["var_info"].items():
                var_records.append({
                    "case_result_id": case_result.id,
                    "step_name": item["step_name"],
                    "extract_method": item["extract_method"],
                    "var_name": var_name,
                    "var_value": str(var_value)
                })

        if var_records:
            # 批量插入
            await PlayResultMapper.batch_insert_vars(var_records)

    async def _flush_asserts(self, case_result) -> None:
        """
        批量写入断言结果

        Args:
            case_result: 用例结果对象
        """
        from app.mapper.play.playResultMapper import PlayResultMapper

        # 构建批量插入数据
        assert_records = []
        for item in self._asserts_buffer:
            assert_records.append({
                "case_result_id": case_result.id,
                "step_name": item["step_name"],
                "assert_method": item["assert_method"],
                "assert_result": item["assert_result"],
                "assert_message": item["assert_message"]
            })

        if assert_records:
            # 批量插入
            await PlayResultMapper.batch_insert_asserts(assert_records)

    async def force_flush(self, case_result) -> None:
        """
        强制刷新缓冲区

        在用例执行结束时调用，确保所有缓冲数据都被写入。

        Args:
            case_result: 用例结果对象
        """
        async with self._lock:
            await self._flush(case_result)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取写入统计信息

        Returns:
            包含缓冲区大小、已写入数量等统计信息的字典
        """
        return {
            "vars_buffered": len(self._vars_buffer),
            "asserts_buffered": len(self._asserts_buffer),
            "total_vars_written": self._total_vars,
            "total_asserts_written": self._total_asserts,
            "batch_size": self._batch_size,
            "flush_interval": self._flush_interval
        }


__all__ = ["BatchResultWriter"]
