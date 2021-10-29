from pathlib import Path

from cats.v2 import Options, Registry, Selector, T_Headers
from cats.v2.compressors.base import Compressor


class CompressorAPI(Registry):
    item_type = Compressor
    registry: dict[int, Compressor]
    named_registry: dict[str, Compressor]

    def get_compressor_name(
        self, selector: Selector, default: str = 'unknown'
    ) -> str: ...

    async def propose_compressor(
        self, buff: bytes | Path, headers: T_Headers, options: Options
    ) -> Compressor | None: ...

    async def compress(
        self, buff: bytes, headers: T_Headers, options: Options
    ) -> (bytes, int): ...

    async def compress_file(
        self, src: Path, dst: Path, headers: T_Headers, options: Options
    ) -> int: ...

    async def decompress(
        self, compressor_id: Selector, data: bytes, headers: T_Headers, options: Options
    ) -> bytes: ...

    async def decompress_file(
        self, compressor_id: Selector, src: Path, dst: Path, headers: T_Headers, options: Options
    ) -> None: ...

    def find(self, selector: Selector = None) -> Compressor | None: ...

    def find_strict(self, selector: Selector = None) -> Compressor: ...
