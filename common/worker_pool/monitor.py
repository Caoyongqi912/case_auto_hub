#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
监控统计模块

负责任务池的监控、统计信息收集和清理任务。
"""
import asyncio
import json
import pickle
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from common.worker_pool.models import Job, JobStatus
from utils import MyLoguru

log = MyLoguru().get_logger()


class PoolMonitor:
    """
    任务池监控器
    
    负责收集统计信息、清理旧任务、重试失败任务等。
    
    Attributes:
        queue_name: 队列名称
        queue_key: 队列键
        processing_key: 处理中任务键前缀
        job_data_key: 任务数据键
        results_key: 结果键
        dead_letter_key: 死信队列键
        server_id: 服务器 ID
        worker_count: Worker 数量
    
    Example:
        >>> monitor = PoolMonitor(queue_name, server_id, worker_count)
        >>> stats = await monitor.get_stats(redis_client)
    """
    
    def __init__(
        self,
        queue_name: str,
        queue_key: str,
        processing_key: str,
        job_data_key: str,
        results_key: str,
        dead_letter_key: str,
        server_id: str,
        worker_count: int
    ):
        """
        初始化监控器
        
        Args:
            queue_name: 队列名称
            queue_key: 队列键
            processing_key: 处理中任务键前缀
            job_data_key: 任务数据键
            results_key: 结果键
            dead_letter_key: 死信队列键
            server_id: 服务器 ID
            worker_count: Worker 数量
        """
        self.queue_name = queue_name
        self.queue_key = queue_key
        self.processing_key = processing_key
        self.job_data_key = job_data_key
        self.results_key = results_key
        self.dead_letter_key = dead_letter_key
        self.server_id = server_id
        self.worker_count = worker_count

    async def get_stats(self, redis_client) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            redis_client: Redis 客户端
            
        Returns:
            包含队列统计信息的字典
        """
        try:
            queue_size = await redis_client.zcard(self.queue_key)

            processing_keys = await self._scan_keys(redis_client, f"{self.processing_key}:*")
            processing = 0
            for key in processing_keys:
                count = await redis_client.hlen(key)
                processing += count

            results = await redis_client.hgetall(self.results_key)
            completed = 0
            failed = 0
            for result_json in results.values():
                result = json.loads(result_json)
                if result.get('status') == 'completed':
                    completed += 1
                else:
                    failed += 1

            servers = self._extract_servers(processing_keys)

            return {
                'queue_name': self.queue_name,
                'queue_size': queue_size,
                'processing': processing,
                'completed': completed,
                'failed': failed,
                'dead_letter': await redis_client.llen(self.dead_letter_key),
                'servers': list(servers),
                'server_id': self.server_id,
                'local_workers': self.worker_count
            }
        except Exception as e:
            log.error(f"获取统计失败: {e}")
            return {}

    async def get_job_status(
        self,
        job_id: str,
        redis_client,
        job_data_key: str,
        results_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            job_id: 任务 ID
            redis_client: Redis 客户端
            job_data_key: 任务数据键
            results_key: 结果键
            
        Returns:
            任务状态字典，或 None
        """
        try:
            serialized_job = await redis_client.hget(job_data_key, job_id)
            if not serialized_job:
                return None

            job_data = pickle.loads(serialized_job)
            job = Job.from_dict(job_data)

            result_data = await redis_client.hget(results_key, job_id)
            if result_data:
                result_json = json.loads(result_data)
                if 'result' in result_json:
                    job.result = pickle.loads(bytes.fromhex(result_json['result']))

            return {
                'id': job.id,
                'name': job.name,
                'status': job.status.value,
                'created_at': datetime.fromtimestamp(job.created_at).isoformat(),
                'start_time': datetime.fromtimestamp(job.start_time).isoformat() if job.start_time else None,
                'end_time': datetime.fromtimestamp(job.end_time).isoformat() if job.end_time else None,
                'duration': job.duration,
                'result': job.result,
                'error': job.error,
                'worker_id': job.worker_id,
                'server_id': job.server_id
            }
        except Exception as e:
            log.error(f"获取任务状态失败 {job_id}: {e}")
            return None

    async def retry_failed_jobs(
        self,
        redis_client,
        queue_key: str,
        job_data_key: str,
        limit: int = 10
    ) -> List[str]:
        """
        重试失败的任务（从死信队列）
        
        Args:
            redis_client: Redis 客户端
            queue_key: 队列键
            job_data_key: 任务数据键
            limit: 最大重试数量
            
        Returns:
            重试的任务 ID 列表
        """
        try:
            retried_jobs = []
            for _ in range(limit):
                error_data = await redis_client.lpop(self.dead_letter_key)
                if not error_data:
                    break

                error_info = json.loads(error_data)
                job_data = error_info.get('job_data')

                if job_data:
                    job = Job.from_dict(job_data)
                    job.id = str(uuid.uuid4())
                    job.status = JobStatus.PENDING
                    job.start_time = None
                    job.end_time = None
                    job.error = None

                    serialized_job = pickle.dumps(job.to_dict())
                    await redis_client.hset(
                        job_data_key,
                        job.id,
                        serialized_job
                    )

                    score = time.time()
                    await redis_client.zadd(queue_key, {job.id: score})

                    retried_jobs.append(job.id)
                    log.info(f"重试任务: {job.id} (原任务: {job_data['id']})")

            log.info(f"重试了 {len(retried_jobs)} 个失败任务")
            return retried_jobs

        except Exception as e:
            log.error(f"重试失败任务错误: {e}")
            return []

    async def cleanup_old_jobs(
        self,
        redis_client,
        job_data_key: str,
        results_key: str,
        processing_key: str,
        older_than_hours: int = 24,
        batch_size: int = 100
    ) -> int:
        """
        清理旧的任务数据（分批处理）
        
        Args:
            redis_client: Redis 客户端
            job_data_key: 任务数据键
            results_key: 结果键
            processing_key: 处理中任务键前缀
            older_than_hours: 清理多少小时前的任务
            batch_size: 批处理大小
            
        Returns:
            清理的任务数量
        """
        try:
            cutoff_time = time.time() - (older_than_hours * 3600)

            cursor = 0
            deleted = 0

            while True:
                cursor, job_items = await redis_client.hscan(job_data_key, cursor, count=batch_size)

                for job_id_bytes, serialized_job in job_items:
                    job_id = job_id_bytes.decode('utf-8') if isinstance(job_id_bytes, bytes) else job_id_bytes
                    try:
                        job_data = pickle.loads(serialized_job)
                        job = Job.from_dict(job_data)

                        if job.end_time and job.end_time < cutoff_time:
                            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                                pipe = redis_client.pipeline()
                                pipe.hdel(job_data_key, job_id)
                                pipe.hdel(results_key, job_id)

                                processing_keys = await self._scan_keys(redis_client, f"{processing_key}:*")
                                for key in processing_keys:
                                    pipe.hdel(key, job_id)

                                await pipe.execute()
                                deleted += 1
                    except Exception:
                        continue

                if cursor == 0:
                    break

            log.info(f"清理了 {deleted} 个旧任务")
            return deleted

        except Exception as e:
            log.error(f"清理旧任务错误: {e}")
            return 0

    async def _scan_keys(self, redis_client, pattern: str) -> List[bytes]:
        """
        使用 SCAN 代替 KEYS 查找 key
        
        Args:
            redis_client: Redis 客户端
            pattern: 匹配模式
            
        Returns:
            匹配的 key 列表
        """
        keys = []
        cursor = 0
        while True:
            cursor, partial_keys = await redis_client.scan(cursor, match=pattern, count=100)
            keys.extend(partial_keys)
            if cursor == 0:
                break
        return keys

    def _extract_servers(self, processing_keys: List[bytes]) -> set:
        """
        从 processing keys 中提取服务器 ID
        
        Args:
            processing_keys: processing key 列表
            
        Returns:
            服务器 ID 集合
        """
        servers = set()
        for key in processing_keys:
            parts = key.decode('utf-8').split(':') if isinstance(key, bytes) else key.split(':')
            if len(parts) >= 3:
                server_worker = parts[2]
                server_id = '_'.join(server_worker.split('_')[:-2])
                servers.add(server_id)
        return servers
