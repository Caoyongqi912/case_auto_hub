from typing import Dict, Any

from app.mapper.ui.uiSubStepMapper import SubStepMapper
from app.model.ui import UICaseStepsModel
from play.extract import ExtractManager
from utils.io_sender import SocketSender





class ExecCondition:
    EQ = 1
    NE = 2
    GT = 3
    GE = 4
    LT = 5
    LE = 6
    @staticmethod
    async def invoke(step: UICaseStepsModel, io: SocketSender, em: ExtractManager):
        if step.has_condition:
            await io.send(f"条件判断 >> {step.condition}")
            condition: Dict[str, Any] = step.condition

            # {"key": "{{name}}", "value": "ok", "operator": 1}
            key = await em.transform_target(condition['key'])
            value = await em.transform_target(condition['value'])
            return await  ExecCondition._asserts(key, value, condition['operator'])
        return False
        # subSteps = await SubStepMapper.query_by_stepId(step.id)

    @staticmethod
    async def _asserts(key: str, value: str, operator: int):
        try:
            match operator:
                case ExecCondition.EQ:
                    return key == value
                case ExecCondition.NE:
                    return key != value
                case ExecCondition.GT:
                    return key > value
                case ExecCondition.GE:
                    return key >= value
                case ExecCondition.LT:
                    return key < value
                case ExecCondition.LE:
                    return key <= value
                case _:
                    return False
        except AssertionError as e:
            return False