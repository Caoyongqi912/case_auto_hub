#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
元素定位缓存模块

提供LRU缓存机制来减少重复的元素定位操作，提升性能。
缓存基于页面ID、选择器和定位类型的组合键。
"""

import time
from typing import Optional, Dict, Tuple
from collections import OrderedDict
from playwright.async_api import Locator, Page


class LocatorCache:
    """
    元素定位缓存器

    使用LRU（最近最少使用）策略缓存元素定位器，减少重复定位操作。
    缓存键由页面ID、选择器和定位类型组成，确保定位器的唯一性。

    性能目标：减少30-40%的元素定位时间
    """

    def __init__(self, max_size: int = 100, ttl: float = 60.0):
        """
        初始化定位缓存器

        Args:
            max_size: 缓存最大容量，超过后移除最久未使用的项
            ttl: 缓存项生存时间（秒），超时后自动失效
        """
        self._cache: OrderedDict[str, Tuple[Locator, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def _make_cache_key(self, page: Page, selector: str, locate_type: str) -> str:
        """
        生成缓存键

        Args:
            page: 页面对象
            selector: 元素选择器
            locate_type: 定位类型

        Returns:
            缓存键字符串
        """
        return f"{id(page)}:{selector}:{locate_type}"

    def get(self, page: Page, selector: str, locate_type: str) -> Optional[Locator]:
        """
        从缓存获取定位器

        Args:
            page: 页面对象
            selector: 元素选择器
            locate_type: 定位类型

        Returns:
            缓存的定位器，如果不存在或已过期则返回None
        """
        cache_key = self._make_cache_key(page, selector, locate_type)

        if cache_key in self._cache:
            locator, timestamp = self._cache[cache_key]

            # 检查是否过期
            if time.time() - timestamp < self._ttl:
                # 移到末尾（标记为最近使用）
                self._cache.move_to_end(cache_key)
                self._hits += 1
                return locator
            else:
                # 过期，删除
                del self._cache[cache_key]

        self._misses += 1
        return None

    def set(self, page: Page, selector: str, locate_type: str, locator: Locator) -> None:
        """
        将定位器存入缓存

        Args:
            page: 页面对象
            selector: 元素选择器
            locate_type: 定位类型
            locator: 定位器对象
        """
        cache_key = self._make_cache_key(page, selector, locate_type)

        # 如果已存在，先删除（会重新添加到末尾）
        if cache_key in self._cache:
            del self._cache[cache_key]

        # 添加新项
        self._cache[cache_key] = (locator, time.time())

        # 检查容量，移除最久未使用的项
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def clear_page(self, page: Page) -> None:
        """
        清除特定页面的所有缓存

        Args:
            page: 要清除缓存的页面对象
        """
        page_id = id(page)
        keys_to_remove = [key for key in self._cache.keys() if key.startswith(f"{page_id}:")]
        for key in keys_to_remove:
            del self._cache[key]

    def get_stats(self) -> Dict[str, any]:
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


# 全局单例缓存实例
_global_cache: Optional[LocatorCache] = None


def get_global_cache() -> LocatorCache:
    """
    获取全局定位缓存实例

    Returns:
        全局LocatorCache单例
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = LocatorCache()
    return _global_cache


def reset_global_cache() -> None:
    """重置全局缓存实例"""
    global _global_cache
    if _global_cache:
        _global_cache.clear()
    _global_cache = None


__all__ = [
    "LocatorCache",
    "get_global_cache",
    "reset_global_cache",
]
