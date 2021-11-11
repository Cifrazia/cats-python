import asyncio
from dataclasses import dataclass

from tornado.iostream import StreamClosedError

from cats.v2.actions import *
from cats.v2.codecs import *
from cats.v2.compressors import *
from cats.v2.cypher import *
from cats.v2.errors import CatsError
from cats.v2.handshake import Handshake
from cats.v2.key_exchanger import *
from cats.v2.scheme import *

__all__ = [
    'Config',
]


@dataclass
class Config:
    idle_timeout: float | int = 120.0
    input_timeout: float | int = 120.0
    input_limit: int = 5
    handshake: Handshake | None = None
    debug: bool = False
    stream_errors: tuple[type[Exception], ...] = (
        asyncio.TimeoutError, asyncio.CancelledError, asyncio.InvalidStateError, StreamClosedError,
    )
    ignore_errors: tuple[type[Exception], ...] = (
        *stream_errors, CatsError, KeyboardInterrupt,
    )
    actions: ActionAPI = ActionAPI([
        DownloadSpeedAction,
        StartEncryptionAction,
        StopEncryptionAction,
        InputAction,
        CancelInputAction,
        PingAction,
    ])
    schemes: SchemeAPI = SchemeAPI([MsgPack(), JSON(), YAML()])
    codecs: CodecAPI = CodecAPI([ByteCodec(), FileCodec(), SchemeCodec()])
    compressors: CompressorAPI = CompressorAPI([GzipCompressor(), ZlibCompressor()])
    cyphers: CypherAPI = CypherAPI([FernetCypher()])
    key_exchangers: KeyExchangerAPI = KeyExchangerAPI([ECDHE()])
