#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
浏览器上下文池模块

提供浏览器上下文的池化管理，支持上下文复用，减少初始化开销。
通过预创建和复用上下文，显著提升并发执行性能。
"""

import asyncio
from typing import Optional, List
from playwright.async_api import Browser, BrowserContext
from utils import log


class ContextPool:
    """
    浏览器上下文池

    管理多个浏览器上下文的生命周期，支持获取、释放和复用。
    避免频繁创建和销毁上下文，提升性能。

    性能目标：减少浏览器初始化开销90%+
    """

    def __init__(
        self,
        browser: Browser,
        max_contexts: int = 5,
        min_contexts: int = 1,
        context_config: Optional[dict] = None
    ):
        """
        初始化上下文池

        Args:
            browser: 浏览器实例
            max_contexts: 最大上下文数量
            min_contexts: 最小保持的上下文数量
            context_config: 上下文配置字典
        """
        self._browser = browser
        self._max_contexts = max_contexts
        self._min_contexts = min_contexts
        self._context_config = context_config or self._default_context_config()

        self._contexts: List[BrowserContext] = []
        self._available: List[BrowserContext] = []
        self._in_use: List[BrowserContext] = []
        self._lock = asyncio.Lock()

        self._total_created = 0
        self._total_acquired = 0
        self._total_released = 0

    def _default_context_config(self) -> dict:
        """
        获取默认上下文配置

        Returns:
            默认配置字典
        """
        from playwright.async_api import ViewportSize
        from config import Config

        return {
            "locale": "zh_CN",
            "ignore_https_errors": True,
            "timezone_id": "Asia/Shanghai",
            "viewport": ViewportSize(width=1920, height=1080),
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/144.0.0.0 Safari/537.36"
            )
        }

    async def initialize(self) -> None:
        """初始化上下文池，预创建最小数量的上下文"""
        async with self._lock:
            for _ in range(self._min_contexts):
                context = await self._create_context()
                self._contexts.append(context)
                self._available.append(context)

        log.info(
            f"[ContextPool] Initialized with {self._min_contexts} contexts "
            f"(max={self._max_contexts})"
        )

    async def acquire(self) -> BrowserContext:
        """
        获取可用上下文

        优先从可用池中获取，如果没有可用的且未达到最大数量则创建新的。
        如果达到最大数量则等待其他上下文释放。

        Returns:
            可用的浏览器上下文

        Raises:
            RuntimeError: 浏览器未连接
        """
        if not self._browser.is_connected():
            raise RuntimeError("Browser is not connected")

        async with self._lock:
            # 优先使用可用的上下文
            if self._available:
                context = self._available.pop()
                self._in_use.append(context)
                self._total_acquired += 1

                log.debug(
                    f"[ContextPool] Acquired existing context "
                    f"(available={len(self._available)}, in_use={len(self._in_use)})"
                )

                return context

            # 如果未达到最大数量，创建新的
            if len(self._contexts) < self._max_contexts:
                context = await self._create_context()
                self._contexts.append(context)
                self._in_use.append(context)
                self._total_acquired += 1

                log.debug(
                    f"[ContextPool] Created new context "
                    f"(total={len(self._contexts)}, in_use={len(self._in_use)})"
                )

                return context

        # 达到最大数量，等待可用上下文
        log.warning(
            f"[ContextPool] Max contexts reached ({self._max_contexts}), waiting..."
        )

        while True:
            await asyncio.sleep(0.1)
            async with self._lock:
                if self._available:
                    context = self._available.pop()
                    self._in_use.append(context)
                    self._total_acquired += 1
                    return context

    async def release(self, context: BrowserContext) -> None:
        """
        释放上下文

        清理上下文状态后放回可用池。

        Args:
            context: 要释放的上下文
        """
        async with self._lock:
            if context not in self._in_use:
                log.warning("[ContextPool] Releasing context not in use")
                return

            # 从使用中移除
            self._in_use.remove(context)

            # 清理上下文
            await self._cleanup_context(context)

            # 放回可用池
            self._available.append(context)
            self._total_released += 1

            log.debug(
                f"[ContextPool] Released context "
                f"(available={len(self._available)}, in_use={len(self._in_use)})"
            )

    async def _create_context(self) -> BrowserContext:
        """
        创建新的浏览器上下文

        Returns:
            新创建的上下文
        """
        from config import Config

        context = await self._browser.new_context(**self._context_config)
        context.set_default_navigation_timeout(Config.UI_Timeout)

        self._total_created += 1

        log.debug(f"[ContextPool] Created context (total={self._total_created})")

        return context

    async def _cleanup_context(self, context: BrowserContext) -> None:
        """
        清理上下文状态

        关闭所有页面，清除cookies和storage。

        Args:
            context: 要清理的上下文
        """
        try:
            # 关闭所有页面
            for page in context.pages:
                await page.close()

            # 清除cookies
            await context.clear_cookies()

            # 清除storage
            await context.clear_permissions()

        except Exception as e:
            log.error(f"[ContextPool] Context cleanup error: {e}")

    async def close_all(self) -> None:
        """关闭所有上下文"""
        async with self._lock:
            errors = []

            for context in self._contexts:
                try:
                    await context.close()
                except Exception as e:
                    errors.append(str(e))

            self._contexts.clear()
            self._available.clear()
            self._in_use.clear()

            if errors:
                log.error(f"[ContextPool] Close errors: {errors}")

        log.info(
            f"[ContextPool] Closed all contexts "
            f"(created={self._total_created}, acquired={self._total_acquired})"
        )

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            包含上下文数量、使用情况等统计信息的字典
        """
        return {
            "total_contexts": len(self._contexts),
            "available": len(self._available),
            "in_use": len(self._in_use),
            "max_contexts": self._max_contexts,
            "min_contexts": self._min_contexts,
            "total_created": self._total_created,
            "total_acquired": self._total_acquired,
            "total_released": self._total_released
        }


__all__ = ["ContextPool"]
