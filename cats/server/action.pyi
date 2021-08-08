import asyncio
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from struct import Struct
from time import time_ns
from typing import Any, AsyncIterator, Optional, Type, Union

from cats.server.conn import Connection
from cats.types import BytesAnyGen, BytesAsyncGen, Headers, T_Headers

__all__ = [
    'Input',
    'BaseAction',
    'BasicAction',
    'Action',
    'StreamAction',
    'InputAction',
    'DownloadSpeedAction',
    'CancelInputAction',
    'PingAction',
]

logging = getLogger('CATS.conn')

MAX_IN_MEMORY: int
MAX_CHUNK_READ: int


class Input:
    __slots__ = ('future', 'conn', 'message_id', 'bypass_count', 'timer')

    def __init__(self,
                 future: asyncio.Future,
                 conn: Connection,
                 message_id: int,
                 bypass_count: bool = False,
                 timeout: Union[float, int] = None):
        self.timer: Optional[asyncio.Task]
        self.future: asyncio.Future = future
        self.conn: Connection = conn
        self.message_id: int = message_id
        self.bypass_count: bool = bypass_count
        if timeout:
            self.timer = asyncio.get_event_loop().call_later(timeout, self.cancel)

    def cancel(self) -> None: ...


class BaseAction(dict):
    __slots__ = ('data', 'headers', 'message_id', 'conn')
    __registry__: dict[bytes, Type['BaseAction']] = {}
    HEADER_SEPARATOR = b'\x00\x00'

    type_id: bytes
    head_struct: Struct
    Head: Type

    def __init__(self, data: Any = None, *, headers: T_Headers = None, status: int = None,
                 message_id: int = None):
        self.data: Any = data
        self.headers: Headers = Headers(headers or {})
        self.status: int = self.headers.get('Status', status or 200)
        self.message_id: Optional[int] = message_id
        self.conn: Optional[Connection] = None
        super().__init__()

    def __init_subclass__(cls, *, type_id: int = 0, struct: Struct = None, abstract: bool = False) -> None: ...

    status: Union[property, int]
    offset: Union[property, int]

    @classmethod
    def get_class_by_type_id(cls, type_id: bytes) -> Optional[Type['BaseAction']]: ...

    async def ask(self, data: Any = None, data_type: int = None, compression: int = None, *,
                  headers: T_Headers = None, status: int = None,
                  bypass_limit: bool = False, bypass_count: bool = False,
                  timeout: Union[int, float] = None) -> 'InputAction': ...

    @classmethod
    async def init(cls, conn: Connection) -> 'BaseAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'BaseAction.Head': ...

    async def dump_data(self, size: int) -> None: ...

    async def handle(self) -> None: ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class BasicAction(BaseAction):
    __slots__ = ('data_len', 'data_type', 'compression', 'encoded')

    def __init__(self, data: Any = None, *, headers: T_Headers = None, status: int = None,
                 message_id: int = None, data_len: int = None, data_type: int = None, compression: int = None,
                 encoded: int = None):
        self.data_len: Optional[int] = data_len
        self.data_type: Optional[int] = data_type
        self.compression: Optional[int] = compression
        self.encoded: Optional[int] = encoded
        super().__init__(data, headers=headers, status=status, message_id=message_id)

    async def recv_data(self) -> None: ...

    async def _recv_small_data(self) -> None: ...

    async def _recv_large_data(self) -> None: ...

    async def _recv_chunk(self, left: int) -> (bytes, int): ...

    async def _encode(self) -> tuple[Union[Path, bytes], int, int, int]: ...

    async def _write_data_to_stream(self, conn: Connection, data: Union[Path, bytes],
                                    data_len: int, data_type: int, compression: int) -> None: ...

    def __repr__(self) -> str: ...


class Action(BasicAction):
    @dataclass
    class Head:
        handler_id: int
        message_id: int
        send_time: int
        data_type: int
        compression: int
        data_len: int

    __slots__ = ('handler_id', 'send_time')

    def __init__(self, data: Any = None, *, headers: T_Headers = None, status: int = None, message_id: int = None,
                 handler_id: int = None, data_len: int = None, data_type: int = None, compression: int = None,
                 send_time: float = None, encoded: int = None):
        self.handler_id: Optional[int] = handler_id
        self.send_time = send_time or (time_ns() // 1000000)
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         data_len=data_len, data_type=data_type, compression=compression, encoded=encoded)

    @classmethod
    async def init(cls, conn: Connection) -> 'Action': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'Action.Head': ...

    async def handle(self) -> None: ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class StreamAction(Action):
    @dataclass
    class Head:
        handler_id: int
        message_id: int
        send_time: int
        data_type: int
        compression: int

    def __init__(self, data: Any = None, *, headers: T_Headers = None, status: int = None, message_id: int = None,
                 handler_id: int = None, data_type: int = None, compression: int = None,
                 send_time: float = None):
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         handler_id=handler_id, data_type=data_type, compression=compression,
                         send_time=send_time)

    @classmethod
    async def init(cls, conn: Connection) -> 'StreamAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'StreamAction.Head': ...

    async def handle(self) -> None: ...

    async def recv_data(self) -> None: ...

    async def _recv_large_chunk(self, fh, chunk_size) -> int: ...

    async def _recv_small_chunk(self, fh, chunk_size) -> int: ...

    async def _encode_gen(self, conn: Connection) -> tuple[BytesAsyncGen, int]: ...

    async def send(self, conn: Connection) -> None: ...

    async def _write_data_to_stream(self, conn: Connection, data: BytesAsyncGen, *_, compression: int) -> None: ...

    async def _async_gen(self, gen: BytesAnyGen, chunk_size: int) -> AsyncIterator[bytes]: ...

    def __repr__(self) -> str: ...


class InputAction(BasicAction):
    @dataclass
    class Head:
        message_id: int
        data_type: int
        compression: int
        data_len: int

    @classmethod
    async def init(cls, conn: Connection) -> 'InputAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'InputAction.Head': ...

    async def handle(self) -> None: ...

    async def send(self, conn: Connection) -> None: ...

    async def reply(self, data: Any = None, data_type: int = None, compression: int = None, *,
                    headers: T_Headers = None, status: int = None) -> None: ...

    async def cancel(self) -> None: ...


class DownloadSpeedAction(BaseAction):
    @dataclass
    class Head:
        speed: int

    def __init__(self, speed: int):
        super().__init__()
        self.speed: int = speed

    @classmethod
    async def init(cls, conn: Connection) -> 'DownloadSpeedAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'DownloadSpeedAction.Head': ...

    async def handle(self) -> None: ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class CancelInputAction(BaseAction):
    @dataclass
    class Head:
        message_id: int

    @classmethod
    async def init(cls, conn: Connection) -> 'CancelInputAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'CancelInputAction.Head': ...

    async def handle(self) -> None: ...

    async def send(self, conn: Connection) -> None: ...


class PingAction(BaseAction):
    @dataclass
    class Head:
        send_time: int

    def __init__(self, send_time: int = None):
        super().__init__()
        self.recv_time: int = time_ns() // 1000000
        self.send_time: int = send_time or self.recv_time

    @classmethod
    async def init(cls, conn: Connection) -> 'PingAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'PingAction.Head': ...

    async def handle(self) -> None: ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...
