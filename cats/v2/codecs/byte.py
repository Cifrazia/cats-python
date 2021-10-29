from cats.v2.codecs.base import Codec
from cats.v2.errors import InvalidCodec
from cats.v2.headers import T_Headers
from cats.v2.options import Options

__all__ = [
    'ByteCodec',
]


class ByteCodec(Codec):
    type_id = 0x00
    type_name = 'bytes'

    async def encode(
        self, data: bytes | bytearray, headers: T_Headers, options: Options
    ) -> bytes:
        if data is not None and not isinstance(data, bytes | bytearray):
            raise InvalidCodec(f'{self} does not support {type(data)}', data=data, headers=headers, options=options)

        return bytes(data) if data else b''

    async def decode(
        self, data: bytes, headers: T_Headers, options: Options
    ) -> bytes:
        return bytes(data) if data else b''
