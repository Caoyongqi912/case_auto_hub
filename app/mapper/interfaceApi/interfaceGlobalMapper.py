
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

