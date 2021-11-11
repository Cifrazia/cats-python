from pathlib import Path
from typing import Generator, Iterable

from struct_model import StructModel, uInt1, uInt4

from cats.v2.actions.base import BaseAction
from cats.v2.errors import InterfaceViolation

__all__ = [
    'StartEncryptionAction',
    'StopEncryptionAction',
]


class StartEncryptionAction(BaseAction):
    __slots__ = ('cypher_type', 'exchange_type', 'public_key')
    type_id = 0xF0
    type_name = 'StartEncryption'

    class Head(StructModel):
        cypher_type: uInt1
        exchange_type: uInt1
        length: uInt4

    def __init__(self, cypher_type: int, exchange_type: int, public_key: bytes, meta: 'BaseAction.Meta' = None):
        super().__init__(meta)
        self.cypher_type: int = cypher_type
        self.exchange_type: int = exchange_type
        self.public_key: bytes = public_key

    @classmethod
    def from_buffer(cls) -> Generator[int, bytes, 'StartEncryptionAction']:
        buff = yield cls.Head.struct.size
        head: cls.Head = cls.Head.unpack(buff)
        buff = yield head.length
        key: bytes = buff
        return cls(head.cypher_type, head.exchange_type, key)

    def __iter__(self) -> Iterable[bytes]:
        yield self.type_byte
        yield self.Head(self.cypher_type, self.exchange_type, len(self.public_key)).pack()
        yield self.public_key

    async def prepare(self) -> None:
        pass

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        raise InterfaceViolation('Cannot store "StartEncryptionAction"')


class StopEncryptionAction(BaseAction):
    type_id = 0xF1
    type_name = 'StopEncryption'

    @classmethod
    def from_buffer(cls) -> Generator[bytes, int, 'StopEncryptionAction']:
        yield 0
        return cls()

    def __iter__(self) -> Iterable[bytes]:
        yield self.type_byte

    async def prepare(self) -> None:
        pass

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        raise InterfaceViolation('Cannot store "StopEncryptionAction"')
