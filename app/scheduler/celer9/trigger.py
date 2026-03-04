#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/3/4
# @Author : cyq
# @File : trigger
# @Software: PyCharm
# @Desc: Celery 触发器封装模块
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, field_validator
from celery.schedules import crontab, schedule

from enums import TriggerTypeEnum
from utils import MyLoguru

log = MyLoguru().get_logger()


class TriggerModel(BaseModel):
    """
    触发器配置模型
    
    用于验证和解析触发器配置参数
    """
    trigger_type: int
    kw: Dict[str, Any] = field(default_factory=dict)
    run_date: Optional[str] = None
    cron: Optional[str] = None
    hours: Optional[int] = None
    minutes: Optional[int] = None
    seconds: Optional[int] = None
    weeks: Optional[int] = None
    days: Optional[int] = None

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger_type(cls, v: int) -> int:
        """验证触发器类型"""
        valid_types = [TriggerTypeEnum.ONCE, TriggerTypeEnum.CRON, TriggerTypeEnum.FIXED_RATE]
        if v not in valid_types:
            raise ValueError(f"无效的触发器类型: {v}")
        return v

    @property
    def values(self) -> Dict[str, Any]:
        """
        根据触发器类型提取对应的配置值
        
        Returns:
            Dict[str, Any]: 配置值字典
        """
        if self.trigger_type == TriggerTypeEnum.CRON:
            cron_value = self.kw.get("cron")
            return {"cron": cron_value} if cron_value is not None else {}

        elif self.trigger_type == TriggerTypeEnum.FIXED_RATE:
            keys = ["seconds", "minutes", "hours", "weeks", "days"]
            return {
                key: self.kw[key]
                for key in keys
                if key in self.kw and self.kw[key] is not None
            }

        elif self.trigger_type == TriggerTypeEnum.ONCE:
            run_date = self.kw.get("run_date")
            return {"run_date": run_date} if run_date is not None else {}

        return {}


@dataclass(kw_only=True)
class CeleryTrigger:
    """
    Celery 触发器封装类
    
    提供与 APScheduler Trigger 一致的接口，支持：
    - CRON 表达式触发
    - 固定间隔触发
    - 单次执行触发
    
    Attributes:
        trigger_type: 触发器类型（1=单次, 2=CRON, 3=固定间隔）
        kw: 触发器配置参数
    """
    trigger_type: int
    kw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后创建触发器"""
        self._schedule = self._create_schedule(self.trigger_type)

    def _create_schedule(self, trigger_type: int) -> Union[crontab, schedule, None]:
        """
        创建调度配置
        
        Args:
            trigger_type: 触发器类型
        
        Returns:
            Union[crontab, schedule, None]: Celery 调度对象
        """
        trigger_model = TriggerModel(trigger_type=trigger_type, kw=self.kw)
        
        match trigger_type:
            case TriggerTypeEnum.ONCE:
                return self._create_once_schedule(trigger_model.values)
            case TriggerTypeEnum.CRON:
                return self._create_cron_schedule(trigger_model.values)
            case TriggerTypeEnum.FIXED_RATE:
                return self._create_interval_schedule(trigger_model.values)
            case _:
                log.warning(f"未知的触发器类型: {trigger_type}")
                return None

    def _create_once_schedule(self, values: Dict[str, Any]) -> Optional[schedule]:
        """
        创建单次执行调度
        
        Args:
            values: 配置值，包含 run_date
        
        Returns:
            Optional[schedule]: 调度对象
        """
        run_date_str = values.get("run_date")
        if not run_date_str:
            log.warning("单次执行任务缺少 run_date 参数")
            return None
        
        try:
            if isinstance(run_date_str, str):
                run_date = datetime.fromisoformat(run_date_str.replace("Z", "+00:00"))
            elif isinstance(run_date_str, datetime):
                run_date = run_date_str
            else:
                raise ValueError(f"无效的 run_date 类型: {type(run_date_str)}")
            
            now = datetime.now(run_date.tzinfo) if run_date.tzinfo else datetime.now()
            delta = run_date - now
            
            if delta.total_seconds() <= 0:
                log.warning(f"执行时间已过: {run_date}")
                return None
            
            return schedule(run_every=delta.total_seconds())
            
        except Exception as e:
            log.error(f"解析执行时间失败: {run_date_str}, 错误: {e}")
            return None

    def _create_cron_schedule(self, values: Dict[str, Any]) -> Optional[crontab]:
        """
        创建 CRON 调度
        
        Args:
            values: 配置值，包含 cron 表达式
        
        Returns:
            Optional[crontab]: CRON 调度对象
        """
        cron_expression = values.get("cron")
        if not cron_expression:
            log.warning("CRON 任务缺少 cron 表达式")
            return None
        
        try:
            fields = cron_expression.strip().split()
            if len(fields) != 5:
                raise ValueError("CRON 表达式必须包含5个字段（分 时 日 月 周）")
            
            return crontab(
                minute=fields[0],
                hour=fields[1],
                day_of_month=fields[2],
                month_of_year=fields[3],
                day_of_week=fields[4],
            )
        except Exception as e:
            log.error(f"解析 CRON 表达式失败: {cron_expression}, 错误: {e}")
            return None

    def _create_interval_schedule(self, values: Dict[str, Any]) -> Optional[schedule]:
        """
        创建固定间隔调度
        
        Args:
            values: 配置值，包含时间间隔参数
        
        Returns:
            Optional[schedule]: 间隔调度对象
        """
        total_seconds = 0
        
        if "seconds" in values and values["seconds"]:
            total_seconds += int(values["seconds"])
        if "minutes" in values and values["minutes"]:
            total_seconds += int(values["minutes"]) * 60
        if "hours" in values and values["hours"]:
            total_seconds += int(values["hours"]) * 3600
        if "days" in values and values["days"]:
            total_seconds += int(values["days"]) * 86400
        if "weeks" in values and values["weeks"]:
            total_seconds += int(values["weeks"]) * 604800
        
        if total_seconds <= 0:
            log.warning("固定间隔任务的时间间隔必须大于0")
            return None
        
        return schedule(run_every=total_seconds)

    @property
    def schedule(self) -> Union[crontab, schedule, None]:
        """
        获取 Celery 调度对象
        
        Returns:
            Union[crontab, schedule, None]: 调度对象
        """
        return self._schedule

    @property
    def is_valid(self) -> bool:
        """
        检查触发器是否有效
        
        Returns:
            bool: 是否有效
        """
        return self._schedule is not None

    def __repr__(self) -> str:
        return f"<CeleryTrigger(type={self.trigger_type}, kw={self.kw}, valid={self.is_valid})>"


def create_trigger(trigger_type: int, kw: Optional[Dict[str, Any]] = None) -> CeleryTrigger:
    """
    创建触发器的工厂函数
    
    Args:
        trigger_type: 触发器类型
        kw: 配置参数
    
    Returns:
        CeleryTrigger: 触发器实例
    """
    return CeleryTrigger(trigger_type=trigger_type, kw=kw or {})


def create_cron_trigger(cron_expression: str) -> CeleryTrigger:
    """
    创建 CRON 触发器的便捷函数
    
    Args:
        cron_expression: CRON 表达式
    
    Returns:
        CeleryTrigger: CRON 触发器实例
    """
    return CeleryTrigger(
        trigger_type=TriggerTypeEnum.CRON,
        kw={"cron": cron_expression}
    )


def create_interval_trigger(
    seconds: Optional[int] = None,
    minutes: Optional[int] = None,
    hours: Optional[int] = None,
    days: Optional[int] = None,
    weeks: Optional[int] = None,
) -> CeleryTrigger:
    """
    创建固定间隔触发器的便捷函数
    
    Args:
        seconds: 秒
        minutes: 分钟
        hours: 小时
        days: 天
        weeks: 周
    
    Returns:
        CeleryTrigger: 间隔触发器实例
    """
    kw = {}
    if seconds:
        kw["seconds"] = seconds
    if minutes:
        kw["minutes"] = minutes
    if hours:
        kw["hours"] = hours
    if days:
        kw["days"] = days
    if weeks:
        kw["weeks"] = weeks
    
    return CeleryTrigger(trigger_type=TriggerTypeEnum.FIXED_RATE, kw=kw)


def create_once_trigger(run_date: Union[str, datetime]) -> CeleryTrigger:
    """
    创建单次执行触发器的便捷函数
    
    Args:
        run_date: 执行时间
    
    Returns:
        CeleryTrigger: 单次触发器实例
    """
    if isinstance(run_date, datetime):
        run_date = run_date.isoformat()
    
    return CeleryTrigger(
        trigger_type=TriggerTypeEnum.ONCE,
        kw={"run_date": run_date}
    )
