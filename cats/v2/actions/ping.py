from pathlib import Path
from time import time_ns
from typing import Generator, Iterable

from struct_model import StructModel, uInt8

from cats.v2.actions.base import BaseAction
from cats.v2.errors import InterfaceViolation

__all__ = [
    'PingAction',
]


class PingAction(BaseAction):
    __slots__ = ('recv_time', 'send_time')
    type_id = 0xFF
    type_name = 'Ping'

    class Head(StructModel):
        send_time: uInt8

    def __init__(self, send_time: int = None, recv_time: int = None):
        super().__init__()
        self.recv_time = recv_time or time_ns() // 1000_000
        self.send_time = send_time or self.recv_time

    @classmethod
    def from_buffer(cls) -> Generator[bytes, int, 'BaseAction']:
        buff = yield cls.Head.struct.size
        head: cls.Head = cls.Head.unpack(buff)
        action = cls(**head.dict())
        return action

    def __iter__(self) -> Iterable[bytes]:
        self.send_time = time_ns() // 1000_000
        yield self.type_byte
        yield self.Head(send_time=self.send_time).pack()

    async def prepare(self) -> None:
        pass

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        raise InterfaceViolation('Cannot store "PingAction"')

    def __repr__(self) -> str:
        return f'{type(self).__name__}(send_time={self.send_time}, recv_time={self.recv_time})'
