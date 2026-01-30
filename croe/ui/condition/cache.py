#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
条件判断缓存模块

缓存条件表达式的判断结果，避免重复计算相同条件。
适用于循环或重复执行的步骤中的条件判断。
"""

import time
import hashlib
import json
from typing import Any, Dict, Optional, Tuple
from collections import OrderedDict
from utils import log


class ConditionCache:
    """
    条件判断缓存器

    缓存条件表达式及其变量上下文的判断结果，避免重复计算。
    使用LRU策略管理缓存，支持TTL过期机制。

    性能目标：提升80-90%的条件判断性能
    """

    def __init__(self, max_size: int = 200, ttl: float = 60.0):
        """
        初始化条件缓存器

        Args:
            max_size: 缓存最大容量
            ttl: 缓存项生存时间（秒）
        """
        self._cache: OrderedDict[str, Tuple[bool, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def _make_cache_key(self, condition: str, variables: Dict[str, Any]) -> str:
        """
        生成缓存键

        基于条件表达式和变量值生成唯一的缓存键。
        使用哈希确保键的唯一性和长度可控。

        Args:
            condition: 条件表达式字符串
            variables: 变量字典

        Returns:
            缓存键字符串
        """
        # 将变量字典排序后序列化，确保相同变量生成相同键
        sorted_vars = json.dumps(variables, sort_keys=True, default=str)

        # 组合条件和变量
        key_data = f"{condition}:{sorted_vars}"

        # 生成哈希
        key_hash = hashlib.md5(key_data.encode()).hexdigest()

        return key_hash

    def get(self, condition: str, variables: Dict[str, Any]) -> Optional[bool]:
        """
        从缓存获取条件判断结果

        Args:
            condition: 条件表达式字符串
            variables: 变量字典

        Returns:
            缓存的判断结果，如果不存在或已过期则返回None
        """
        cache_key = self._make_cache_key(condition, variables)

        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]

            # 检查是否过期
            if time.time() - timestamp < self._ttl:
                # 移到末尾（标记为最近使用）
                self._cache.move_to_end(cache_key)
                self._hits += 1

                log.debug(
                    f"[ConditionCache] Cache hit for condition: {condition[:50]}..."
                )

                return result
            else:
                # 过期，删除
                del self._cache[cache_key]

        self._misses += 1
        return None

    def set(self, condition: str, variables: Dict[str, Any], result: bool) -> None:
        """
        将条件判断结果存入缓存

        Args:
            condition: 条件表达式字符串
            variables: 变量字典
            result: 判断结果
        """
        cache_key = self._make_cache_key(condition, variables)

        # 如果已存在，先删除（会重新添加到末尾）
        if cache_key in self._cache:
            del self._cache[cache_key]

        # 添加新项
        self._cache[cache_key] = (result, time.time())

        # 检查容量，移除最久未使用的项
        if len(self._cache) > self._max_size:
            removed_key, _ = self._cache.popitem(last=False)
            log.debug(f"[ConditionCache] Evicted oldest entry")

        log.debug(
            f"[ConditionCache] Cached result for condition: "
            f"{condition[:50]}... = {result}"
        )

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        log.info("[ConditionCache] Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含命中率、缓存大小等统计信息的字典
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "ttl": self._ttl
        }


class CachedConditionChecker:
    """
    带缓存的条件检查器

    封装条件判断逻辑，自动使用缓存优化性能。
    """

    def __init__(self, cache: Optional[ConditionCache] = None):
        """
        初始化条件检查器

        Args:
            cache: 条件缓存实例，如果为None则创建新实例
        """
        self._cache = cache or ConditionCache()

    async def check(
        self,
        condition: str,
        variables: Dict[str, Any],
        force_refresh: bool = False
    ) -> bool:
        """
        检查条件是否满足

        优先从缓存获取结果，缓存未命中时执行实际判断。

        Args:
            condition: 条件表达式字符串
            variables: 变量字典
            force_refresh: 是否强制刷新缓存

        Returns:
            条件判断结果
        """
        # 如果不强制刷新，先尝试从缓存获取
        if not force_refresh:
            cached_result = self._cache.get(condition, variables)
            if cached_result is not None:
                return cached_result

        # 执行实际判断
        start_time = time.time()
        result = await self._evaluate_condition(condition, variables)
        elapsed = (time.time() - start_time) * 1000

        log.debug(
            f"[ConditionChecker] Evaluated condition in {elapsed:.2f}ms: "
            f"{condition[:50]}... = {result}"
        )

        # 存入缓存
        self._cache.set(condition, variables, result)

        return result

    async def _evaluate_condition(
        self,
        condition: str,
        variables: Dict[str, Any]
    ) -> bool:
        """
        执行条件判断

        Args:
            condition: 条件表达式字符串
            variables: 变量字典

        Returns:
            判断结果
        """
        try:
            # 创建安全的执行环境
            safe_globals = {
                "__builtins__": {
                    "True": True,
                    "False": False,
                    "None": None,
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "len": len,
                }
            }

            # 执行条件表达式
            result = eval(condition, safe_globals, variables)

            return bool(result)

        except Exception as e:
            log.error(f"[ConditionChecker] Condition evaluation error: {e}")
            log.error(f"  Condition: {condition}")
            log.error(f"  Variables: {variables}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self._cache.get_stats()

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()


# 全局单例实例
_global_condition_cache: Optional[ConditionCache] = None
_global_condition_checker: Optional[CachedConditionChecker] = None


def get_global_condition_cache() -> ConditionCache:
    """
    获取全局条件缓存实例

    Returns:
        全局ConditionCache单例
    """
    global _global_condition_cache
    if _global_condition_cache is None:
        _global_condition_cache = ConditionCache()
    return _global_condition_cache


def get_global_condition_checker() -> CachedConditionChecker:
    """
    获取全局条件检查器实例

    Returns:
        全局CachedConditionChecker单例
    """
    global _global_condition_checker
    if _global_condition_checker is None:
        cache = get_global_condition_cache()
        _global_condition_checker = CachedConditionChecker(cache)
    return _global_condition_checker


def reset_global_condition_cache() -> None:
    """重置全局条件缓存实例"""
    global _global_condition_cache, _global_condition_checker
    if _global_condition_cache:
        _global_condition_cache.clear()
    _global_condition_cache = None
    _global_condition_checker = None


__all__ = [
    "ConditionCache",
    "CachedConditionChecker",
    "get_global_condition_cache",
    "get_global_condition_checker",
    "reset_global_condition_cache",
]
