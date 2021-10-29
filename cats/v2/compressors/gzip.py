import gzip
from pathlib import Path

from cats.v2.compressors.base import Compressor
from cats.v2.errors import CompressorError
from cats.v2.headers import T_Headers

__all__ = [
    'GzipCompressor',
]


class GzipCompressor(Compressor):
    type_id = 0x01
    type_name = 'gzip'

    async def compress(
        self, data: bytes, headers: T_Headers
    ) -> bytes:
        return gzip.compress(data, compresslevel=6)

    async def decompress(
        self, data: bytes, headers: T_Headers
    ) -> bytes:
        try:
            return gzip.decompress(data)
        except gzip.BadGzipFile as err:
            raise CompressorError('Failed to decompress file as gzip', data=data, headers=headers) from err

    async def compress_file(
        self, src: Path, dst: Path, headers: T_Headers
    ) -> None:
        # TODO: Rewrite as parenthesized once https://youtrack.jetbrains.com/issue/PY-42200 resolved
        with src.open('rb') as rc, gzip.open(dst.resolve().as_posix(), 'wb', compresslevel=6) as wc:
            while line := rc.read(1 << 24):
                wc.write(line)

    async def decompress_file(
        self, src: Path, dst: Path, headers: T_Headers
    ) -> None:
        try:
            # TODO: Rewrite as parenthesized once https://youtrack.jetbrains.com/issue/PY-42200 resolved
            with gzip.open(src.resolve().as_posix(), 'rb') as rc, dst.open('wb') as wc:
                while line := rc.read(1 << 24):
                    wc.write(line)
        except gzip.BadGzipFile as err:
            raise CompressorError('Failed to decompress file as gzip', data=src, headers=headers) from err
