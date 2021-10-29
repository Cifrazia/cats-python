from abc import ABC
from pathlib import Path

from cats.v2.headers import T_Headers
from cats.v2.registry import Item

__all__ = [
    'Compressor',
]


class Compressor(Item, ABC):
    async def compress(
        self, data: bytes, headers: T_Headers
    ) -> bytes:
        raise NotImplementedError

    async def decompress(
        self, data: bytes, headers: T_Headers
    ) -> bytes:
        raise NotImplementedError

    async def compress_file(
        self, src: Path, dst: Path, headers: T_Headers
    ) -> None:
        raise NotImplementedError

    async def decompress_file(
        self, src: Path, dst: Path, headers: T_Headers
    ) -> None:
        raise NotImplementedError
