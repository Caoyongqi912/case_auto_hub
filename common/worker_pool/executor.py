#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
任务执行器模块

负责任务的实际执行、状态更新和结果处理。
"""
import asyncio
import json
import pickle
import time
from typing import Any, Callable, Dict, Optional

from common.worker_pool.models import Job, JobStatus
from utils import MyLoguru

log = MyLoguru().get_logger()

DEFAULT_JOB_TIMEOUT = 3600


class TaskExecutor:
    """
    任务执行器
    
    负责任务的实际执行、超时控制、状态更新和结果处理。
    
    Attributes:
        function_registry: 已注册函数的字典
        job_timeout: 任务执行超时时间（秒）

    """
    
    def __init__(self, job_timeout: int = DEFAULT_JOB_TIMEOUT):
        """
        初始化任务执行器
        
        Args:
            job_timeout: 任务执行超时时间（秒），默认 3600
        """
        self.function_registry: Dict[str, Callable] = {}
        self.job_timeout = job_timeout

    def register_function(self, func: Callable = None):
        """
        注册执行函数（装饰器或直接调用）
        
        Args:
            func: 要注册的函数
            
        Returns:
            装饰器或原函数

        """
        def decorator(f: Callable):
            func_name = f.__name__
            self.function_registry[func_name] = f
            log.info(f"TaskExecutor register function: {func_name}")
            return f

        if func is None:
            return decorator
        return decorator(func)

    def get_function(self, func_name: str) -> Optional[Callable]:
        """
        获取已注册的函数
        
        Args:
            func_name: 函数名称
            
        Returns:
            函数对象，或 None
        """
        return self.function_registry.get(func_name)

    async def execute_job(
        self,
        job: Job,
        redis_client,
        results_key: str,
        dead_letter_key: str,
        processing_key: str
    ) -> None:
        """
        执行任务
        
        执行任务的完整流程：运行中状态 -> 执行 -> 完成/失败 -> 清理。
        
        Args:
            job: 任务对象
            redis_client: Redis 客户端
            results_key: 结果存储键
            dead_letter_key: 死信队列键
            processing_key: 处理中任务键
        """
        try:
            if job.func_name not in self.function_registry:
                raise ValueError(f"找不到函数: {job.func_name}")

            _func = self.function_registry[job.func_name]

            try:
                async with asyncio.timeout(self.job_timeout):
                    _func_result = await _func(*job.args, **job.kwargs)
            except asyncio.TimeoutError:
                raise TimeoutError(f"任务执行超时 ({self.job_timeout}秒)")

            await self._mark_job_completed(job, _func_result, redis_client, results_key)

            log.info(f"任务 {job} 执行完成 result: {_func_result} 耗时 {job.duration:.2f}s")

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.end_time = time.time()
            raise

        except Exception as e:
            await self._mark_job_failed(job, e, redis_client, dead_letter_key)
            log.error(f"任务执行失败: {e}")

        finally:
            await self._cleanup_job(job, redis_client, processing_key)

    async def mark_job_running(
        self,
        job: Job,
        worker_name: str,
        redis_client,
        job_data_key: str
    ) -> None:
        """
        标记任务为运行中状态
        
        Args:
            job: 任务对象
            worker_name: Worker 名称
            redis_client: Redis 客户端
            job_data_key: 任务数据键
        """
        job.status = JobStatus.RUNNING
        job.start_time = time.time()
        job.worker_id = worker_name

        updated_job_data = job.to_dict()
        await redis_client.hset(
            key=job_data_key,
            name=job.id,
            value=pickle.dumps(updated_job_data)
        )

    async def _mark_job_completed(
        self,
        job: Job,
        result: Any,
        redis_client,
        results_key: str
    ) -> None:
        """
        标记任务完成
        
        Args:
            job: 任务对象
            result: 执行结果
            redis_client: Redis 客户端
            results_key: 结果存储键
        """
        job.status = JobStatus.COMPLETED
        job.result = result
        job.end_time = time.time()

        result_data = {
            'status': 'completed',
            'result': pickle.dumps(result).hex(),
            'end_time': job.end_time,
            'duration': job.duration
        }
        await redis_client.hset(
            results_key,
            job.id,
            json.dumps(result_data)
        )

    async def _mark_job_failed(
        self,
        job: Job,
        error: Exception,
        redis_client,
        dead_letter_key: str
    ) -> None:
        """
        标记任务失败
        
        Args:
            job: 任务对象
            error: 错误对象
            redis_client: Redis 客户端
            dead_letter_key: 死信队列键
        """
        job.status = JobStatus.FAILED
        job.error = str(error)
        job.end_time = time.time()

        error_data = {
            "error": str(error),
            "failed_at": time.time(),
            "job_data": job.to_dict()
        }

        await redis_client.rpush(
            dead_letter_key,
            json.dumps(error_data)
        )

    async def _cleanup_job(
        self,
        job: Job,
        redis_client,
        processing_key: str
    ) -> None:
        """
        清理任务执行后的数据
        
        Args:
            job: 任务对象
            redis_client: Redis 客户端
            processing_key: 处理中任务键
        """
        final_job_data = job.to_dict()
        await redis_client.hset(
            name=processing_key.split(':')[0] + ':' + ':'.join(processing_key.split(':')[1:2]),
            key=job.id,
            value=pickle.dumps(final_job_data)
        )
        await redis_client.hdel(processing_key, job.id)
