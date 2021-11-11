from pathlib import Path
from typing import Generator, Iterable

from struct_model import StructModel, uInt1, uInt2, uInt4

from cats.v2 import format_amount, int2hex
from cats.v2.actions.base import BaseAction
from cats.v2.errors import InterfaceViolation

__all__ = [
    'InputAction',
    'CancelInputAction',
]


class InputAction(BaseAction):
    type_id = 0x02
    type_name = 'Input'

    def __init__(self, meta: 'BaseAction.Meta' = None):
        super().__init__(meta)

    class Head(StructModel):
        message_id: uInt2
        data_type: uInt1
        compressor: uInt1
        data_len: uInt4

    @classmethod
    def from_buffer(cls) -> Generator[bytes, int, 'BaseAction']:
        buff = yield cls.Head.struct.size
        head: cls.Head = cls.Head.unpack(buff)
        left = head.data_len
        while left > 0:
            buff = yield cls.MAX_CHUNK_READ

    def __iter__(self) -> Iterable[bytes]:
        pass

    async def prepare(self) -> None:
        pass

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        raise InterfaceViolation('Cannot store "InputAction"')

    @classmethod
    async def _recv_head(cls, conn):
        buff = await conn.read(cls.Head.struct.size)
        head = cls.Head.unpack(buff)
        conn.debug(f'[RECV {conn.address}] Answer   '
                   f'M: {int2hex(head.message_id):<4} '
                   f'L: {format_amount(head.data_len):<8}'
                   f'T: {conn.conf.codecs.registry[head.data_type].type_name:<8} '
                   f'C: {conn.conf.compressors.registry[head.compressor].type_name:<8} ')
        return head

    async def send(self, conn) -> None:
        self.conn = conn
        await self.prepare()
        compressor = self.conf.compressors.find_strict(self.compressor)

        message_headers = self.headers.encode() + self.HEADER_SEPARATOR
        _data_len = self.data_len + len(message_headers)
        header = self.type_id + self.Head(
            self.message_id,
            self.data_type,
            compressor.type_id,
            _data_len
        ).pack() + message_headers

        async with conn.lock_write:
            await conn.write(header)
            conn.debug(f'[SEND {conn.address}] Input    '
                       f'M: {int2hex(self.message_id):<4} '
                       f'L: {format_amount(_data_len):<8}'
                       f'T: {self.conf.codecs.registry[self.data_type].type_name:<8} '
                       f'C: {compressor.type_name:<8} ')
            conn.debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> HEADERS {self.headers}')
            await self._write_data_to_stream()

    async def reply(self, data=None, data_type=None, compressor=None, *,
                    headers=None, status=None) -> ActionLike | None:
        action = InputAction(data, headers=headers, status=status, message_id=self.message_id,
                             data_type=data_type, compressor=compressor)
        action.offset = self.skip
        await action.send(self.conn)
        return await self.conn.recv(self.message_id)  # noqa

    async def cancel(self) -> ActionLike | None:
        res = CancelInputAction(self.message_id)
        await res.send(self.conn)
        return await self.conn.recv(self.message_id)  # noqa


class CancelInputAction(BaseAction):
    __slots__ = ('message_id',)
    type_id = 0x06
    type_name = 'CancelInput'

    class Head(StructModel):
        message_id: uInt2

    def __init__(self, message_id: int):
        super().__init__()
        self.message_id = message_id

    @classmethod
    def from_buffer(cls) -> Generator[bytes, int, 'BaseAction']:
        buff = yield cls.Head.struct.size
        head: cls.Head = cls.Head.unpack(buff)
        action = cls(**head.dict())
        return action

    def __iter__(self) -> Iterable[bytes]:
        yield self.type_byte
        yield self.Head(message_id=self.message_id).pack()

    async def prepare(self) -> None:
        pass

    async def store(self, filename: str | Path = None, ttl: int = 0) -> Path:
        raise InterfaceViolation('Cannot store "CancelInputAction"')

    def __repr__(self) -> str:
        return f'{type(self).__name__}(message_id={self.message_id})'
