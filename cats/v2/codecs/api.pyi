from pathlib import Path
from typing import Any

from cats.v2 import Options, Registry, Selector, T_Headers
from cats.v2.codecs.base import Codec


class CodecAPI(Registry):
    item_type = Codec
    registry: dict[int, Codec]
    named_registry: dict[str, Codec]

    async def encode(self, buff: Any, headers: T_Headers, options: Options) -> (bytes, int): ...

    async def decode(self, codec_id: Selector, buff: bytes | Path, headers: T_Headers, options: Options) -> Any: ...

    def get_codec_name(self, codec_id: Selector, default: str = 'unknown') -> str: ...

    def find(self, selector: Selector = None) -> Codec | None: ...

    def find_strict(self, selector: Selector = None) -> Codec: ...
