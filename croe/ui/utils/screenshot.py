#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
异步截图处理模块

提供非阻塞的截图捕获功能，避免截图操作阻塞主执行流程。
通过异步任务队列处理截图，显著降低截图开销。
"""

import asyncio
from typing import Optional
from pathlib import Path
from playwright.async_api import Page
from utils import log


class AsyncScreenshot:
    """
    异步截图处理器

    将截图操作放入后台异步执行，避免阻塞主流程。
    适用于错误截图、调试截图等非关键路径场景。

    性能目标：将截图开销从1.5-3.5秒降低到接近0秒（异步处理）
    """

    def __init__(self, max_workers: int = 2):
        """
        初始化异步截图处理器

        Args:
            max_workers: 最大并发截图任务数
        """
        self._max_workers = max_workers
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._total_captured = 0
        self._total_failed = 0

    async def start(self) -> None:
        """启动后台工作线程"""
        if self._running:
            return

        self._running = True
        for i in range(self._max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        log.info(f"[AsyncScreenshot] Started {self._max_workers} workers")

    async def stop(self) -> None:
        """停止后台工作线程，等待所有任务完成"""
        if not self._running:
            return

        self._running = False

        # 等待队列清空
        await self._queue.join()

        # 取消所有工作线程
        for worker in self._workers:
            worker.cancel()

        # 等待工作线程结束
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        log.info(
            f"[AsyncScreenshot] Stopped. "
            f"Total captured: {self._total_captured}, Failed: {self._total_failed}"
        )

    async def capture_async(
        self,
        page: Page,
        path: str,
        full_page: bool = False,
        timeout: float = 30000
    ) -> None:
        """
        异步捕获截图

        将截图任务放入队列，立即返回，不阻塞主流程。

        Args:
            page: 页面对象
            path: 截图保存路径
            full_page: 是否截取整个页面
            timeout: 超时时间（毫秒）
        """
        if not self._running:
            await self.start()

        await self._queue.put({
            "page": page,
            "path": path,
            "full_page": full_page,
            "timeout": timeout
        })

    async def capture_sync(
        self,
        page: Page,
        path: str,
        full_page: bool = False,
        timeout: float = 30000
    ) -> bool:
        """
        同步捕获截图

        直接执行截图操作，等待完成后返回。
        用于必须立即获取截图的场景。

        Args:
            page: 页面对象
            path: 截图保存路径
            full_page: 是否截取整个页面
            timeout: 超时时间（毫秒）

        Returns:
            是否成功
        """
        return await self._capture(page, path, full_page, timeout)

    async def _worker(self, worker_id: int) -> None:
        """
        后台工作线程

        持续从队列中获取截图任务并执行。

        Args:
            worker_id: 工作线程ID
        """
        log.info(f"[AsyncScreenshot] Worker {worker_id} started")

        while self._running:
            try:
                # 从队列获取任务，超时1秒
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # 执行截图
                success = await self._capture(
                    task["page"],
                    task["path"],
                    task["full_page"],
                    task["timeout"]
                )

                if success:
                    self._total_captured += 1
                else:
                    self._total_failed += 1

                # 标记任务完成
                self._queue.task_done()

            except asyncio.TimeoutError:
                # 队列为空，继续等待
                continue
            except asyncio.CancelledError:
                # 工作线程被取消
                break
            except Exception as e:
                log.error(f"[AsyncScreenshot] Worker {worker_id} error: {e}")
                self._total_failed += 1
                self._queue.task_done()

        log.info(f"[AsyncScreenshot] Worker {worker_id} stopped")

    async def _capture(
        self,
        page: Page,
        path: str,
        full_page: bool,
        timeout: float
    ) -> bool:
        """
        执行截图操作

        Args:
            page: 页面对象
            path: 截图保存路径
            full_page: 是否截取整个页面
            timeout: 超时时间（毫秒）

        Returns:
            是否成功
        """
        try:
            # 确保目录存在
            Path(path).parent.mkdir(parents=True, exist_ok=True)

            # 执行截图
            await page.screenshot(
                path=path,
                full_page=full_page,
                timeout=timeout
            )

            log.debug(f"[AsyncScreenshot] Captured: {path}")
            return True

        except Exception as e:
            log.error(f"[AsyncScreenshot] Capture failed for {path}: {e}")
            return False

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            包含队列大小、已捕获数量等统计信息的字典
        """
        return {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "workers": len(self._workers),
            "total_captured": self._total_captured,
            "total_failed": self._total_failed
        }


# 全局单例实例
_global_screenshot: Optional[AsyncScreenshot] = None


def get_global_screenshot() -> AsyncScreenshot:
    """
    获取全局异步截图实例

    Returns:
        全局AsyncScreenshot单例
    """
    global _global_screenshot
    if _global_screenshot is None:
        _global_screenshot = AsyncScreenshot()
    return _global_screenshot


async def cleanup_global_screenshot() -> None:
    """清理全局截图实例"""
    global _global_screenshot
    if _global_screenshot:
        await _global_screenshot.stop()
    _global_screenshot = None


__all__ = [
    "AsyncScreenshot",
    "get_global_screenshot",
    "cleanup_global_screenshot",
]
