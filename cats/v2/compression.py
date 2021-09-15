import gzip
import shutil
from pathlib import Path

import zlib

from cats.errors import ClientSupportError, CompressorError, InvalidCompressorError
from cats.types import T_Headers
from cats.utils import as_uint, to_uint

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
    async def compress(cls, data: bytes, headers: T_Headers) -> bytes:
        raise NotImplementedError

    @classmethod
    async def decompress(cls, data: bytes, headers: T_Headers) -> bytes:
        raise NotImplementedError

    @classmethod
    async def compress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        raise NotImplementedError

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        raise NotImplementedError


class DummyCompressor(BaseCompressor):
    type_id = 0x00
    type_name = 'dummy'

    @classmethod
    async def compress(cls, data: bytes, headers: T_Headers) -> bytes:
        return data

    @classmethod
    async def decompress(cls, data: bytes, headers: T_Headers) -> bytes:
        return data

    @classmethod
    async def compress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        shutil.copy(src.resolve().as_posix(), dst.resolve().as_posix())

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        shutil.copy(src.resolve().as_posix(), dst.resolve().as_posix())


class GzipCompressor(BaseCompressor):
    type_id = 0x01
    type_name = 'GZip'

    @classmethod
    async def compress(cls, data: bytes, headers: T_Headers) -> bytes:
        return gzip.compress(data, compresslevel=6)

    @classmethod
    async def decompress(cls, data: bytes, headers: T_Headers) -> bytes:
        return gzip.decompress(data)

    @classmethod
    async def compress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        with src.open('rb') as rc:
            with gzip.open(dst.resolve().as_posix(), 'wb', compresslevel=6) as wc:
                while line := rc.read(1 << 24):
                    wc.write(line)

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        with gzip.open(src.resolve().as_posix(), 'rb') as rc:
            with dst.open('wb') as wc:
                while line := rc.read(1 << 24):
                    wc.write(line)


class ZlibCompressor(BaseCompressor):
    """Modified ZLib compressor: uint4 length of original data will be prepended to result payload"""
    type_id = 0x02
    type_name = 'ZLib'

    @classmethod
    async def compress(cls, data: bytes, headers: T_Headers) -> bytes:
        headers['Adler32'] = zlib.adler32(data)
        return to_uint(len(data), 4) + zlib.compress(data, level=6)

    @classmethod
    async def decompress(cls, data: bytes, headers: T_Headers) -> bytes:
        ln, data = as_uint(data[:4]), data[4:]
        buff = zlib.decompress(data)
        checksum = headers.get('Adler32', None)
        if ln != len(buff):
            raise CompressorError('Broken data received: Length mismatch', data=data, headers=headers)
        if checksum is not None and zlib.adler32(buff) != checksum:
            raise CompressorError('Broken data received: Checksum mismatch', data=data, headers=headers)
        return buff

    @classmethod
    async def compress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        compressor = zlib.compressobj(level=6)
        value = 1
        ln = src.stat().st_size
        with src.open('rb') as rc:
            with dst.open('wb') as wc:
                wc.write(to_uint(ln, 4))
                while line := rc.read(1 << 24):
                    value = zlib.adler32(line, value)
                    wc.write(compressor.compress(line))
                wc.write(compressor.flush())
        del compressor
        headers['Adler32'] = value

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path, headers: T_Headers) -> None:
        compressor = zlib.decompressobj()
        value = 1
        with src.open('rb') as rc:
            with dst.open('wb') as wc:
                ln = as_uint(rc.read(4))
                while line := rc.read(1 << 24):
                    wc.write(buff := compressor.decompress(line))
                    value = zlib.adler32(buff, value)
                wc.write(compressor.flush())
        if dst.stat().st_size != ln:
            raise CompressorError('Broken data received: Length mismatch', data=src, headers=headers)
        checksum = headers.get('Adler32', None)
        if checksum is not None and value != checksum:
            dst.unlink(missing_ok=True)
            raise CompressorError('Broken data received: Checksum mismatch', data=src, headers=headers)


C_NONE = DummyCompressor.type_id
C_GZIP = GzipCompressor.type_id
C_ZLIB = ZlibCompressor.type_id


class Compressor:
    codes = {
        DummyCompressor.type_name.lower(): DummyCompressor.type_id,
        GzipCompressor.type_name.lower(): GzipCompressor.type_id,
        ZlibCompressor.type_name.lower(): ZlibCompressor.type_id,
    }
    compressors = {
        C_NONE: DummyCompressor,
        C_GZIP: GzipCompressor,
        C_ZLIB: ZlibCompressor,
    }

    @classmethod
    async def compress(cls, buff: bytes, headers: T_Headers, allowed: set[int], default: int,
                       compression: int = None) -> (bytes, int):
        try:
            if compression is None:
                compression = await cls.propose_compression(buff, headers, default)
            if compression not in allowed:
                raise ClientSupportError(f'Compression unsupported by client: {cls.compressors[compression].type_name}')
            buff = await cls.compressors[compression].compress(buff, headers)
            return buff, compression

        except (KeyError, ValueError, TypeError) as err:
            raise CompressorError(f'Failed to compress data: {str(err)}', data=buff, headers=headers) from err

    @classmethod
    async def decompress(cls, buff: bytes, headers: T_Headers, compression: int) -> bytes:
        try:
            return await cls.compressors[compression].decompress(buff, headers)
        except (KeyError, ValueError, TypeError) as err:
            raise CompressorError(f'Failed to decompress data: {str(err)}', data=buff, headers=headers) from err

    @classmethod
    async def compress_file(cls, src: Path, dst: Path, headers: T_Headers, allowed: set[int], default: int,
                            compression: int = None) -> int:
        try:
            if compression is None:
                compression = await cls.propose_compression(src, headers, default)
            if compression not in allowed:
                raise ClientSupportError(f'Compression unsupported by client: {cls.compressors[compression].type_name}')

            await cls.compressors[compression].compress_file(src, dst, headers)
            return compression
        except (KeyError, ValueError, TypeError) as err:
            raise CompressorError(f'Failed to compress file: {str(err)}', data=src, headers=headers)

    @classmethod
    async def decompress_file(cls, src: Path, dst: Path, headers: T_Headers, compression: int) -> None:
        try:
            await cls.compressors[compression].decompress_file(src, dst, headers)
        except (KeyError, ValueError, TypeError) as err:
            raise CompressorError(f'Failed to decompress file: {str(err)}', data=src, headers=headers)

    @classmethod
    async def propose_compression(cls, buff: bytes | Path, headers: T_Headers, default: int):
        if isinstance(buff, bytes):
            ln = len(buff)
        elif isinstance(buff, Path):
            ln = buff.stat().st_size
        else:
            raise InvalidCompressorError('Unsupported buffer type', data=buff, headers=headers)
        if ln <= 4096:
            return C_NONE
        else:
            return default
