import enum
from enum import StrEnum
from app.model.base import User


class TaskStatus:
    RUNNING = "RUNNING"
    DONE = "DONE"


class TaskResult:
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class StarterEnum(enum.Enum):
    User = 1
    Jenkins = 2
    RoBot =3
    Celery = 4



class TriggerType(StrEnum):
    Once = "once"  # 单次执行
    Cron = "cron"  # 定时执行
    FixedRate = "fixedRate"  # 固定频率


class ExecuteStrategy(StrEnum):
    Parallel = "parallel"  # 并行
    Skip = "skip"  # 跳过
    Wait = "wait"  # 等待

