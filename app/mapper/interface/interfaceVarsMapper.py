from typing import Type, TypeVar

from sqlalchemy import and_, select

from app.exception import NotFind
from app.mapper import Mapper
from app.mapper.interface import InterfaceCaseMapper
from app.model import BaseModel, async_session
from app.model.base import User
from app.model.interface import InterfaceVariables
from utils import log

T = TypeVar('T', bound=BaseModel)


class InterfaceVarsMapper(Mapper[InterfaceVariables]):
    __model__ = InterfaceVariables

    @classmethod
    async def insert(cls: Type[T], user: User, case_id: int, key: str, value: str) -> T:
        """
        插入数据
        同一个case 校验 key 唯一
        :param user
        :param case_id
        :param key:
        :param value:
        :return:
        """
        log.debug(f"caseId = {case_id}")
        try:
            async with async_session() as session:
                async with session.begin():
                    case = await InterfaceCaseMapper.get_by_id(ident=case_id, session=session)

                    key_exists = await session.execute(
                        select(InterfaceVariables).where(and_(
                            InterfaceVariables.key == key,
                            InterfaceVariables.case_id == case_id
                        ))
                    )
                    if key_exists.scalar():
                        raise NotFind("key 已存在")
                    model = cls.__model__(key=key, value=value, case_id=case_id,
                                          creator=user.id, creatorName=user.username)
                    await cls.add_flush_expunge(session, model)
        except Exception as e:
            raise e


__all__ = ["InterfaceVarsMapper"]