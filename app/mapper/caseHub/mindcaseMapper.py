from app.mapper import Mapper
from app.model.caseHub.caseHUB import TestCaseMind


class MindCaseMapper(Mapper[TestCaseMind]):
    __model__ = TestCaseMind