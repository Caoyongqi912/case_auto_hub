#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
独立 WorkPool 执行器入口

运行方式：
    python run_worker_pool.py --queue interface --workers 10
    python run_worker_pool.py --queue ui --workers 2
    python run_worker_pool.py --queue default --workers 5

说明：
    该进程专门消费 Redis 任务队列，不处理 HTTP 请求。
    Web 服务（Gunicorn）只负责任务提交，不启动 WorkPool。
"""
import argparse
import asyncio
import signal
import sys

# 确保业务任务函数被注册到 WorkPool
# noqa 用于抑制未使用导入的警告
from common.worker_pool import tasks  # noqa: F401
from common import rc
from common.worker_pool import RedisWorkerPool
from config import Config
from utils import MyLoguru

log = MyLoguru().get_logger()


async def main():
    parser = argparse.ArgumentParser(description="CaseAutoHub WorkPool Worker")
    parser.add_argument(
        "--queue",
        type=str,
        default="default",
        help="队列名称，默认 default"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Worker 数量，默认 5"
    )
    parser.add_argument(
        "--graceful-timeout",
        type=float,
        default=60.0,
        help="优雅退出等待超时时间（秒），默认 60"
    )
    args = parser.parse_args()

    log.info(
        f"[WorkPool] 准备启动: queue={args.queue}, "
        f"workers={args.workers}, graceful_timeout={args.graceful_timeout}"
    )

    # 初始化 Redis 连接池
    await rc.init_pool()

    # 获取队列对应的 WorkPool 实例
    pool = RedisWorkerPool.get_instance(
        queue_name=args.queue,
        worker_count=args.workers
    )
    await pool.set_redis_client(rc)

    loop = asyncio.get_event_loop()

    # 注册信号处理器，实现优雅退出
    async def _signal_handler():
        log.info("[WorkPool] 收到停止信号，开始优雅退出...")
        await pool.stop(graceful_timeout=args.graceful_timeout)

    def _on_signal():
        asyncio.create_task(_signal_handler())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows 不支持 SIGTERM，回退到 signal.signal
            signal.signal(sig, lambda s, f: _on_signal())

    # 启动 WorkPool
    await pool.start()

    # 保持进程运行，直到 pool 停止
    try:
        while pool.is_running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        if pool.is_running:
            await pool.stop(graceful_timeout=args.graceful_timeout)
        await rc.close_pool()
        log.info("[WorkPool] 已退出")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("[WorkPool] 被手动停止")
        sys.exit(0)
