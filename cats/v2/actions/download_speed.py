from pathlib import Path
from typing import Generator, Iterable

from struct_model import StructModel, uInt4

from cats.v2.actions.base import Action
from cats.v2.errors import InterfaceViolation

__all__ = [
    'DownloadSpeedAction',
]


class DownloadSpeedAction(Action):
    __slots__ = ('speed',)
    type_id = 0x05
    type_name = 'DownloadSpeed'

    class Head(StructModel):
        speed: uInt4

    def __init__(self, speed: int = 0):
        super().__init__()
        self.speed: int = speed

    @classmethod
    def from_buffer(cls) -> Generator[bytes, int, 'Action']:
        buff = yield cls.Head.struct.size
        head: cls.Head = cls.Head.unpack(buff)
        action = cls(**head.dict())
        return action

    def __iter__(self) -> Iterable[bytes]:
        yield self.type_byte
        yield self.Head(speed=self.speed).pack()

    async def prepare(self) -> None:
        pass

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        raise InterfaceViolation('Cannot store "DownloadSpeedAction"')

    def __repr__(self) -> str:
        return f'{type(self).__name__}(speed={self.speed})'
