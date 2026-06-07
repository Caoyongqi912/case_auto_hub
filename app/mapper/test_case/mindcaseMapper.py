from typing import Optional

from sqlalchemy import or_, and_

from app.mapper import Mapper
from app.model.caseHub.test_case_mind import TestCaseMind
from utils import log


class MindCaseMapper(Mapper[TestCaseMind]):
    __model__ = TestCaseMind

    @classmethod
    async def get_by_plan_or_requirement(
        cls,
        plan_id: Optional[int] = None,
        requirement_id: Optional[int] = None,
    ) -> Optional[TestCaseMind]:
        """
        按 plan_id 或 requirement_id 拉取脑图

        优先级：plan_id > requirement_id
        """
        try:
            if plan_id:
                return await cls.get_by(plan_id=plan_id)
            if requirement_id:
                return await cls.get_by(requirement_id=requirement_id)
            return None
        except Exception as e:
            log.error(f"get_by_plan_or_requirement error: {e}")
            raise
