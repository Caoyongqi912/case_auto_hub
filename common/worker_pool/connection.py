#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Redis 连接管理模块

负责管理 Worker Pool 的 Redis 连接，包括：
- 主连接（用于常规操作，支持 decode_responses）
- 原始连接（用于二进制操作，不支持 decode_responses）
- Lua 脚本加载和管理
"""
import socket
import os
from typing import Optional

from redis.asyncio import Redis as AsyncRedis

from config import Config
from utils import MyLoguru

log = MyLoguru().get_logger()


def generate_server_id() -> str:
    """
    生成服务器唯一标识符
    
    使用主机名和进程 ID 组合生成唯一标识。
    
    Returns:
        格式为 "{hostname}_{pid}" 的唯一标识符
    """
    hostname = socket.gethostname()
    pid = os.getpid()
    return f"{hostname}_{pid}"


class RedisConnectionManager:
    """
    Redis 连接管理器
    
    管理 Worker Pool 所需的 Redis 连接，包括：
    - 主客户端连接（用于常规操作）
    - 原始连接（用于二进制数据操作，如 pickle 序列化数据）
    
    Attributes:
        redis_client: 主 Redis 客户端（来自外部注入）
        raw_redis: 原始 Redis 连接（不支持 decode_responses）
        is_connected: 连接状态标志

    """
    
    LUA_SCRIPT_GET_JOB = """
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
    
    def __init__(self):
        self.redis_client = None
        self._raw_redis: Optional[AsyncRedis] = None
        self._is_connected: bool = False
        self._get_job_script_sha: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """返回连接状态"""
        return self._is_connected

    @property
    def raw_redis(self) -> Optional[AsyncRedis]:
        """返回原始 Redis 连接"""
        return self._raw_redis

    @property
    def redis(self) -> AsyncRedis:
        """
        返回主 Redis 连接
        
        Raises:
            RuntimeError: 如果 Redis 客户端未设置
        """
        if self.redis_client is None:
            raise RuntimeError("Redis 客户端未初始化")
        return self.redis_client.r

    @property
    def script_sha(self) -> Optional[str]:
        """返回 Lua 脚本的 SHA 值"""
        return self._get_job_script_sha

    async def connect(self, external_client=None) -> None:
        """
        建立 Redis 连接
        
        Args:
            external_client: 外部注入的 RedisClient 实例（可选）
        
        Note:
            如果提供了 external_client，将使用其作为主客户端；
            同时会创建一个独立的原始连接用于二进制操作。
        """
        if self._is_connected and self._raw_redis:
            return

        self._raw_redis = AsyncRedis(
            host=Config.REDIS_SERVER,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=False,
            max_connections=20
        )

        if external_client:
            self.redis_client = external_client

        self._is_connected = True
        await self._load_scripts()

    async def disconnect(self) -> None:
        """
        断开所有 Redis 连接
        
        关闭原始连接并清理状态。
        """
        self._is_connected = False
        if self._raw_redis:
            await self._raw_redis.aclose()
            self._raw_redis = None
        self.redis_client = None
        log.info("Redis 连接已关闭")

    async def _load_scripts(self) -> None:
        """
        加载 Lua 脚本到 Redis
        
        将 Lua 脚本加载到 Redis 服务器，获取 SHA 值用于后续调用。
        """
        try:
            self._get_job_script_sha = await self._raw_redis.script_load(
                self.LUA_SCRIPT_GET_JOB
            )
            log.debug(f"Lua 脚本已加载，SHA: {self._get_job_script_sha}")
        except Exception as e:
            log.warning(f"加载 Lua 脚本失败: {e}")

    def set_client(self, client) -> None:
        """
        设置外部 Redis 客户端
        
        Args:
            client: RedisClient 实例
        """
        self.redis_client = client
        self._is_connected = True
