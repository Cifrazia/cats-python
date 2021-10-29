from dataclasses import asdict, dataclass, field
from typing import Literal, TypeVar

from cats.v2.scheme import Scheme, SchemeAPI
from cats.v2.utils import to_uint

__all__ = [
    'Statement',
    'ClientStatement',
    'ServerStatement',
]

T = TypeVar('T', bound='Statement')


@dataclass
class Statement:
    def pack(self, scheme: Scheme) -> bytes:
        data = scheme.dumps(asdict(self))
        return to_uint(len(data), 4) + data

    @classmethod
    def unpack(cls, buffer: bytes, scheme_api: SchemeAPI) -> T:
        data = scheme_api.loads(buffer)
        return cls(**data)  # noqa


@dataclass
class ClientStatement(Statement):
    api: int
    client_time: int
    scheme_format: Literal['json', 'yaml', 'msgpack'] = 'json'
    compressors: list[Literal['gzip', 'zlib']] = field(default_factory=lambda: ['zlib'])
    default_compression: Literal['gzip', 'zlib'] = 'zlib'


@dataclass
class ServerStatement(Statement):
    server_time: int
