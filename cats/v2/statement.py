from dataclasses import asdict, dataclass
from typing import Literal, TypeVar

import ujson

from cats import to_uint

__all__ = [
    'ClientStatement',
    'ServerStatement',
]
T = TypeVar('T', bound='Statement')


@dataclass
class Statement:
    def pack(self) -> bytes:
        data: str = ujson.dumps(asdict(self), ensure_ascii=False, escape_forward_slashes=False)
        return to_uint(len(data), 4) + data.encode('utf-8')

    @classmethod
    def unpack(cls, buffer: bytes) -> T:
        return cls(**ujson.loads(buffer))  # noqa


@dataclass
class ClientStatement(Statement):
    api: int
    client_time: int
    scheme_format: Literal['JSON']
    compressors: list[Literal['gzip', 'zlib']]
    default_compression: Literal['gzip', 'zlib']


@dataclass
class ServerStatement(Statement):
    server_time: int
