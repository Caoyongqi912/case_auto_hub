
from app.mapper import Mapper
from app.model.interface.interfaceGlobal import  InterfaceGlobalHeader, InterfaceGlobalFunc




class InterfaceGlobalHeaderMapper(Mapper[InterfaceGlobalHeader]):
    __model__ = InterfaceGlobalHeader


class InterfaceGlobalFuncMapper(Mapper[InterfaceGlobalFunc]):
    __model__ = InterfaceGlobalFunc


__all__ = [
    "InterfaceGlobalHeaderMapper",
    "InterfaceGlobalFuncMapper"
]
