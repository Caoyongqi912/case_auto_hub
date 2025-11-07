import enum

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
