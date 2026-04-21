#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/12/8
# @Author : cyq
# @File : redis_worker_pool
# @Software: PyCharm
# @Desc:
import asyncio
import json
import pickle
import socket
import os
from enum import Enum
from typing import Optional, Dict, List, Callable, Any
from datetime import datetime
from collections import OrderedDict

from app.model.base import User
from common import RedisClient
from dataclasses import dataclass, field, asdict
import time
import uuid
from config import Config
from croe.interface.task import TaskRunner, TaskParams
from enums import StarterEnum
from croe.interface.starter import APIStarter
from croe.play.task_runner import PlayTaskRunner, PlayTaskExecuteParams
from croe.play.starter import UIStarter
from utils import MyLoguru

log = MyLoguru().get_logger()


def generate_server_id() -> str:
    """生成服务器唯一ID"""
    hostname = socket.gethostname()
    pid = os.getpid()
    return f"{hostname}_{pid}"


class JobStatus(Enum):
    """任务状态"""
    PENDING = "pending"  # 等待中
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class JOB:
    """
    任务对象
    """
    id: str
    name: str
    func_name: str  # 函数名称，用于反序列化时查找
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    worker_id: Optional[str] = None  # 执行此任务的worker ID
    server_id: Optional[str] = None  # 服务器ID

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]

    @property
    def duration(self) -> Optional[float]:
        """执行时长"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> dict:
        """转换为字典（可序列化）"""
        data = asdict(self)
        data['status'] = self.status.value
        # 处理特殊类型
        data['args'] = self._serialize_args(self.args)
        data['kwargs'] = self._serialize_kwargs(self.kwargs)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'JOB':
        """从字典创建"""
        data = data.copy()
        data['status'] = JobStatus(data['status'])
        data['args'] = cls._deserialize_args(data['args'])
        data['kwargs'] = cls._deserialize_kwargs(data['kwargs'])
        return cls(**data)

    @staticmethod
    def _serialize_args(args: tuple) -> str:
        """序列化参数"""
        return pickle.dumps(args).hex()

    @staticmethod
    def _deserialize_args(args_hex: str) -> tuple:
        """反序列化参数"""
        return pickle.loads(bytes.fromhex(args_hex))

    @staticmethod
    def _serialize_kwargs(kwargs: dict) -> str:
        """序列化关键字参数"""
        return pickle.dumps(kwargs).hex()

    @staticmethod
    def _deserialize_kwargs(kwargs_hex: str) -> dict:
        """反序列化关键字参数"""
        return pickle.loads(bytes.fromhex(kwargs_hex))

    def __repr__(self):
        return f"<JOB(id={self.id}, name={self.name} >"


class RedisWorkerPool:
    """
    redis任务池

    -  任务队列 job_queue:{queue_name}
    -  处理中 job_processing
    -  任务数据 job_data
    -  任务结果 job_results
    -  死亡任务队列 job_dead_letter
    """

    _instances: Dict[str, 'RedisWorkerPool'] = {}
    redis_client: Optional["RedisClient"] = None
    _redis_connected: bool = False

    _GET_JOB_SCRIPT = """
    local job_id = redis.call('zpopmin', KEYS[1])
    if not job_id or #job_id == 0 then
        return nil
    end
    local job_data = redis.call('hget', KEYS[2], job_id[1])
    if not job_data then
        return nil
    end
    redis.call('hset', KEYS[3], job_id[1], job_data)
    return {job_id[1], job_data}
    """

    @classmethod
    def get_instance(cls,
                     queue_name: str = "default",
                     worker_count: int = 5,
                     server_id: str = None) -> 'RedisWorkerPool':
        """获取单例实例（按队列名区分）"""
        instance_key = f"{queue_name}_{server_id or 'default'}"
        if instance_key not in cls._instances:
            cls._instances[instance_key] = cls(
                queue_name=queue_name,
                worker_count=worker_count,
                server_id=server_id
            )
        return cls._instances[instance_key]

    def __init__(self, queue_name: str = "default", worker_count: int = 5, server_id: str = None):
        self.queue_name = queue_name
        self.worker_count = worker_count
        self.server_id = server_id or generate_server_id()

        self.redis_client = None

        self.queue_key = f"job_queue:{queue_name}"
        self.processing_key = f"job_processing:{queue_name}"
        self.job_data_key = f"job_data:{queue_name}"
        self.results_key = f"job_results:{queue_name}"
        self.dead_letter_key = f"job_dead_letter:{queue_name}"

        self.workers: List[asyncio.Task] = []
        self.local_jobs: OrderedDict = OrderedDict()
        self.local_jobs_max_size = 10000
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None

        # 函数注册表（用于反序列化）
        self.function_registry: Dict[str, Callable] = {}

        self._get_job_sha = None

        self.job_timeout = 3600

        log.info(
            f"RedisWorkerPool init redis worker pool : Queue Name={queue_name}  workers={worker_count}, server={self.server_id}")

    @property
    def redis(self):
        if self.redis_client is None:
            raise RuntimeError("miss redis")
        return self.redis_client.r

    def register_function(self, func: Callable = None):
        """注册函数（装饰器或直接调用）"""

        def decorator(f: Callable):
            func_name = f.__name__
            self.function_registry[func_name] = f
            log.info(f"RedisWorkerPool register function: {func_name}")
            return f

        if func is None:
            return decorator
        return decorator(func)

    def check_pool_ready(self) -> bool:
        """检查任务池是否就绪"""
        if not self.is_running:
            return False
        if not self._redis_connected:
            return False
        if self.redis_client is None:
            return False
        return True

    async def start(self):
        """
        启动工作池
        """
        if self.is_running:
            log.warning("redis worker pool already running ..... ")
            return
        try:
            await self.connect_redis()
            await self._load_scripts()
        except Exception as e:
            log.error(f"start fail ，connect redis fail: {e}")
            raise
        self.is_running = True
        self.workers = [
            asyncio.create_task(self._worker(i), name=f"RedisWorker-{i}")
            for i in range(self.worker_count)
        ]

        self.monitor_task = asyncio.create_task(self._monitor(), name="RedisMonitor")

        log.info(
            f"====================== Redis工作池启动: {self.worker_count} workers, server={self.server_id} ====================== ")

    async def stop(self):
        """停止工作池"""
        if not self.is_running:
            return

        log.info("正在停止 Redis 工作池...")
        self.is_running = False

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        for worker in self.workers:
            if not worker.done():
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass

        await self.disconnect_redis()
        log.info("Redis 工作池已停止")

    async def set_redis_client(self, redis_client: RedisClient):
        """设置外部 Redis 客户端，避免重复连接池"""
        self.redis_client = redis_client
        self._redis_connected = True

    async def connect_redis(self):
        """
        连接redis
        """
        if self._redis_connected and self.redis_client:
            return

        from common import rc
        self.redis_client = rc
        self._redis_connected = True

    async def disconnect_redis(self):
        """断开Redis连接"""
        self._redis_connected = False
        self.redis_client = None
        log.info("RedisWorkerPool 连接已关闭")

    async def _load_scripts(self):
        """加载 Lua 脚本"""
        try:
            self._get_job_sha = await self.redis.script_load(self._GET_JOB_SCRIPT)
        except Exception as e:
            log.warning(f"加载 Lua 脚本失败: {e}")

    async def _scan_keys(self, pattern: str) -> List[bytes]:
        """使用 SCAN 代替 KEYS 查找 key"""
        keys = []
        cursor = 0
        while True:
            cursor, partial_keys = await self.redis.scan(cursor, match=pattern, count=100)
            keys.extend(partial_keys)
            if cursor == 0:
                break
        return keys

    async def submit_to_redis(self,
                              func: Callable,
                              job_id: str,
                              job_name: str,
                              job_args: tuple = (),
                              job_kwargs: dict = None
                              ) -> str:
        """
        添加任务
        """
        if not self.check_pool_ready():
            raise RuntimeError("任务池未启动或 Redis 未连接")

        if not job_kwargs:
            job_kwargs = {}
        func_name = func.__name__
        job = JOB(id=job_id, name=job_name, func_name=func_name, args=job_args, kwargs=job_kwargs)
        job_data = job.to_dict()
        serialized_job = pickle.dumps(job_data)

        await self.redis.hset(
            name=self.job_data_key,
            key=job.id,
            value=serialized_job,
        )

        # 计算优先级分数（时间戳 + 优先级）
        # 优先级越高，分数越小，越先被处理
        score = time.time()
        # 添加到有序集合（实现优先级队列）
        await self.redis.zadd(
            self.queue_key,
            {job.id: score}
        )

        self._add_local_job(job)

        queue_size = await self.redis.zcard(self.queue_key)
        log.info(f"提交任务 {job.id}: {job_name} (队列: {queue_size})")
        return job.id

    async def submit_batch_to_redis(self,
                                     func: Callable,
                                     job_infos: List[Dict[str, Any]]
                                     ) -> List[str]:
        """
        批量添加任务（使用 Pipeline 事务保护）
        job_infos: [{'job_id': 'xxx', 'job_name': 'xxx', 'job_args': (), 'job_kwargs': {}}, ...]
        """
        if not self.check_pool_ready():
            raise RuntimeError("任务池未启动或 Redis 未连接")

        pipe = self.redis.pipeline()
        job_ids = []
        score = time.time()

        for info in job_infos:
            job_id = info.get('job_id')
            job_name = info.get('job_name', 'unnamed')
            job_args = info.get('job_args', ())
            job_kwargs = info.get('job_kwargs', {})

            func_name = func.__name__
            job = JOB(id=job_id, name=job_name, func_name=func_name, args=job_args, kwargs=job_kwargs)
            job_data = job.to_dict()
            serialized_job = pickle.dumps(job_data)

            pipe.hset(self.job_data_key, job.id, serialized_job)
            pipe.zadd(self.queue_key, {job.id: score})
            job_ids.append(job.id)
            self._add_local_job(job)

        await pipe.execute()

        queue_size = await self.redis.zcard(self.queue_key)
        log.info(f"批量提交任务 {len(job_ids)} 个 (队列: {queue_size})")
        return job_ids

    def _add_local_job(self, job: JOB):
        """添加任务到本地缓存，自动清理旧任务"""
        self.local_jobs[job.id] = job
        while len(self.local_jobs) > self.local_jobs_max_size:
            self.local_jobs.popitem(last=False)

    async def _worker(self, worker_id: int):
        """
        任务
        """

        worker_name = f"{self.server_id}_worker_{worker_id}"
        processing_key = f"{self.processing_key}:{worker_name}"

        try:
            await self.connect_redis()
            log.info(f" worker:【{worker_name}】 start ， connect to redis success")
        except Exception as e:
            log.error(f"{worker_name} connect redis fail: {e}")
            return

        while self.is_running:
            try:
                job = None
                try:
                    async with asyncio.timeout(1):
                        job_result = await self._get_job_atomic(processing_key)

                    if not job_result:
                        await asyncio.sleep(0.1)
                        continue

                    job_id, serialized_job = job_result
                    job_data = pickle.loads(serialized_job)
                    job = JOB.from_dict(job_data)

                    log.info(f"{worker_name} 开始处理任务 {job.id}: {job.name}")
                    await self.__job_running(job, worker_name)
                    await self.__worker_execute_job(job, processing_key)

                except asyncio.TimeoutError:
                    continue

            except asyncio.CancelledError:
                log.info(f"{worker_name} 被取消")
                break
            except Exception as e:
                log.exception(f"{worker_name} 异常: {e}")
                await asyncio.sleep(1)

    async def _get_job_atomic(self, processing_key: str) -> Optional[tuple]:
        """使用 Lua 脚本原子性获取任务"""
        try:
            if self._get_job_sha:
                result = await self.redis.evalsha(
                    self._get_job_sha,
                    3,
                    self.queue_key,
                    self.job_data_key,
                    processing_key
                )
            else:
                result = await self.redis.eval(
                    self._GET_JOB_SCRIPT,
                    3,
                    self.queue_key,
                    self.job_data_key,
                    processing_key
                )

            if result:
                job_id = result[0] if isinstance(result[0], str) else result[0].decode('utf-8')
                return job_id, result[1]
            return None
        except Exception as e:
            result = await self.redis.bzpopmin(self.queue_key, timeout=0.5)
            if not result:
                return None

            _key, job_id, _score = result
            job_id = job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id

            serialized_job = await self.redis.hget(self.job_data_key, job_id)
            if not serialized_job:
                return None

            await self.redis.hset(processing_key, job_id, serialized_job)
            return job_id, serialized_job

    async def _monitor(self):
        """
        监控
        """
        try:
            log.info("[RedisMonitor] 启动")
            while self.is_running:
                await asyncio.sleep(5)
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

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        try:
            await self.connect_redis()
            serialized_job = await self.redis.hget(self.job_data_key, job_id)
            if not serialized_job:
                return None

            job_data = pickle.loads(serialized_job)
            job = JOB.from_dict(job_data)

            result_data = await self.redis.hget(self.results_key, job_id)
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

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            await self.connect_redis()
            queue_size = await self.redis.zcard(self.queue_key)

            processing_keys = await self._scan_keys(f"{self.processing_key}:*")
            processing = 0
            for key in processing_keys:
                count = await self.redis.hlen(key)
                processing += count

            results = await self.redis.hgetall(self.results_key)
            completed = 0
            failed = 0
            for result_json in results.values():
                result = json.loads(result_json)
                if result.get('status') == 'completed':
                    completed += 1
                else:
                    failed += 1

            servers = set()
            for key in processing_keys:
                    parts = key.decode('utf-8').split(':') if isinstance(key, bytes) else key.split(':')
                    if len(parts) >= 3:
                        server_worker = parts[2]
                        if len(parts) >= 3:
                            server_id = '_'.join(server_worker.split('_')[:-2])
                        else:
                            server_id = '_'.join(server_worker.split('_')[:-2])
                    servers.add(server_id)

            return {
                'queue_name': self.queue_name,
                'queue_size': queue_size,
                'processing': processing,
                'completed': completed,
                'failed': failed,
                'dead_letter': await self.redis.llen(self.dead_letter_key),
                'servers': list(servers),
                'server_id': self.server_id,
                'local_workers': self.worker_count
            }
        except Exception as e:
            log.error(f"获取统计失败: {e}")
            return {}

    async def cancel_job(self, job_id: str) -> bool:
        """取消任务（如果还在队列中）"""
        try:
            await self.connect_redis()

            removed = await self.redis.zrem(self.queue_key, job_id)
            if removed:
                serialized_job = await self.redis.hget(self.job_data_key, job_id)
                if serialized_job:
                    job_data = pickle.loads(serialized_job)
                    job = JOB.from_dict(job_data)
                    job.status = JobStatus.CANCELLED
                    job.end_time = time.time()

                    await self.redis.hset(
                        self.job_data_key,
                        job_id,
                        pickle.dumps(job.to_dict())
                    )

                log.info(f"取消任务: {job_id}")
                return True

            return False
        except Exception as e:
            log.error(f"取消任务失败 {job_id}: {e}")
            return False

    async def retry_failed_jobs(self, limit: int = 10) -> List[str]:
        """重试失败的任务（从死信队列）"""
        try:
            await self.connect_redis()

            retried_jobs = []
            for _ in range(limit):
                error_data = await self.redis.lpop(self.dead_letter_key)
                if not error_data:
                    break

                error_info = json.loads(error_data)
                job_data = error_info.get('job_data')

                if job_data:
                    job = JOB.from_dict(job_data)
                    job.id = str(uuid.uuid4())
                    job.status = JobStatus.PENDING
                    job.start_time = None
                    job.end_time = None
                    job.error = None

                    serialized_job = pickle.dumps(job.to_dict())
                    await self.redis.hset(
                        self.job_data_key,
                        job.id,
                        serialized_job
                    )

                    score = time.time()
                    await self.redis.zadd(self.queue_key, {job.id: score})

                    retried_jobs.append(job.id)
                    log.info(f"重试任务: {job.id} (原任务: {job_data['id']})")

            log.info(f"重试了 {len(retried_jobs)} 个失败任务")
            return retried_jobs

        except Exception as e:
            log.error(f"重试失败任务错误: {e}")
            return []

    async def cleanup_old_jobs(self, older_than_hours: int = 24, batch_size: int = 100) -> int:
        """清理旧的任务数据（分批处理）"""
        try:
            await self.connect_redis()

            cutoff_time = time.time() - (older_than_hours * 3600)

            cursor = 0
            deleted = 0

            while True:
                cursor, job_items = await self.redis.hscan(self.job_data_key, cursor, count=batch_size)

                for job_id_bytes, serialized_job in job_items:
                    job_id = job_id_bytes.decode('utf-8') if isinstance(job_id_bytes, bytes) else job_id_bytes
                    try:
                        job_data = pickle.loads(serialized_job)
                        job = JOB.from_dict(job_data)

                        if job.end_time and job.end_time < cutoff_time:
                            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                                pipe = self.redis.pipeline()
                                pipe.hdel(self.job_data_key, job_id)
                                pipe.hdel(self.results_key, job_id)

                                processing_keys = await self._scan_keys(f"{self.processing_key}:*")
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

    async def __worker_execute_job(self, job: JOB, processing_key: str):
        """
        任务执行
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

            await self.__job_completed(job, _func_result)

            log.info(f"任务 {job}  执行完成 result: {_func_result} "
                     f"耗时 {job.duration:.2f}s")


        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.end_time = time.time()
            raise

        except Exception as e:
            await self.__job_failed(job, e)
            log.error(f"任务执行失败: {e}")

        finally:
            final_job_data = job.to_dict()
            await self.redis.hset(
                self.job_data_key,
                job.id,
                pickle.dumps(final_job_data)
            )
            await self.redis.hdel(processing_key, job.id)

            self._add_local_job(job)

    async def __job_running(self, job: JOB, worker_name: str):
        """
        任务运行中
        """
        job.status = JobStatus.RUNNING
        job.start_time = time.time()
        job.worker_id = worker_name

        updated_job_data = job.to_dict()
        await self.redis.hset(
            key=self.job_data_key,
            name=job.id,
            value=pickle.dumps(updated_job_data)
        )

    async def __job_completed(self, job: JOB, result: Dict[str, Any]):
        """
        - 设置任务状态
        - 保存结果
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
        await self.redis.hset(
            self.results_key,
            job.id,
            json.dumps(result_data)
        )

    async def __job_failed(self, job: JOB, e: Exception):
        """
        任务失败
        """

        job.status = JobStatus.FAILED
        job.error = str(e)
        job.end_time = time.time()

        error_data = {
            "error": str(e),
            "failed_at": time.time(),
            "job_data": job.to_dict()
        }

        await self.redis.rpush(
            self.dead_letter_key,
            json.dumps(error_data)
        )


r_pool = RedisWorkerPool.get_instance()


@r_pool.register_function
async def register_interface_task_RoBot(**kwargs):
    log.info("=== register_interface_task_RoBot 开始 ===")  # 添加
    try:
        runner = TaskRunner(APIStarter(StarterEnum.RoBot))
        log.info(f"=== runner created: {runner} ===")  # 添加
        await runner.execute_task(params=TaskParams(**kwargs))
        log.info("=== register_interface_task_RoBot 结束 ===")  # 添加
    except Exception as e:
        log.error(f"=== register_interface_task_RoBot 异常: {e} ===")  # 添加

@r_pool.register_function
async def register_interface_task_Handle(user: User, **kwargs):
    """
    接口任务注册执行
    接口调用执行
    """
    runner = TaskRunner(APIStarter(user))
    await runner.execute_task(params=TaskParams(**kwargs))


@r_pool.register_function
async def register_play_task_handle(user: User, **kwargs):
    """
    UI 任务函数注册
    """
    runner = PlayTaskRunner(UIStarter(user))
    await runner.execute_task(params=PlayTaskExecuteParams(**kwargs))


@r_pool.register_function
async def register_play_task_robot(**kwargs):
    """
    UI 任务函数注册
    """
    runner = PlayTaskRunner(UIStarter(StarterEnum.RoBot))
    await runner.execute_task(params=PlayTaskExecuteParams(**kwargs))


__all__ = [
    "r_pool",
    "register_interface_task_RoBot",
    "register_interface_task_Handle",
    "register_play_task_robot",
    "register_play_task_handle",
]
