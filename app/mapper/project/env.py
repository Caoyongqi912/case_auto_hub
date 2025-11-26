from app.mapper import Mapper
from app.model.base import EnvModel


class EnvMapper(Mapper[EnvModel]):
    __model__ = EnvModel