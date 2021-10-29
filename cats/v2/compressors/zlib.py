from pathlib import Path

import zlib

from cats.v2.compressors.base import Compressor
from cats.v2.errors import CompressorError
from cats.v2.headers import T_Headers
from cats.v2.utils import from_uint, to_uint

__all__ = [
    'ZlibCompressor',
]


class ZlibCompressor(Compressor):
    """Modified ZLib compressor: uint4 length of original data will be prepended to result payload"""
    type_id = 0x02
    type_name = 'zlib'

    async def compress(
        self, data: bytes, headers: T_Headers
    ) -> bytes:
        headers['Adler32'] = zlib.adler32(data)
        return to_uint(len(data), 4) + zlib.compress(data, level=6)

    async def decompress(
        self, data: bytes, headers: T_Headers
    ) -> bytes:
        try:
            ln, data = from_uint(data[:4]), data[4:]
            buff = zlib.decompress(data)
            checksum = headers.get('Adler32', None)
            if ln != len(buff):
                raise CompressorError('Broken data received: Length mismatch', data=data,
                                      headers=headers)
            if checksum is not None and zlib.adler32(buff) != checksum:
                raise CompressorError('Broken data received: Checksum mismatch',
                                      data=data, headers=headers)
            return buff
        except zlib.error as err:
            raise CompressorError('Failed to decompress file as zlib',
                                  data=data, headers=headers) from err

    async def compress_file(
        self, src: Path, dst: Path, headers: T_Headers
    ) -> None:
        compressor = zlib.compressobj(level=6)
        value = 1
        ln = src.stat().st_size
        with src.open('rb') as rc, dst.open('wb') as wc:
            wc.write(to_uint(ln, 4))
            while line := rc.read(1 << 24):
                value = zlib.adler32(line, value)
                wc.write(compressor.compress(line))
            wc.write(compressor.flush())
        del compressor
        headers['Adler32'] = value

    async def decompress_file(
        self, src: Path, dst: Path, headers: T_Headers
    ) -> None:
        try:
            compressor = zlib.decompressobj()
            value = 1
            with src.open('rb') as rc, dst.open('wb') as wc:
                ln = from_uint(rc.read(4))
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
        except zlib.error as err:
            raise CompressorError('Failed to decompress file as zlib',
                                  data=src, headers=headers) from err
