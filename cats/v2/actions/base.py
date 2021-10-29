from abc import ABC
from enum import IntEnum
from io import BytesIO
from pathlib import Path
from time import time_ns
from typing import Generator, Iterable

from struct_model import StructModel, uInt1, uInt4, uInt8

from cats.v2.registry import Item

__all__ = [
    'Action',
]


class State(IntEnum):
    raw = 0
    prepared = 1
    compiled = 2


class Action(Item, ABC):
    __slots__ = (
        'state',
        'compiled',
        'meta',
    )
    MAX_IN_MEMORY = 1 << 24
    MAX_CHUNK_READ = 1 << 20

    def __init__(self, meta: 'Action.Meta' = None):
        self.state: State = State.raw
        if meta is None:
            meta = self.Meta(
                created_at=time_ns() // 1000_000,
                expired_at=0,
                times_used=0,
            )
        self.meta = meta
        self.compiled: BytesIO | None = None

    @classmethod
    def from_buffer(cls) -> Generator[bytes, int, 'Action']:
        """
        Will yield amount of bytes to read, should accept bytes of requested length
        :return:
        """
        raise NotImplementedError

    def __iter__(self) -> Iterable[bytes]:
        """
        Return bytes sequence that should be sent to IOStream
        :return:
        """
        raise NotImplementedError

    async def prepare(self) -> None:
        """
        Encode payload to bytes / Path
        Compress bytes / Path
        Set codec and compressor to a specific values
        """
        raise NotImplementedError

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        """
        Write compiled action to .cats file at @filename that will be invalidated after @ttl or never
        :param filename:  Optional path to store. temp_file created if None
        :param ttl: Seconds to live. 0 == infinite
        :return: Path to a *temp* `.cats` file
        """
        raise NotImplementedError

    @classmethod
    async def load(cls, filename: str | Path) -> 'Action':
        """
        Read `.cats` file, load META to __init__, put descriptor to _compiled section and set state to Compiled
        :param filename:
        :return:
        """
        compiled = open(filename, 'rb+')
        meta = compiled.read(cls.Meta.struct.size)
        action = cls(cls.Meta.loads(meta))
        action.meta.times_used += 1
        compiled.seek(0)
        compiled.write(action.meta.pack())
        compiled.flush()
        action.compiled = compiled
        action.state = State.compiled
        return action

    @property
    def type_byte(self) -> bytes:
        return self.type_id.to_bytes(1, 'big', signed=False)

    def __repr__(self) -> str:
        return f'{type(self).__qualname__}(meta={self.meta})'

    def __del__(self):
        if self.compiled is not None and not self.compiled.closed:
            self.compiled.close()

    class Meta(StructModel):
        version: uInt4  # .cats Meta version, not file version. Currently is 0
        created_at: uInt8
        expired_at: uInt8
        compressor: uInt1
        times_used: uInt4
