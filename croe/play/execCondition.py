from typing import Dict, Any

from app.model.playUI import PlayStep
from utils.io_sender import SocketSender
from utils.variableTrans import VariableTrans
from utils import MyLoguru

log = MyLoguru().get_logger()


class ExecCondition:
    EQ = 1
    NE = 2
    GT = 3
    GE = 4
    LT = 5
    LE = 6

    def __init__(self, var: VariableTrans):
        self._var = var

    async def invoke(self, step: PlayStep, io: SocketSender) -> bool:
        """
        条件判断
        """
        condition: Dict[str, Any] = step.condition
        key = await self._var.trans(condition['key'])
        value = await self._var.trans(condition['value'])
        await io.send(f"条件判断 >> key={key} & value={value}")
        return await  ExecCondition._asserts(key, value, condition['operator'])

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
