import asyncio
from typing import List, Callable, Any
from collections import deque

from dataclasses import dataclass


@dataclass
class Master:
    name: str


@dataclass
class Man1(Master):
    age: int

    def __post_init__(self):
        print(self.name)




if __name__ == '__main__':
    m1 = Man1(name="cyq", age=18)
