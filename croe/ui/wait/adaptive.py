#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
自适应等待策略模块

根据历史元素出现时间动态调整等待超时，减少不必要的等待时间。
通过学习元素加载模式，优化等待策略。
"""

import time
from typing import Dict, List, Optional
from collections import defaultdict
from playwright.async_api import Locator
from utils import log


class AdaptiveWaitStrategy:
    """
    自适应等待策略

    记录每个元素的历史出现时间，根据统计数据预测合理的等待超时。
    避免固定超时导致的过长等待或过短超时。

    性能目标：减少40-50%的等待时间
    """

    def __init__(
        self,
        min_timeout: float = 1000,
        max_timeout: float = 30000,
        default_timeout: float = 10000,
        history_size: int = 10
    ):
        """
        初始化自适应等待策略

        Args:
            min_timeout: 最小超时时间（毫秒）
            max_timeout: 最大超时时间（毫秒）
            default_timeout: 默认超时时间（毫秒）
            history_size: 保留的历史记录数量
        """
        self._min_timeout = min_timeout
        self._max_timeout = max_timeout
        self._default_timeout = default_timeout
        self._history_size = history_size

        # 元素选择器 -> 出现时间列表（毫秒）
        self._element_stats: Dict[str, List[float]] = defaultdict(list)

        # 统计信息
        self._total_waits = 0
        self._total_time_saved = 0.0

    def _get_selector_key(self, selector: str, state: str = "visible") -> str:
        """
        生成选择器统计键

        Args:
            selector: 元素选择器
            state: 等待状态

        Returns:
            统计键字符串
        """
        return f"{selector}:{state}"

    def predict_timeout(self, selector: str, state: str = "visible") -> float:
        """
        预测元素等待超时时间

        基于历史数据计算合理的超时时间。
        使用平均值 + 1.5倍标准差作为预测值，确保95%的情况下不会超时。

        Args:
            selector: 元素选择器
            state: 等待状态

        Returns:
            预测的超时时间（毫秒）
        """
        key = self._get_selector_key(selector, state)
        history = self._element_stats.get(key, [])

        if not history:
            # 无历史数据，使用默认超时
            return self._default_timeout

        # 计算平均值和标准差
        avg = sum(history) / len(history)
        variance = sum((x - avg) ** 2 for x in history) / len(history)
        std_dev = variance ** 0.5

        # 预测超时 = 平均值 + 1.5倍标准差
        predicted = avg + 1.5 * std_dev

        # 限制在最小和最大超时范围内
        timeout = max(self._min_timeout, min(predicted, self._max_timeout))

        log.debug(
            f"[AdaptiveWait] Predicted timeout for {selector}: "
            f"{timeout:.0f}ms (avg={avg:.0f}ms, std={std_dev:.0f}ms)"
        )

        return timeout

    async def smart_wait(
        self,
        locator: Locator,
        selector: str,
        state: str = "visible"
    ) -> float:
        """
        智能等待元素

        使用预测的超时时间等待元素，并记录实际等待时间。

        Args:
            locator: 元素定位器
            selector: 元素选择器
            state: 等待状态

        Returns:
            实际等待时间（毫秒）

        Raises:
            TimeoutError: 等待超时
        """
        # 预测超时时间
        timeout = self.predict_timeout(selector, state)

        # 记录开始时间
        start_time = time.time()

        try:
            # 等待元素
            await locator.wait_for(state=state, timeout=timeout)

            # 计算实际等待时间
            actual_time = (time.time() - start_time) * 1000

            # 更新统计
            self._update_stats(selector, state, actual_time)

            # 计算节省的时间（相对于默认超时）
            time_saved = self._default_timeout - timeout
            if time_saved > 0:
                self._total_time_saved += time_saved

            self._total_waits += 1

            log.debug(
                f"[AdaptiveWait] Element appeared in {actual_time:.0f}ms "
                f"(timeout={timeout:.0f}ms, saved={time_saved:.0f}ms)"
            )

            return actual_time

        except Exception as e:
            # 等待失败，记录超时时间
            actual_time = (time.time() - start_time) * 1000
            log.warning(
                f"[AdaptiveWait] Wait failed for {selector} after {actual_time:.0f}ms: {e}"
            )
            raise

    def _update_stats(self, selector: str, state: str, actual_time: float) -> None:
        """
        更新元素统计信息

        Args:
            selector: 元素选择器
            state: 等待状态
            actual_time: 实际等待时间（毫秒）
        """
        key = self._get_selector_key(selector, state)
        history = self._element_stats[key]

        # 添加新记录
        history.append(actual_time)

        # 保持历史记录大小
        if len(history) > self._history_size:
            history.pop(0)

    def get_stats(self) -> Dict[str, any]:
        """
        获取统计信息

        Returns:
            包含总等待次数、节省时间等统计信息的字典
        """
        total_elements = len(self._element_stats)
        avg_time_saved = (
            self._total_time_saved / self._total_waits
            if self._total_waits > 0
            else 0
        )

        return {
            "total_waits": self._total_waits,
            "total_time_saved_ms": self._total_time_saved,
            "avg_time_saved_ms": avg_time_saved,
            "tracked_elements": total_elements,
            "min_timeout": self._min_timeout,
            "max_timeout": self._max_timeout,
            "default_timeout": self._default_timeout
        }

    def clear(self) -> None:
        """清空所有统计数据"""
        self._element_stats.clear()
        self._total_waits = 0
        self._total_time_saved = 0.0


# 全局单例实例
_global_adaptive_wait: Optional[AdaptiveWaitStrategy] = None


def get_global_adaptive_wait() -> AdaptiveWaitStrategy:
    """
    获取全局自适应等待策略实例

    Returns:
        全局AdaptiveWaitStrategy单例
    """
    global _global_adaptive_wait
    if _global_adaptive_wait is None:
        _global_adaptive_wait = AdaptiveWaitStrategy()
    return _global_adaptive_wait


def reset_global_adaptive_wait() -> None:
    """重置全局自适应等待策略实例"""
    global _global_adaptive_wait
    if _global_adaptive_wait:
        _global_adaptive_wait.clear()
    _global_adaptive_wait = None


__all__ = [
    "AdaptiveWaitStrategy",
    "get_global_adaptive_wait",
    "reset_global_adaptive_wait",
]
