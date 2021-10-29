from dataclasses import dataclass

from cats.v2.compressors import Compressor
from cats.v2.cypher import Cypher
from cats.v2.scheme import MsgPack, Scheme

__all__ = [
    'Options',
]


@dataclass
class Options:
    scheme: Scheme = MsgPack()
    cypher: Cypher | None = None
    api_version: int = 1
    download_speed: int = 0
    allowed_compressors: tuple[Compressor] = ()
    default_compressor: Compressor | None = None
    symmetric_key: bytes | None = None
    private_key: bytes | None = None
    public_key: bytes | None = None
