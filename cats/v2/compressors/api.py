import shutil
from pathlib import Path

from cats.v2.compressors.base import Compressor
from cats.v2.errors import InvalidCompressor
from cats.v2.headers import T_Headers
from cats.v2.options import Options
from cats.v2.registry import Registry, Selector

__all__ = [
    'CompressorAPI',
]


class CompressorAPI(Registry):
    item_type = Compressor

    def get_compressor_name(
        self, selector: Selector, default: str = 'unknown'
    ) -> str:
        """ Returns Type Name by it's id (w/ fallback to default) """
        try:
            return self.find_strict(selector).type_name
        except KeyError:
            return default

    async def propose_compressor(
        self, buff: bytes | Path, headers: T_Headers, options: Options
    ) -> Compressor | None:
        if isinstance(buff, bytes):
            ln = len(buff)
        elif isinstance(buff, Path):
            ln = buff.stat().st_size
        else:
            raise InvalidCompressor('Unsupported buffer type', data=buff, headers=headers, options=options)

        if ln > 4096:
            return options.default_compressor

    async def compress(
        self, buff: bytes, headers: T_Headers, options: Options
    ) -> (bytes, int):
        if compressor := await self.propose_compressor(buff, headers, options):
            return await compressor.compress(buff, headers), compressor.type_id

        return buff, 0

    async def compress_file(
        self, src: Path, dst: Path, headers: T_Headers, options: Options
    ) -> int:
        if compressor := await self.propose_compressor(src, headers, options):
            await compressor.compress_file(src, dst, headers)
            return compressor.type_id
        shutil.copyfile(src, dst, follow_symlinks=True)
        return 0

    async def decompress(
        self, compressor_id: Selector, data: bytes, headers: T_Headers
    ) -> bytes:
        if compressor_id:
            compressor = self.find_strict(compressor_id)
            return await compressor.decompress(data, headers)

        return data

    async def decompress_file(
        self, compressor_id: Selector, src: Path, dst: Path, headers: T_Headers
    ) -> None:
        if compressor_id:
            compressor = self.find_strict(compressor_id)
            await compressor.decompress_file(src, dst, headers)
            return

        shutil.copyfile(src, dst, follow_symlinks=True)
