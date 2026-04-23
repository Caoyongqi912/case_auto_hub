#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
任务数据模型模块

包含任务状态枚举和任务数据类定义
"""
import pickle
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class JobStatus(Enum):
    """
    任务状态枚举
    
    Attributes:
        PENDING: 等待执行
        RUNNING: 执行中
        COMPLETED: 执行完成
        FAILED: 执行失败
        CANCELLED: 已取消
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """
    任务数据类
    
    用于表示一个待执行的任务，包含任务的所有元数据和执行信息。
    
    Attributes:
        id: 任务唯一标识符
        name: 任务名称
        func_name: 执行函数名称（用于在注册表中查找）
        args: 位置参数元组
        kwargs: 关键字参数字典
        status: 任务当前状态
        result: 执行结果
        error: 错误信息
        start_time: 开始执行时间戳
        end_time: 结束执行时间戳
        created_at: 任务创建时间戳
        worker_id: 执行此任务的 Worker ID
        server_id: 执行此任务的服务器 ID
    
    Example:
        >>> job = Job(id="abc123", name="test_job", func_name="process_data")
        >>> job.to_dict()
        {'id': 'abc123', 'name': 'test_job', ...}
    """
    id: str
    name: str
    func_name: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    worker_id: Optional[str] = None
    server_id: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]

    @property
    def duration(self) -> Optional[float]:
        """
        计算任务执行时长
        
        Returns:
            执行时长（秒），如果任务未完成则返回 None
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> dict:
        """
        将任务对象转换为可序列化的字典
        
        将枚举类型转换为其值，将参数序列化为十六进制字符串。
        
        Returns:
            包含任务所有属性的字典
        """
        data = asdict(self)
        data['status'] = self.status.value
        data['args'] = self._serialize_args(self.args)
        data['kwargs'] = self._serialize_kwargs(self.kwargs)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """
        从字典创建任务对象
        
        Args:
            data: 包含任务属性的字典
            
        Returns:
            Job 实例
        """
        data = data.copy()
        data['status'] = JobStatus(data['status'])
        data['args'] = cls._deserialize_args(data['args'])
        data['kwargs'] = cls._deserialize_kwargs(data['kwargs'])
        return cls(**data)

    @staticmethod
    def _serialize_args(args: tuple) -> str:
        """将位置参数序列化为十六进制字符串"""
        return pickle.dumps(args).hex()

    @staticmethod
    def _deserialize_args(args_hex: str) -> tuple:
        """从十六进制字符串反序列化位置参数"""
        return pickle.loads(bytes.fromhex(args_hex))

    @staticmethod
    def _serialize_kwargs(kwargs: dict) -> str:
        """将关键字参数序列化为十六进制字符串"""
        return pickle.dumps(kwargs).hex()

    @staticmethod
    def _deserialize_kwargs(kwargs_hex: str) -> dict:
        """从十六进制字符串反序列化关键字参数"""
        return pickle.loads(bytes.fromhex(kwargs_hex))

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, name={self.name}, status={self.status.value})>"


# 兼容旧代码的别名
JOB = Job
