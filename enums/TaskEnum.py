import enum


class TaskStatus:
    RUNNING = "RUNNING"
    DONE = "DONE"


class TaskResult:
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class StarterEnum(enum.Enum):
    User = 1
    Jenkins = 2
    RoBot = 3
    Celery = 4


class TriggerTypeEnum(enum.IntEnum):
    ONCE = 1
    CRON = 2
    FIXED_RATE = 3


class ExecuteStrategyEnum(enum.IntEnum):
    Skip = 1
    Parallel = 2
    Wait = 3



class PushEnum(enum.IntEnum):
    Email = 1
    DingTalk = 2
    WeWork = 3