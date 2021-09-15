import asyncio
from dataclasses import dataclass
from typing import Type

from tornado.iostream import StreamClosedError

from cats.errors import CatsError
from cats.v2.handshake import Handshake

__all__ = [
    'Config',
]


@dataclass
class Config:
    idle_timeout: float | int = 120.0
    input_timeout: float | int = 120.0
    input_limit: int = 5
    debug: bool = False
    max_plain_payload: int = 16 * 1024 * 1024
    stream_errors: Type[Exception] | tuple[Type[Exception]] = (
        asyncio.TimeoutError,
        asyncio.CancelledError,
        asyncio.InvalidStateError,
        StreamClosedError,
    )
    ignore_errors: Type[Exception] | tuple[Type[Exception]] = (
        *stream_errors,
        CatsError,
        KeyboardInterrupt,
    )
    handshake: Handshake | None = None
