import ujson

from cats.v2.errors import MalformedData
from cats.v2.scheme.base import Scheme
from cats.v2.types import Data

__all__ = [
    'JSON',
]


class JSON(Scheme):
    type_id = 1
    type_name = 'json'

    def loads(self, buff: bytes | str) -> Data:
        try:
            return ujson.loads(buff)
        except ValueError as err:
            raise MalformedData('Failed to parse JSON from buffer', data=buff) from err

    def dumps(self, data: Data) -> bytes:
        return ujson.dumps(data, ensure_ascii=False, escape_forward_slashes=False).encode('utf-8')
