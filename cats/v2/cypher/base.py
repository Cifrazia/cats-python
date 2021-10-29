from abc import ABC
from enum import Enum, auto

from cats.v2.registry import Item

__all__ = [
    'Cypher',
]


class KeyType(Enum):
    symmetric = auto()
    asymmetric = auto()


class Cypher(Item, ABC):
    key_type: KeyType

    async def encrypt(
        self, data: bytes, key: bytes
    ) -> bytes:
        raise NotImplementedError

    async def decrypt(
        self, data: bytes, key: bytes
    ) -> bytes:
        raise NotImplementedError
