#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Redis 客户端模块

提供异步和同步的 Redis 客户端封装。
"""
import asyncio
from typing import Any, Dict

from redis.asyncio import Redis
from redis import Redis as SyncRedis

from config import Config
from utils import MyLoguru

log = MyLoguru().get_logger()


class RedisClient:
    """
    异步 Redis 客户端
    
    封装 redis.asyncio.Redis，提供常用的 Redis 操作方法。
    
    Attributes:
        r: Redis 连接实例
    
    Example:
        >>> client = RedisClient()
        >>> await client.init_pool()
        >>> await client.h_set("key", {"field": "value"})
    """
    
    r: Redis = None

    async def init_pool(self) -> None:
        """
        初始化 Redis 连接池
        
        创建连接并测试连接是否正常。
        
        Raises:
            Exception: 连接失败时抛出异常
        """
        self.r = Redis(
            host=Config.REDIS_SERVER,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True,
            max_connections=100
        )
        try:
            await self.r.ping()
        except Exception as e:
            log.error(f"Redis connection failed: {e}")
            raise

    async def close_pool(self) -> None:
        """
        关闭连接池
        """
        if self.r:
            await self.r.aclose()

    async def check_key_exist(self, key: str) -> int:
        """
        检查 key 是否存在
        
        Args:
            key: Redis key
            
        Returns:
            存在返回 1，不存在返回 0
        """
        return await self.r.exists(key)

    async def h_set(self, name: str, value: Dict[str, Any] | str) -> int:
        """
        设置 Hash 字段
        
        Args:
            name: Hash 名称
            value: 字段映射或值
            
        Returns:
            新增字段数量
        """
        return await self.r.hset(name=name, mapping=value)

    async def h_get_all(self, key: str) -> Dict[str, str]:
        """
        获取 Hash 所有字段
        
        Args:
            key: Hash 名称
            
        Returns:
            字段映射字典
        """
        return await self.r.hgetall(key)

    async def l_push(self, name: str, values: Any) -> int:
        """
        从左侧推入列表
        
        Args:
            name: 列表名称
            values: 推入的值
            
        Returns:
            列表长度
        """
        return await self.r.lpush(name, values)

    async def l_range(self, name: str) -> list:
        """
        获取列表所有元素
        
        Args:
            name: 列表名称
            
        Returns:
            元素列表
        """
        return await self.r.lrange(name, 0, -1)

    async def remove_key(self, key: str) -> int:
        """
        删除 key
        
        Args:
            key: 要删除的 key
            
        Returns:
            删除的 key 数量
        """
        return await self.r.delete(key)

    async def clear_all_record(self) -> None:
        """
        清除所有 record_* 开头的 key
        """
        keys = await self.r.keys("record_*")
        for key in keys:
            await self.r.delete(key)


class SyncRedisClient:
    """
    同步 Redis 客户端
    
    封装 redis.Redis，提供同步的 Redis 操作方法。
    
    Attributes:
        r: Redis 连接实例
        perf_name: 性能测试数据列表名称
    """
    
    r: SyncRedis = None
    perf_name: str = None

    def init_pool(self) -> None:
        """
        初始化 Redis 连接池
        """
        self.r = SyncRedis(
            host=Config.REDIS_SERVER,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True,
            max_connections=100
        )

    def perf_l_push(self, values: str) -> int:
        """
        推入性能测试数据
        
        Args:
            values: 数据值
            
        Returns:
            列表长度
        """
        return self.r.lpush(self.perf_name, values)

    def perf_l_range(self) -> list:
        """
        获取所有性能测试数据
        
        Returns:
            数据列表
        """
        return self.r.lrange(self.perf_name, 0, -1)


async def get_redis() -> RedisClient:
    """
    依赖注入：获取 Redis 客户端
    
    Yields:
        RedisClient 实例
    """
    r = RedisClient()
    try:
        await r.init_pool()
        yield r
    except ConnectionError:
        log.warning("redis Connect call failed")
    finally:
        await r.close_pool()


__all__ = [
    "RedisClient",
    "SyncRedisClient",
    "get_redis",
]
