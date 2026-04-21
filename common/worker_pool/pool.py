#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Redis Worker Pool 主模块

组合各个子模块，提供完整的任务池功能。
"""
import asyncio
import pickle
from typing import Any, Callable, Dict, List, Optional

from common import RedisClient
from common.worker_pool.connection import RedisConnectionManager, generate_server_id
from common.worker_pool.executor import TaskExecutor
from common.worker_pool.models import Job, JobStatus
from common.worker_pool.monitor import PoolMonitor
from common.worker_pool.queue import TaskQueue
from utils import MyLoguru

log = MyLoguru().get_logger()


class RedisWorkerPool:
    """
    Redis 任务工作池
    
    整合连接管理、任务队列、执行器和监控模块，提供完整的任务池功能。
    
    Features:
        - 基于优先级的任务队列
        - 多 Worker 并发执行
        - 任务超时控制
        - 死信队列支持
        - 实时监控统计
    
    Attributes:
        queue_name: 队列名称
        worker_count: Worker 数量
        server_id: 服务器唯一标识
        is_running: 运行状态
    
        # >>> pool = RedisWorkerPool.get_instance()
        # >>> await pool.start()
        # >>> await pool.submit_to_redis(func, job_id, "task_name")
    """
    
    _instances: Dict[str, 'RedisWorkerPool'] = {}

    @classmethod
    def get_instance(
        cls,
        queue_name: str = "default",
        worker_count: int = 5,
        server_id: str = None
    ) -> 'RedisWorkerPool':
        """
        获取单例实例（按队列名区分）
        
        Args:
            queue_name: 队列名称
            worker_count: Worker 数量
            server_id: 服务器 ID（可选）
            
        Returns:
            RedisWorkerPool 实例
        """
        instance_key = f"{queue_name}_{server_id or 'default'}"
        if instance_key not in cls._instances:
            cls._instances[instance_key] = cls(
                queue_name=queue_name,
                worker_count=worker_count,
                server_id=server_id
            )
        return cls._instances[instance_key]

    def __init__(
        self,
        queue_name: str = "default",
        worker_count: int = 5,
        server_id: str = None
    ):
        """
        初始化工作池
        
        Args:
            queue_name: 队列名称
            worker_count: Worker 数量
            server_id: 服务器 ID
        """
        self.queue_name = queue_name
        self.worker_count = worker_count
        self.server_id = server_id or generate_server_id()

        self._connection = RedisConnectionManager()
        self._queue = TaskQueue(queue_name)
        self._executor = TaskExecutor()
        self._monitor = PoolMonitor(
            queue_name=queue_name,
            queue_key=self._queue.queue_key,
            processing_key=self._queue.processing_key,
            job_data_key=self._queue.job_data_key,
            results_key=self._queue.results_key,
            dead_letter_key=self._queue.dead_letter_key,
            server_id=self.server_id,
            worker_count=self.worker_count
        )

        self.workers: List[asyncio.Task] = []
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None

        log.info(
            f"RedisWorkerPool init: Queue={queue_name}, "
            f"workers={worker_count}, server={self.server_id}"
        )

    @property
    def redis(self):
        """返回主 Redis 连接"""
        return self._connection.redis

    @property
    def function_registry(self) -> Dict[str, Callable]:
        """返回函数注册表"""
        return self._executor.function_registry

    def register_function(self, func: Callable = None):
        """
        注册执行函数（装饰器或直接调用）
        
        Args:
            func: 要注册的函数
        """
        return self._executor.register_function(func)

    def check_pool_ready(self) -> bool:
        """
        检查任务池是否就绪
        
        Returns:
            是否就绪
        """
        if not self.is_running:
            return False
        if not self._connection.is_connected:
            return False
        if self._connection.redis_client is None:
            return False
        return True

    async def start(self) -> None:
        """
        启动工作池
        
        初始化连接、加载脚本、启动 Worker 和监控任务。
        """
        if self.is_running:
            log.warning("RedisWorkerPool already running")
            return

        try:
            await self._connection.connect()
        except Exception as e:
            log.error(f"start fail, connect redis fail: {e}")
            raise

        self.is_running = True

        self.workers = [
            asyncio.create_task(self._worker(i), name=f"RedisWorker-{i}")
            for i in range(self.worker_count)
        ]

        self._monitor_task = asyncio.create_task(self._run_monitor(), name="RedisMonitor")

        log.info(
            f"====================== Redis工作池启动: "
            f"{self.worker_count} workers, server={self.server_id} ====================== "
        )

    async def stop(self) -> None:
        """
        停止工作池
        
        取消所有 Worker 和监控任务，断开连接。
        """
        if not self.is_running:
            return

        log.info("正在停止 Redis 工作池...")
        self.is_running = False

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        for worker in self.workers:
            if not worker.done():
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass

        await self._connection.disconnect()
        log.info("Redis 工作池已停止")

    async def set_redis_client(self, redis_client: RedisClient) -> None:
        """
        设置外部 Redis 客户端
        
        Args:
            redis_client: RedisClient 实例
        """
        self._connection.set_client(redis_client)

    async def submit_to_redis(
        self,
        func: Callable,
        job_id: str,
        job_name: str,
        job_args: tuple = (),
        job_kwargs: dict = None
    ) -> str:
        """
        提交任务到队列
        
        Args:
            func: 执行函数
            job_id: 任务 ID
            job_name: 任务名称
            job_args: 位置参数
            job_kwargs: 关键字参数
            
        Returns:
            任务 ID
        """
        if not self.check_pool_ready():
            raise RuntimeError("任务池未启动或 Redis 未连接")

        if not job_kwargs:
            job_kwargs = {}

        func_name = func.__name__
        job = Job(
            id=job_id,
            name=job_name,
            func_name=func_name,
            args=job_args,
            kwargs=job_kwargs
        )

        return await self._queue.submit_job(
            self.redis,
            self._connection.raw_redis,
            job
        )

    async def submit_batch_to_redis(
        self,
        func: Callable,
        job_infos: List[Dict[str, Any]]
    ) -> List[str]:
        """
        批量提交任务
        
        Args:
            func: 执行函数
            job_infos: 任务信息列表
            
        Returns:
            任务 ID 列表
        """
        if not self.check_pool_ready():
            raise RuntimeError("任务池未启动或 Redis 未连接")

        func_name = func.__name__
        jobs = []
        for info in job_infos:
            job = Job(
                id=info.get('job_id'),
                name=info.get('job_name', 'unnamed'),
                func_name=func_name,
                args=info.get('job_args', ()),
                kwargs=info.get('job_kwargs', {})
            )
            jobs.append(job)

        return await self._queue.submit_batch_jobs(self.redis, jobs)

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            job_id: 任务 ID
            
        Returns:
            任务状态字典
        """
        await self._connection.connect()
        return await self._monitor.get_job_status(
            job_id,
            self.redis,
            self._queue.job_data_key,
            self._queue.results_key
        )

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        await self._connection.connect()
        return await self._monitor.get_stats(self.redis)

    async def cancel_job(self, job_id: str) -> bool:
        """
        取消任务
        
        Args:
            job_id: 任务 ID
            
        Returns:
            是否成功取消
        """
        await self._connection.connect()
        return await self._queue.cancel_job(self.redis, job_id)

    async def retry_failed_jobs(self, limit: int = 10) -> List[str]:
        """
        重试失败的任务
        
        Args:
            limit: 最大重试数量
            
        Returns:
            重试的任务 ID 列表
        """
        await self._connection.connect()
        return await self._monitor.retry_failed_jobs(
            self.redis,
            self._queue.queue_key,
            self._queue.job_data_key,
            limit
        )

    async def cleanup_old_jobs(self, older_than_hours: int = 24, batch_size: int = 100) -> int:
        """
        清理旧任务
        
        Args:
            older_than_hours: 清理多少小时前的任务
            batch_size: 批处理大小
            
        Returns:
            清理的任务数量
        """
        await self._connection.connect()
        return await self._monitor.cleanup_old_jobs(
            self.redis,
            self._queue.job_data_key,
            self._queue.results_key,
            self._queue.processing_key,
            older_than_hours,
            batch_size
        )

    async def _worker(self, worker_id: int) -> None:
        """
        Worker 协程
        
        Args:
            worker_id: Worker 编号
        """
        worker_name = f"{self.server_id}_worker_{worker_id}"
        processing_key = f"{self._queue.processing_key}:{worker_name}"

        try:
            await self._connection.connect()
            log.info(f"worker:【{worker_name}】start, connect to redis success")
        except Exception as e:
            log.error(f"{worker_name} connect redis fail: {e}")
            return

        while self.is_running:
            try:
                try:
                    async with asyncio.timeout(1):
                        job_result = await self._queue.fetch_job_atomic(
                            self._connection.raw_redis,
                            self._connection.script_sha,
                            processing_key
                        )

                    if not job_result:
                        await asyncio.sleep(0.1)
                        continue

                    job_id, serialized_job = job_result
                    job_data = pickle.loads(serialized_job)
                    job = Job.from_dict(job_data)

                    log.info(f"{worker_name} 开始处理任务 {job.id}: {job.name}")
                    
                    await self._executor.mark_job_running(
                        job, worker_name, self.redis, self._queue.job_data_key
                    )
                    
                    await self._executor.execute_job(
                        job,
                        self.redis,
                        self._queue.results_key,
                        self._queue.dead_letter_key,
                        processing_key
                    )

                except asyncio.TimeoutError:
                    continue

            except asyncio.CancelledError:
                log.info(f"{worker_name} 被取消")
                break
            except Exception as e:
                log.exception(f"{worker_name} 异常: {e}")
                await asyncio.sleep(1)

    async def _run_monitor(self) -> None:
        """
        运行监控任务
        """
        try:
            log.info("[RedisMonitor] 启动")
            while self.is_running:
                await asyncio.sleep(5*60)
                try:
                    stats = await self.get_stats()
                    log.info(
                        f"[RedisMonitor] 队列: {stats.get('queue_size', 0)}, "
                        f"处理中: {stats.get('processing', 0)}, "
                        f"已完成: {stats.get('completed', 0)}, "
                        f"失败: {stats.get('failed', 0)}, "
                        f"服务器: {stats.get('servers', [])}"
                    )
                except Exception as e:
                    log.error(f"[RedisMonitor] 获取统计失败: {e}")

        except asyncio.CancelledError:
            log.info("[RedisMonitor] 停止")
