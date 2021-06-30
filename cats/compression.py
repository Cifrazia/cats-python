import gzip
import shutil
from pathlib import Path
from typing import Union

import zlib

__all__ = [
    'C_NONE',
    'C_ZLIB',
    'C_GZIP',
    'BaseCompressor',
    'DummyCompressor',
    'GzipCompressor',
    'ZlibCompressor',
    'Compressor',
]


class BaseCompressor:
    type_id: int
    type_name: str

    @classmethod
    async def compress(cls, data: bytes) -> bytes:
        raise NotImplementedError

    @classmethod
    async def decompress(cls, data: bytes) -> bytes:
        raise NotImplementedError

    @classmethod
    async def compress_file(cls, src: Path, dst: Path) -> None:
        raise NotImplementedError

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path) -> None:
        raise NotImplementedError


class DummyCompressor(BaseCompressor):
    type_id = 0x00
    type_name = 'dummy'

    @classmethod
    async def compress(cls, data: bytes) -> bytes:
        return data

    @classmethod
    async def decompress(cls, data: bytes) -> bytes:
        return data

    @classmethod
    async def compress_file(cls, src: Path, dst: Path) -> None:
        shutil.copy(src.resolve().as_posix(), dst.resolve().as_posix())

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path) -> None:
        shutil.copy(src.resolve().as_posix(), dst.resolve().as_posix())


class GzipCompressor(BaseCompressor):
    type_id = 0x01
    type_name = 'GZip'

    @classmethod
    async def compress(cls, data: bytes) -> bytes:
        return gzip.compress(data, compresslevel=6)

    @classmethod
    async def decompress(cls, data: bytes) -> bytes:
        return gzip.decompress(data)

    @classmethod
    async def compress_file(cls, src: Path, dst: Path) -> None:
        with src.open('rb') as rc:
            with gzip.open(dst.resolve().as_posix(), 'wb', compresslevel=6) as wc:
                while line := rc.read(1 << 24):
                    wc.write(line)

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path) -> None:
        with gzip.open(src.resolve().as_posix(), 'rb') as rc:
            with dst.open('wb') as wc:
                while line := rc.read(1 << 24):
                    wc.write(line)


class ZlibCompressor(BaseCompressor):
    type_id = 0x02
    type_name = 'ZLib'

    @classmethod
    async def compress(cls, data: bytes) -> bytes:
        return zlib.compress(data, level=6)

    @classmethod
    async def decompress(cls, data: bytes) -> bytes:
        return zlib.decompress(data)

    @classmethod
    async def compress_file(cls, src: Path, dst: Path) -> None:
        compressor = zlib.compressobj(level=6)
        with src.open('rb') as rc:
            with dst.open('wb') as wc:
                while line := rc.read(1 << 24):
                    wc.write(compressor.compress(line))
                wc.write(compressor.flush())
        del compressor

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path) -> None:
        compressor = zlib.decompressobj()
        with src.open('rb') as rc:
            with dst.open('wb') as wc:
                while line := rc.read(1 << 24):
                    wc.write(compressor.decompress(line))
                wc.write(compressor.flush())


C_NONE = DummyCompressor.type_id
C_GZIP = GzipCompressor.type_id
C_ZLIB = ZlibCompressor.type_id


class Compressor:
    compressors = {
        C_NONE: DummyCompressor,
        C_GZIP: GzipCompressor,
        C_ZLIB: ZlibCompressor,
    }

    @classmethod
    async def compress(cls, buff: bytes, compression: int = None) -> (bytes, int):
        try:
            if compression is None:
                compression = await cls.propose_compression(buff)

            buff = await cls.compressors[compression].compress(buff)
            return buff, compression

        except (KeyError, ValueError, TypeError) as err:
            raise ValueError(f'Failed to compress data: {str(err)}')

    @classmethod
    async def decompress(cls, buff: bytes, compression: int) -> bytes:
        try:
            return await cls.compressors[compression].decompress(buff)
        except (KeyError, ValueError, TypeError) as err:
            raise ValueError(f'Failed to decompress data: {str(err)}')

    @classmethod
    async def compress_file(cls, src: Path, dst: Path, compression: int = None) -> int:
        try:
            if compression is None:
                compression = await cls.propose_compression(src)

            await cls.compressors[compression].compress_file(src, dst)
            return compression
        except (KeyError, ValueError, TypeError) as err:
            raise ValueError(f'Failed to compress file: {str(err)}')

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path, compression: int) -> None:
        try:
            await cls.compressors[compression].decompress_file(src, dst)
        except (KeyError, ValueError, TypeError) as err:
            raise ValueError(f'Failed to decompress file: {str(err)}')

    @classmethod
    async def propose_compression(cls, buff: Union[bytes, Path]):
        if isinstance(buff, bytes):
            ln = len(buff)
        elif isinstance(buff, Path):
            ln = buff.stat().st_size
        else:
            raise TypeError('Unsupported buffer type')
        if ln <= 4096:
            return C_NONE
        else:
            return C_ZLIB
