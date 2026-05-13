from app.mapper import Mapper
from app.model.caseHub.test_case_mind import TestCaseMind


class MindCaseMapper(Mapper[TestCaseMind]):
    __model__ = TestCaseMind