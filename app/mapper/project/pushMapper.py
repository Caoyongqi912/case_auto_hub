from app.mapper import Mapper
from app.model.base import PushModel


class PushMapper(Mapper[PushModel]):
    __model__ = PushModel
