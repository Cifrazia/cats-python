from pathlib import Path
from time import time_ns
from typing import Any, Generator, Iterable

from struct_model import StructModel, uInt1, uInt2, uInt4, uInt8

from cats.v2.actions import BaseAction
from cats.v2.errors import ProtocolViolation
from cats.v2.headers import Headers, T_Headers


class Action(BaseAction):
    __slots__ = (
        'handler_id',
        'message_id',
        'headers',
        'data',
        'data_len',
        'data_type',
        'send_time',
        'compression',
        'encoded',
    )
    type_id = 0x00
    type_name = 'Action'
    HEAD_SEPARATOR = b'\x00\x00'

    class Head(StructModel):
        handler_id: uInt2
        message_id: uInt2
        send_time: uInt8
        data_type: uInt1
        compression: uInt1
        data_len: uInt4

    def __init__(
        self,
        handler_id: int = None,
        message_id: int = None,
        status: int = None,
        headers: T_Headers = None,
        data: Any = None,
        data_len: int = None,
        data_type: int = None,
        compression: int = None,
        encoded: int = None,
        send_time: int = None,
        meta: 'BaseAction.Meta' = None,
    ):
        assert compression is None or isinstance(compression, int), 'Invalid compression type'
        assert data_type is None or isinstance(data_type, int), 'Invalid data type provided'

        self.handler_id: int | None = handler_id
        self.message_id: int | None = message_id
        self.send_time: int = send_time or (time_ns() // 1000_000)
        self.data_len: int | None = data_len
        self.data_type: int | None = data_type
        self.compression: int | None = compression
        self.encoded: int | None = encoded
        self.data: Any = data
        self.headers: Headers = Headers(headers or {})
        self.status: int = status or self.status
        super().__init__(meta)

    @property
    def status(self):
        return self.headers.get('Status', 200)

    @status.setter
    def status(self, value=None):
        if value is None:
            value = 200
        elif not isinstance(value, int):
            raise TypeError('Invalid status type')
        self.headers['Status'] = value

    @status.deleter
    def status(self):
        self.headers['Status'] = 200

    @classmethod
    def from_buffer(cls) -> Generator[bytes, int | bytes, 'Action']:
        buff = yield cls.Head.struct.size
        head: cls.Head = cls.Head.unpack(buff)
        headers = yield cls.HEAD_SEPARATOR
        if len(headers) > head.data_len:
            raise ProtocolViolation(f'Received headers exceeds data length. Terminating connection')

        head.data_len -= len(headers)
        headers = Headers.decode(headers[:-2])
        action = cls(**vars(head), headers=headers)
        return action

    def __iter__(self) -> Iterable[bytes]:
        pass

    async def prepare(self) -> None:
        if self.compiled:
            return

        await self._encode()

    async def _encode(self):

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        pass
