import msgpack

from cats.v2.errors import MalformedData
from cats.v2.scheme.base import Scheme
from cats.v2.types import Data

__all__ = [
    'MsgPack',
]


class MsgPack(Scheme):
    type_id = 0
    type_name = 'msgpack'

    def loads(self, buff: bytes) -> Data:
        try:
            return msgpack.loads(buff)
        except ValueError as err:
            raise MalformedData('Failed to parse MsgPack from buffer', data=buff) from err

    def dumps(self, data: Data) -> bytes:
        return msgpack.dumps(data)
