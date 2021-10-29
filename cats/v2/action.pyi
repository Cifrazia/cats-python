import asyncio
from logging import getLogger
from time import time_ns
from typing import AsyncIterator, TypeAlias, TypeVar

from struct_model import *

from cats.v2.config import Config
from cats.v2.connection import Connection
from cats.v2.headers import Headers, T_Headers
from cats.v2.registry import Selector
from cats.v2.types import BytesAnyGen

__all__ = [
    'ActionLike',
    'Input',
    'BaseAction',
    'BasicAction',
    'Action',
    'StreamAction',
    'InputAction',
    'DownloadSpeedAction',
    'CancelInputAction',
    'PingAction',
    'StartEncryptionAction',
    'StopEncryptionAction',
]

logging = getLogger('CATS.conn')

MAX_IN_MEMORY: int
MAX_CHUNK_READ: int

ActionLike: TypeAlias = TypeVar('ActionLike', bound='Action')


class Input:
    __slots__ = ('future', 'conn', 'message_id', 'bypass_count', 'timer')

    def __init__(self,
                 future: asyncio.Future,
                 conn: Connection,
                 message_id: int,
                 bypass_count: bool = False,
                 timeout: float | int = None):
        self.timer: asyncio.TimerHandle | None = None
        self.future: asyncio.Future = future
        self.conn: Connection = conn
        self.message_id: int = message_id
        self.bypass_count: bool = bypass_count
        if timeout:
            self.timer = asyncio.get_running_loop().call_later(timeout, self.cancel)

    def done(self, result) -> None: ...

    def cancel(self) -> None: ...


class BaseAction(dict):
    __slots__ = ('data', 'headers', 'message_id', 'conn')
    __registry__: dict[bytes, type['BaseAction']] = {}
    HEADER_SEPARATOR = b'\x00\x00'

    type_id: bytes
    Head: type
    conf: property | Config | None
    status: property | int
    offset: property | int
    skip: property | int

    def __init__(self, data=None, *, headers: T_Headers = None, status: int = None,
                 message_id: int = None):
        self.data = data
        self.headers: Headers = Headers(headers or {})
        self.status: int = self.headers.get('Status', status or 200)
        self.message_id: int | None = message_id
        self.conn: Connection | None = None
        super().__init__()

    def __init_subclass__(cls, *, abstract: bool = False) -> None: ...

    @classmethod
    def get_type_by_id(cls, type_id: bytes) -> type['BaseAction'] | None: ...

    async def ask(self, data=None, data_type: int = None, compressor: Selector = None, *,
                  headers: T_Headers = None, status: int = None,
                  bypass_limit: bool = False, bypass_count: bool = False,
                  timeout: int | float = None) -> 'InputAction': ...

    @classmethod
    async def init(cls, conn: Connection) -> 'BaseAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'BaseAction.Head': ...

    async def dump_data(self, size: int) -> None: ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class BasicAction(BaseAction):
    __slots__ = ('data_len', 'data_type', 'compressor', 'encoded', '_prepared')

    def __init__(self, data=None, *, headers: T_Headers = None, status: int = None,
                 message_id: int = None, data_len: int = None, data_type: int = None, compressor: Selector = None,
                 encoded: Selector = None):
        self.data_len: int | None = data_len
        self.data_type: int | None = data_type
        self.compressor: Selector | None = compressor
        self.encoded: Selector | None = encoded
        self._prepared: bool = False
        super().__init__(data, headers=headers, status=status, message_id=message_id)

    async def recv_data(self) -> None: ...

    async def _recv_small_data(self) -> None: ...

    async def _recv_large_data(self) -> None: ...

    async def _recv_chunk(self, left: int) -> (bytes, int): ...

    async def prepare(self) -> None: ...

    async def _encode(self) -> None: ...

    async def _write_data_to_stream(self) -> None: ...

    def __repr__(self) -> str: ...


class Action(BasicAction):
    class Head(StructModel):
        handler_id: uInt2
        message_id: uInt2
        send_time: uInt8
        data_type: uInt1
        compressor: uInt1
        data_len: uInt4

    __slots__ = ('handler_id', 'send_time')

    def __init__(self, data=None, *, headers: T_Headers = None, status: int = None, message_id: int = None,
                 handler_id: int = None, data_len: int = None, data_type: int = None, compressor: Selector = None,
                 send_time: float = None, encoded: Selector = None):
        self.handler_id: int | None = handler_id
        self.send_time = send_time or (time_ns() // 1000000)
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         data_len=data_len, data_type=data_type, compressor=compressor, encoded=encoded)

    @classmethod
    async def init(cls, conn: Connection) -> 'Action': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'Action.Head': ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class StreamAction(Action):
    class Head(StructModel):
        handler_id: uInt2
        message_id: uInt2
        send_time: uInt8
        data_type: uInt1
        compressor: uInt1

    def __init__(self, data=None, *, headers: T_Headers = None, status: int = None, message_id: int = None,
                 handler_id: int = None, data_type: int = None, compressor: Selector = None,
                 send_time: float = None):
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         handler_id=handler_id, data_type=data_type, compressor=compressor,
                         send_time=send_time)

    @classmethod
    async def init(cls, conn: Connection) -> 'StreamAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'StreamAction.Head': ...

    async def recv_data(self) -> None: ...

    async def _recv_large_chunk(self, fh, chunk_size) -> int: ...

    async def _recv_small_chunk(self, fh, chunk_size) -> int: ...

    async def send(self, conn: Connection) -> None: ...

    async def _write_data_to_stream(self) -> None: ...

    async def _async_gen(self, gen: BytesAnyGen, chunk_size: int) -> AsyncIterator[bytes]: ...

    def __repr__(self) -> str: ...


class InputAction(BasicAction):
    class Head(StructModel):
        message_id: uInt2
        data_type: uInt1
        compressor: uInt1
        data_len: uInt4

    @classmethod
    async def init(cls, conn: Connection) -> 'InputAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'InputAction.Head': ...

    async def send(self, conn: Connection) -> None: ...

    async def reply(self, data=None, data_type: int = None, compressor: Selector = None, *,
                    headers: T_Headers = None, status: int = None) -> ActionLike | None: ...

    async def cancel(self) -> ActionLike | None: ...


class DownloadSpeedAction(BaseAction):
    class Head(StructModel):
        speed: uInt4

    def __init__(self, speed: int):
        super().__init__()
        self.speed: int = speed

    @classmethod
    async def init(cls, conn: Connection) -> 'DownloadSpeedAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'DownloadSpeedAction.Head': ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class CancelInputAction(BaseAction):
    class Head(StructModel):
        message_id: uInt2

    @classmethod
    async def init(cls, conn: Connection) -> 'CancelInputAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'CancelInputAction.Head': ...

    async def send(self, conn: Connection) -> None: ...


class PingAction(BaseAction):
    class Head(StructModel):
        send_time: uInt8

    def __init__(self, send_time: int = None):
        super().__init__()
        self.recv_time: int = time_ns() // 1000000
        self.send_time: int = send_time or self.recv_time

    @classmethod
    async def init(cls, conn: Connection) -> 'PingAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'PingAction.Head': ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class StartEncryptionAction(BaseAction):
    __slots__ = ('cypher_type', 'exchange_type', 'public_key')
    type_id = b'\xF0'

    class Head(StructModel):
        cypher_type: uInt1
        exchange_type: uInt1
        length: uInt4

    def __init__(self, cypher_type: int, exchange_type: int, public_key: bytes):
        super().__init__()
        self.cypher_type: int = cypher_type
        self.exchange_type: int = exchange_type
        self.public_key: bytes = public_key

    @classmethod
    async def init(cls, conn) -> 'StartEncryptionAction': ...

    async def send(self, conn) -> None: ...

    def __repr__(self) -> str: ...


class StopEncryptionAction(BaseAction):
    type_id = b'\xF1'

    @classmethod
    async def init(cls, conn) -> 'StopEncryptionAction': ...

    async def send(self, conn) -> None: ...

    def __repr__(self) -> str: ...
