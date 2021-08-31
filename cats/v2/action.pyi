import asyncio
from logging import getLogger
from pathlib import Path
from time import time_ns
from typing import AsyncIterator, Type

import struct_model

from cats.types import BytesAnyGen, BytesAsyncGen, Headers, T_Headers
from cats.v2.connection import Connection

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
                 timeout: float | int = None):
        self.timer: asyncio.Task | None
        self.future: asyncio.Future = future
        self.conn: Connection = conn
        self.message_id: int = message_id
        self.bypass_count: bool = bypass_count
        if timeout:
            self.timer = asyncio.get_event_loop().call_later(timeout, self.cancel)

    def done(self, result) -> None: ...

    def cancel(self) -> None: ...


class BaseAction(dict):
    __slots__ = ('data', 'headers', 'message_id', 'conn')
    __registry__: dict[bytes, Type['BaseAction']] = {}
    HEADER_SEPARATOR = b'\x00\x00'

    type_id: bytes
    Head: type
    status: property | int
    offset: property | int

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
    def get_class_by_type_id(cls, type_id: bytes) -> Type['BaseAction'] | None: ...

    async def ask(self, data=None, data_type: int = None, compression: int = None, *,
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
    __slots__ = ('data_len', 'data_type', 'compression', 'encoded')

    def __init__(self, data=None, *, headers: T_Headers = None, status: int = None,
                 message_id: int = None, data_len: int = None, data_type: int = None, compression: int = None,
                 encoded: int = None):
        self.data_len: int | None = data_len
        self.data_type: int | None = data_type
        self.compression: int | None = compression
        self.encoded: int | None = encoded
        super().__init__(data, headers=headers, status=status, message_id=message_id)

    async def recv_data(self) -> None: ...

    async def _recv_small_data(self) -> None: ...

    async def _recv_large_data(self) -> None: ...

    async def _recv_chunk(self, left: int) -> (bytes, int): ...

    async def _encode(self) -> tuple[Path | bytes, int, int, int]: ...

    async def _write_data_to_stream(self, conn: Connection, data: Path | bytes,
                                    data_len: int, data_type: int, compression: int) -> None: ...

    def __repr__(self) -> str: ...


class Action(BasicAction):
    class Head(struct_model.StructModel):
        handler_id: struct_model.uInt2
        message_id: struct_model.uInt2
        send_time: struct_model.uInt8
        data_type: struct_model.uInt1
        compression: struct_model.uInt1
        data_len: struct_model.uInt4

    __slots__ = ('handler_id', 'send_time')

    def __init__(self, data=None, *, headers: T_Headers = None, status: int = None, message_id: int = None,
                 handler_id: int = None, data_len: int = None, data_type: int = None, compression: int = None,
                 send_time: float = None, encoded: int = None):
        self.handler_id: int | None = handler_id
        self.send_time = send_time or (time_ns() // 1000000)
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         data_len=data_len, data_type=data_type, compression=compression, encoded=encoded)

    @classmethod
    async def init(cls, conn: Connection) -> 'Action': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'Action.Head': ...

    async def send(self, conn: Connection) -> None: ...

    def __repr__(self) -> str: ...


class StreamAction(Action):
    class Head(struct_model.StructModel):
        handler_id: struct_model.uInt2
        message_id: struct_model.uInt2
        send_time: struct_model.uInt8
        data_type: struct_model.uInt1
        compression: struct_model.uInt1

    def __init__(self, data=None, *, headers: T_Headers = None, status: int = None, message_id: int = None,
                 handler_id: int = None, data_type: int = None, compression: int = None,
                 send_time: float = None):
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         handler_id=handler_id, data_type=data_type, compression=compression,
                         send_time=send_time)

    @classmethod
    async def init(cls, conn: Connection) -> 'StreamAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'StreamAction.Head': ...

    async def recv_data(self) -> None: ...

    async def _recv_large_chunk(self, fh, chunk_size) -> int: ...

    async def _recv_small_chunk(self, fh, chunk_size) -> int: ...

    async def _encode_gen(self, conn: Connection) -> tuple[BytesAsyncGen, int]: ...

    async def send(self, conn: Connection) -> None: ...

    async def _write_data_to_stream(self, conn: Connection, data: BytesAsyncGen, *_, compression: int) -> None: ...

    async def _async_gen(self, gen: BytesAnyGen, chunk_size: int) -> AsyncIterator[bytes]: ...

    def __repr__(self) -> str: ...


class InputAction(BasicAction):
    class Head(struct_model.StructModel):
        message_id: struct_model.uInt2
        data_type: struct_model.uInt1
        compression: struct_model.uInt1
        data_len: struct_model.uInt4

    @classmethod
    async def init(cls, conn: Connection) -> 'InputAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'InputAction.Head': ...

    async def send(self, conn: Connection) -> None: ...

    async def reply(self, data=None, data_type: int = None, compression: int = None, *,
                    headers: T_Headers = None, status: int = None) -> Action | None: ...

    async def cancel(self) -> Action | None: ...


class DownloadSpeedAction(BaseAction):
    class Head(struct_model.StructModel):
        speed: struct_model.uInt4

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
    class Head(struct_model.StructModel):
        message_id: struct_model.uInt2

    @classmethod
    async def init(cls, conn: Connection) -> 'CancelInputAction': ...

    @classmethod
    async def _recv_head(cls, conn: Connection) -> 'CancelInputAction.Head': ...

    async def send(self, conn: Connection) -> None: ...


class PingAction(BaseAction):
    class Head(struct_model.StructModel):
        send_time: struct_model.uInt8

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
