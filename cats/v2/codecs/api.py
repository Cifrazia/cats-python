from pathlib import Path
from typing import Any

from cats.v2.codecs.base import Codec
from cats.v2.errors import CodecError, InvalidCodec
from cats.v2.headers import T_Headers
from cats.v2.options import Options
from cats.v2.registry import Registry, Selector

__all__ = [
    'CodecAPI',
]


class CodecAPI(Registry):
    item_type = Codec

    async def encode(self, buff: Any, headers: T_Headers, options: Options) -> (bytes, int):
        """
        Takes any supported data type and returns tuple (encoded: bytes, type_id: int)
        """
        for type_id, codec in self.registry.items():
            try:
                encoded = await codec.encode(buff, headers, options)
                return encoded, type_id
            except InvalidCodec:
                continue

        raise CodecError(f'Failed to encode data: Type {type(buff)} not supported',
                         data=buff, headers=headers, options=options)

    async def decode(self, codec_id: Selector, buff: bytes | Path, headers: T_Headers, options: Options) -> Any:
        if codec := self.find(codec_id):
            return await codec.decode(buff, headers, options)
        raise InvalidCodec(f'Codec with type ID {codec_id} not found', data=buff, headers=headers, options=options)

    def get_codec_name(self, codec_id: Selector, default: str = 'unknown') -> str:
        """
        Returns Type Name by it's id (w/ fallback to default)
        :param codec_id:
        :param default:
        :return:
        """
        if codec := self.find(codec_id):
            return codec.type_name
        return default
