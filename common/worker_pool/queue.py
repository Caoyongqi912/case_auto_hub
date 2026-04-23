#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
任务队列操作模块

负责任务的提交、获取、取消等队列操作。
"""
import pickle
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from common.worker_pool.models import Job, JobStatus
from utils import MyLoguru

log = MyLoguru().get_logger()

PROCESSING_KEY_TTL = 300


class TaskQueue:
    """
    任务队列管理器
    
    管理任务的入队、出队、状态更新等操作。
    使用 Redis 有序集合实现优先级队列。
    
    Attributes:
        queue_name: 队列名称
        queue_key: 队列 Redis 键
        processing_key: 处理中任务 Redis 键前缀
        job_data_key: 任务数据 Redis 键
        results_key: 结果数据 Redis 键
        dead_letter_key: 死信队列 Redis 键
    
    Example:
        >>> queue = TaskQueue("default")
        >>> job_id = await queue.submit(redis, job, func)
        >>> job_data = await queue.fetch_job(redis, processing_key)
    """
    
    def __init__(self, queue_name: str):
        """
        初始化任务队列
        
        Args:
            queue_name: 队列名称，用于区分不同队列
        """
        self.queue_name = queue_name
        self.queue_key = f"job_queue:{queue_name}"
        self.processing_key = f"job_processing:{queue_name}"
        self.job_data_key = f"job_data:{queue_name}"
        self.results_key = f"job_results:{queue_name}"
        self.dead_letter_key = f"job_dead_letter:{queue_name}"
        
        self._local_jobs: OrderedDict = OrderedDict()
        self._local_jobs_max_size = 10000

    async def submit_job(
        self,
        redis_client,
        raw_redis,
        job: Job
    ) -> str:
        """
        提交单个任务到队列
        
        Args:
            redis_client: Redis 客户端（用于主连接）
            raw_redis: 原始 Redis 连接（用于二进制操作）
            job: 任务对象
            
        Returns:
            任务 ID
        """
        job_data = job.to_dict()
        serialized_job = pickle.dumps(job_data)

        await redis_client.hset(
            name=self.job_data_key,
            key=job.id,
            value=serialized_job,
        )

        score = time.time()
        await redis_client.zadd(
            self.queue_key,
            {job.id: score}
        )

        self._add_local_job(job)

        queue_size = await redis_client.zcard(self.queue_key)
        log.info(f"提交任务 {job.id}: {job.name} (队列: {queue_size})")
        return job.id

    async def submit_batch_jobs(
        self,
        redis_client,
        jobs: List[Job]
    ) -> List[str]:
        """
        批量提交任务到队列
        
        使用 Pipeline 事务保护批量操作。
        
        Args:
            redis_client: Redis 客户端
            jobs: 任务对象列表
            
        Returns:
            任务 ID 列表
        """
        pipe = redis_client.pipeline()
        job_ids = []
        score = time.time()

        for job in jobs:
            job_data = job.to_dict()
            serialized_job = pickle.dumps(job_data)

            pipe.hset(self.job_data_key, job.id, serialized_job)
            pipe.zadd(self.queue_key, {job.id: score})
            job_ids.append(job.id)
            self._add_local_job(job)

        await pipe.execute()

        queue_size = await redis_client.zcard(self.queue_key)
        log.info(f"批量提交任务 {len(job_ids)} 个 (队列: {queue_size})")
        return job_ids

    async def fetch_job_atomic(
        self,
        raw_redis,
        script_sha: Optional[str],
        processing_key: str
    ) -> Optional[Tuple[str, bytes]]:
        """
        原子性获取任务
        
        使用 Lua 脚本或 fallback 方式从队列获取任务。
        
        Args:
            raw_redis: 原始 Redis 连接
            script_sha: Lua 脚本 SHA 值
            processing_key: 处理中任务键
            
        Returns:
            (job_id, serialized_job) 元组，或 None
        """
        try:
            if script_sha:
                result = await raw_redis.evalsha(
                    script_sha,
                    3,
                    self.queue_key,
                    self.job_data_key,
                    processing_key
                )
            else:
                result = await raw_redis.eval(
                    RedisConnectionManager.LUA_SCRIPT_GET_JOB,
                    3,
                    self.queue_key,
                    self.job_data_key,
                    processing_key
                )

            if result:
                job_id = result[0] if isinstance(result[0], str) else result[0].decode('utf-8')
                job_data = result[1] if isinstance(result[1], bytes) else result[1]
                await raw_redis.expire(processing_key, PROCESSING_KEY_TTL)
                return job_id, job_data
            return None

        except Exception as e:
            log.warning(f"Lua script error, falling back: {e}")
            return await self._fetch_job_fallback(raw_redis, processing_key)

    async def _fetch_job_fallback(
        self,
        raw_redis,
        processing_key: str
    ) -> Optional[Tuple[str, bytes]]:
        """
        Fallback 方式获取任务
        
        当 Lua 脚本失败时使用 bzpopmin 方式获取任务。
        
        Args:
            raw_redis: 原始 Redis 连接
            processing_key: 处理中任务键
            
        Returns:
            (job_id, serialized_job) 元组，或 None
        """
        result = await raw_redis.bzpopmin(self.queue_key, timeout=0.5)
        if not result:
            return None

        _key, job_id, _score = result
        job_id = job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id

        serialized_job = await raw_redis.hget(self.job_data_key, job_id)
        if not serialized_job:
            return None

        await raw_redis.hset(processing_key, job_id, serialized_job)
        await raw_redis.expire(processing_key, PROCESSING_KEY_TTL)
        return job_id, serialized_job

    async def cancel_job(self, redis_client, job_id: str) -> bool:
        """
        取消任务
        
        Args:
            redis_client: Redis 客户端
            job_id: 任务 ID
            
        Returns:
            是否成功取消
        """
        removed = await redis_client.zrem(self.queue_key, job_id)
        if removed:
            serialized_job = await redis_client.hget(self.job_data_key, job_id)
            if serialized_job:
                job_data = pickle.loads(serialized_job)
                job = Job.from_dict(job_data)
                job.status = JobStatus.CANCELLED
                job.end_time = time.time()

                await redis_client.hset(
                    self.job_data_key,
                    job_id,
                    pickle.dumps(job.to_dict())
                )

            log.info(f"取消任务: {job_id}")
            return True
        return False

    async def update_job_status(
        self,
        redis_client,
        job: Job,
        status: JobStatus,
        processing_key: Optional[str] = None
    ) -> None:
        """
        更新任务状态
        
        Args:
            redis_client: Redis 客户端
            job: 任务对象
            status: 新状态
            processing_key: 处理中任务键（可选）
        """
        job.status = status
        job_data = pickle.dumps(job.to_dict())
        
        await redis_client.hset(
            self.job_data_key,
            job.id,
            job_data
        )

        if processing_key:
            await redis_client.hdel(processing_key, job.id)

        self._add_local_job(job)

    def _add_local_job(self, job: Job) -> None:
        """
        添加任务到本地缓存
        
        自动清理超出最大数量的旧任务。
        
        Args:
            job: 任务对象
        """
        self._local_jobs[job.id] = job
        while len(self._local_jobs) > self._local_jobs_max_size:
            self._local_jobs.popitem(last=False)

    def get_local_job(self, job_id: str) -> Optional[Job]:
        """
        从本地缓存获取任务
        
        Args:
            job_id: 任务 ID
            
        Returns:
            任务对象，或 None
        """
        return self._local_jobs.get(job_id)


from common.worker_pool.connection import RedisConnectionManager
