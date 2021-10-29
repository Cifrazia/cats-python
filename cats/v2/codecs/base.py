from abc import ABC
from pathlib import Path
from typing import Any

from cats.v2.headers import T_Headers
from cats.v2.options import Options
from cats.v2.registry import Item

__all__ = [
    'Codec',
]


class Codec(Item, ABC):
    async def encode(
        self, data: Any, headers: T_Headers, options: Options
    ) -> bytes:
        """
        Encode data into byte buffer, change headers if required
        :raise TypeError: Encoder doesn't support this type
        :raise ValueError: Failed to encode
        """
        raise NotImplementedError

    async def decode(
        self, buff: bytes | Path, headers: T_Headers, options: Options
    ) -> Any:
        """
        Decode byte buffer into <Any> data, use headers if required
        :raise TypeError: Encoder doesn't support this type
        :raise ValueError: Failed to encode
        """
        raise NotImplementedError
