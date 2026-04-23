from typing import List, Dict

from sqlalchemy import insert

from app.mapper import Mapper
from app.model.interfaceAPIModel.interfaceGlobalModel import  InterfaceGlobalHeader, InterfaceGlobalFunc

__all__ = [
    "InterfaceGlobalHeaderMapper",
    "InterfaceGlobalFuncMapper"
]





class InterfaceGlobalHeaderMapper(Mapper[InterfaceGlobalHeader]):
    __model__ = InterfaceGlobalHeader



class InterfaceGlobalFuncMapper(Mapper[InterfaceGlobalFunc]):
    __model__ = InterfaceGlobalFunc

    @classmethod
    async def init_interface_funcs(cls, methods: List[Dict[str, str]]):

        try:
            async with cls.transaction() as session:
                await session.execute(
                    insert(cls.__model__).values(methods)
                )
                await session.commit()
        except Exception as e:
            raise e