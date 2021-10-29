from pathlib import Path

from pytest import fixture

from cats.v2 import Compressor, T_Headers
from cats.v2.options import Options


@fixture
def broken_compressor():
    registry = Compressor.registry.copy()
    named_registry = Compressor.named_registry.copy()
    Compressor.registry.clear()
    Compressor.named_registry.clear()

    class BrokenCompressor(Compressor):
        type_id = 0
        type_name = 'broken'

        @classmethod
        async def compress(cls, data: bytes, headers: T_Headers, options: Options) -> bytes:
            raise ValueError

        @classmethod
        async def decompress(cls, data: bytes, headers: T_Headers, options: Options) -> bytes:
            raise ValueError

        @classmethod
        async def compress_file(cls, src: Path, dst: Path, headers: T_Headers, options: Options) -> None:
            raise ValueError

        @classmethod
        async def decompress_file(cls, src: Path, dst: Path, headers: T_Headers, options: Options) -> None:
            raise ValueError

    yield BrokenCompressor
    Compressor.registry = registry
    Compressor.named_registry = named_registry
