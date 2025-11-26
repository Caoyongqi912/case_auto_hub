from typing import ClassVar, Type, TypeVar, Any, Generic


class Base:
    ...


class A(Base):
    name = "a"


class B(Base):
    name = 'b'


T = TypeVar('T', bound=Base)


class Master(Generic[T]):
    __model__: Type[T]| Any

    @classmethod
    def return_(cls) -> T:
        return cls.__model__


class SlaverA(Master[A]):
    __model__ = A


class SlaverB(Master[B]):
    __model__ = B


if __name__ == '__main__':
    a = SlaverA.return_()
    b = SlaverB.return_()
    print(a.name)  # a
    print(b.name)  # b
