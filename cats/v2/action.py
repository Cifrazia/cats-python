import asyncio
from io import BytesIO
from pathlib import Path
from struct import Struct
from time import time_ns
from typing import NamedTuple, TypeAlias, TypeVar

import math
from struct_model import *

from cats.v2.codecs import FileCodec, SchemeCodec
from cats.v2.errors import InputCancelled, InterfaceViolation, MalformedData, MalformedHeaders, ProtocolViolation
from cats.v2.headers import Header, Headers
from cats.v2.types import Bytes
from cats.v2.utils import Delay, bytes2hex, filter_json, format_amount, from_uint, int2hex, tmp_file, to_uint

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

MAX_IN_MEMORY = 1 << 24
MAX_CHUNK_READ = 1 << 20

ActionLike: TypeAlias = TypeVar('ActionLike', bound='Action')


class Input:
    __slots__ = ('future', 'conn', 'message_id', 'bypass_count', 'timer')

    def __init__(self,
                 future,
                 conn,
                 message_id,
                 bypass_count=False,
                 timeout: int | float = None):
        self.timer = None
        self.future = future
        self.conn = conn
        self.message_id = message_id
        self.bypass_count = bypass_count
        if timeout:
            self.timer = asyncio.get_running_loop().call_later(timeout, self.cancel)

    def done(self, result):
        self.future.set_result(result)
        self.cancel()

    def cancel(self):
        if self.timer is not None:
            if not self.timer.cancelled():
                self.timer.cancel()
            self.timer = None
        if not self.future.done():
            self.future.cancel()
        self.conn.input_pool.pop(self.message_id, None)


class BaseAction(dict):
    __slots__ = ('data', 'headers', 'message_id', 'conn')
    __registry__ = {}
    HEADER_SEPARATOR = b'\x00\x00'

    type_id: bytes
    head_struct: Struct
    head_tuple: type[NamedTuple]

    def __init__(self, data=None, *, headers=None, status=None, message_id=None):
        assert type(self) is not BaseAction, 'Creation of BaseAction instances are prohibited'

        if headers is not None and not isinstance(headers, dict):
            raise MalformedHeaders('Invalid Headers provided', headers=headers)

        self.data = data
        self.headers = Headers(headers or {})
        self.status = status or self.status
        self.message_id = message_id
        self.conn = None
        super().__init__()

    def __init_subclass__(cls, *, abstract=False):
        if abstract:
            return
        assert cls.type_id not in cls.__registry__, f'ActionType with ID {cls.type_id} already assigned'
        cls.__registry__[cls.type_id] = cls

    @property
    def conf(self):
        return self.conn.conf

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

    @property
    def offset(self) -> int:
        return self.headers.get(Header.offset, 0)

    @offset.setter
    def offset(self, value: int = None):
        if value is None:
            value = 0
        elif not isinstance(value, int):
            raise TypeError('Invalid offset type')
        self.headers[Header.offset] = value

    @offset.deleter
    def offset(self):
        self.headers[Header.offset] = 0

    @property
    def skip(self) -> int:
        return self.headers.get(Header.skip, 0)

    @skip.setter
    def skip(self, value: int = None):
        if value is None:
            value = 0
        elif not isinstance(value, int):
            raise TypeError('Invalid skip type')
        self.headers[Header.skip] = value

    @skip.deleter
    def skip(self):
        self.headers[Header.skip] = 0

    @classmethod
    def get_type_by_id(cls, type_id):
        return cls.__registry__.get(type_id)

    async def ask(self, data=None, data_type=None, compressor=None, *,
                  headers=None, status=None,
                  bypass_limit=False, bypass_count=False,
                  timeout=None):
        if not self.conn:
            raise InterfaceViolation('Connection is not set')
        fut = asyncio.Future()
        timeout = self.conn.conf.input_timeout if timeout is None else timeout

        if not bypass_limit:
            amount = sum(not i.bypass_count for i in self.conn.input_pool.values())
            if amount > self.conn.conf.input_limit:
                k = min(self.conn.input_pool.keys())
                self.conn.input_pool[k].cancel()

        inp = Input(fut, self.conn, self.message_id, bypass_count, timeout)
        if self.message_id in self.conn.input_pool:
            raise ProtocolViolation(f'Input query with MID {self.message_id} already exists', conn=self.conn)

        self.conn.input_pool[self.message_id] = inp
        action = InputAction(data, headers=headers, status=status, message_id=self.message_id,
                             data_type=data_type, compressor=compressor)
        await action.send(self.conn)
        try:
            return await fut
        except (asyncio.TimeoutError, asyncio.CancelledError) as err:
            raise InputCancelled from err

    @classmethod
    async def init(cls, conn):
        raise NotImplementedError

    @classmethod
    async def _recv_head(cls, conn):
        raise NotImplementedError

    async def dump_data(self, size: int) -> None:
        while size > 0:
            size -= len(await self.conn.read(min(size, MAX_CHUNK_READ), partial=True))
        self.conn.lock_read.release()

    async def send(self, conn) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f'{type(self).__qualname__}(data={str(self.data)[:256]}, headers={self.headers}, ' \
               f'status={self.status}, message_id={self.message_id})'


class BasicAction(BaseAction, abstract=True):
    __slots__ = ('data_len', 'data_type', 'compressor', 'encoded', '_prepared')

    def __init__(self, data=None, *, headers=None, status=None,
                 message_id=None, data_len=None, data_type=None, compressor=None, encoded=None):
        self.data_len = data_len
        self.data_type = data_type
        self.compressor = compressor
        self.encoded = encoded
        self._prepared: bool = False
        super().__init__(data, headers=headers, status=status, message_id=message_id)

    @classmethod
    async def init(cls, conn):
        raise NotImplementedError

    @classmethod
    async def _recv_head(cls, conn):
        raise NotImplementedError

    async def send(self, conn) -> None:
        raise NotImplementedError

    async def recv_data(self):
        if self.data_len > MAX_IN_MEMORY:
            if FileCodec != self.data_type:
                raise ProtocolViolation(f'Attempted to send message larger than '
                                        f'{format_amount(MAX_IN_MEMORY)}', conn=self.conn)
            await self._recv_large_data()
        else:
            await self._recv_small_data()

        self.conn.lock_read.release()

    async def _recv_small_data(self):
        left = self.data_len
        buff = bytearray()
        while left > 0:
            chunk, left = await self._recv_chunk(left)
            buff.extend(chunk)

        buff = await self.conf.compressors.decompress(self.compressor, buff, self.headers, self.conn.options)
        self.data = await self.conf.codecs.decode(self.data_type, buff, self.headers, self.conn.options)
        if SchemeCodec == self.data_type:
            self.conn.debug(f'[RECV {self.conn.address}] [{int2hex(self.message_id):<4}] <- {filter_json(self.data)}')

    async def _recv_large_data(self):
        left = self.data_len
        src, dst = tmp_file(), tmp_file()

        try:
            with src.open('wb') as fh:
                while left > 0:
                    chunk, left = await self._recv_chunk(left)
                    fh.write(chunk)

            await self.conf.compressors.decompress_file(self.compressor, src, dst, self.headers, self.conn.options)
            self.data = await self.conf.codecs.decode(self.data_type, dst, self.headers, self.conn.options)
        except Exception:
            dst.unlink(missing_ok=True)
            raise
        finally:
            src.unlink(missing_ok=True)

    async def _recv_chunk(self, left):
        chunk = await self.conn.read(min(left, MAX_CHUNK_READ), partial=True)
        self.conn.debug(f'[RECV {self.conn.address}] [{int2hex(self.message_id):<4}] <- {bytes2hex(chunk[:64])}...')
        left -= len(chunk)
        return chunk, left

    async def prepare(self):
        if self._prepared:
            return
        await self._encode()
        data = self.data
        if isinstance(data, Path):
            data, buff = tmp_file(), data
            self.compressor = await self.conf.compressors.compress_file(buff, data, self.headers, self.conn.options)
            self.data = data
            self.data_len = data.stat().st_size
        else:
            data = data[self.offset:]
            self.data, self.compressor = await self.conf.compressors.compress(data, self.headers, self.conn.options)
            self.data_len = len(self.data)
        self._prepared = True

    async def _encode(self):
        if self.encoded is None:
            self.data, self.data_type = await self.conf.codecs.encode(self.data, self.headers, self.conn.options)
            self.encoded = self.data_type

    async def _write_data_to_stream(self):
        data = self.data
        conn = self.conn
        if isinstance(data, Path):
            fh = data.open('rb')
            left = data.stat().st_size
        else:
            fh = BytesIO(data)
            left = len(data)

        try:
            max_chunk_size = min(MAX_IN_MEMORY, conn.options.download_speed) or MAX_IN_MEMORY
            delay = Delay(conn.options.download_speed)
            while left > 0:
                size = min(left, max_chunk_size)
                chunk = fh.read(size)
                left -= size
                await delay(size)
                conn.debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> {bytes2hex(chunk[:64])}...')
                await conn.write(chunk)
        finally:
            fh.close()
            if SchemeCodec == self.data_type:
                conn.debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> {filter_json(self.data)}')

    def __repr__(self) -> str:
        return f'{type(self).__name__}(data={str(self.data)[:256]}, headers={self.headers}, ' \
               f'status={self.status}, message_id={self.message_id}, ' \
               f'data_len={self.data_len}, data_type={self.data_type}, ' \
               f'compressor={self.compressor}, encoded={self.encoded})'


class Action(BasicAction):
    __slots__ = ('handler_id', 'send_time')

    type_id = b'\x00'

    class Head(StructModel):
        handler_id: uInt2
        message_id: uInt2
        send_time: uInt8
        data_type: uInt1
        compressor: uInt1
        data_len: uInt4

    def __init__(self, data=None, *, headers=None, status=None, message_id=None,
                 handler_id=None, data_len=None, data_type=None, compressor=None,
                 send_time=None, encoded=None):
        self.handler_id = handler_id
        self.send_time = send_time or (time_ns() // 1000_000)
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         data_len=data_len, data_type=data_type, compressor=compressor, encoded=encoded)

    @classmethod
    async def init(cls, conn):
        head = await cls._recv_head(conn)
        headers = await conn.read_until(cls.HEADER_SEPARATOR, head.data_len)
        head.data_len -= len(headers)
        headers = Headers.decode(headers[:-2])
        conn.debug(f'[RECV {conn.address}] [{int2hex(head.message_id):<4}] <- HEADERS {headers}')

        action = cls(**vars(head), headers=headers)
        action.conn = conn
        return action

    @classmethod
    async def _recv_head(cls, conn):
        buff = await conn.read(cls.Head.struct.size)
        head: cls.Head = cls.Head.unpack(buff)
        conn.debug(f'[RECV {conn.address}] Request  '
                   f'H: {int2hex(head.handler_id):<4} '
                   f'M: {int2hex(head.message_id):<4} '
                   f'L: {format_amount(head.data_len):<8}'
                   f'T: {conn.conf.codecs.registry[head.data_type].type_name:<8} '
                   f'C: {conn.conf.compressors.registry[head.compressor].type_name:<8}')
        return head

    async def send(self, conn) -> None:
        self.conn = conn
        await self.prepare()
        compressor = self.conf.compressors.find_strict(self.compressor)

        message_headers = self.headers.encode() + self.HEADER_SEPARATOR

        _data_len = self.data_len + len(message_headers)
        header = self.type_id + self.Head(
            self.handler_id,
            self.message_id,
            time_ns() // 1000_000,
            self.data_type,
            compressor.type_id,
            _data_len
        ).pack() + message_headers

        async with conn.lock_write:
            await conn.write(header)
            conn.debug(f'[SEND {conn.address}] Response '
                       f'H: {int2hex(self.handler_id):<4} '
                       f'M: {int2hex(self.message_id):<4} '
                       f'L: {format_amount(_data_len):<8}'
                       f'T: {conn.conf.codecs.registry[self.data_type].type_name:<8} '
                       f'C: {compressor.type_name:<8} ')
            conn.debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> HEADERS {self.headers}')
            await self._write_data_to_stream()

    def __repr__(self) -> str:
        return f'{type(self).__name__}(data={str(self.data)[:256]}, headers={self.headers}, ' \
               f'status={self.status}, message_id={self.message_id}, ' \
               f'data_len={self.data_len}, data_type={self.data_type}, ' \
               f'compressor={self.compressor}, send_time={self.send_time}, encoded={self.encoded})'

    def __del__(self):
        if self._prepared and isinstance(self.data, Path):
            self.data.unlink(missing_ok=True)


class StreamAction(Action):
    type_id = b'\x01'

    class Head(StructModel):
        handler_id: uInt2
        message_id: uInt2
        send_time: uInt8
        data_type: uInt1
        compressor: uInt1

    def __init__(self, data=None, *, headers=None, status=None, message_id=None,
                 handler_id=None, data_type=None, compressor=None,
                 send_time=None):
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         handler_id=handler_id, data_type=data_type, compressor=compressor,
                         send_time=send_time)

    @classmethod
    async def init(cls, conn):
        head = await cls._recv_head(conn)
        headers_size = from_uint(await conn.read(4))
        headers = Headers.decode(await conn.read(headers_size))
        conn.debug(f'[RECV {conn.address}] [{int2hex(head.message_id):<4}] <- HEADERS {headers}')

        action = cls(**vars(head), headers=headers)
        action.conn = conn
        return action

    @classmethod
    async def _recv_head(cls, conn):
        buff = await conn.read(cls.Head.struct.size)
        head: cls.Head = cls.Head.unpack(buff)
        conn.debug(f'[RECV {conn.address}] Stream   '
                   f'H: {int2hex(head.handler_id):<4} '
                   f'M: {int2hex(head.message_id):<4} '
                   f'T: {conn.conf.codecs.registry[head.data_type].type_name:<8} '
                   f'C: {conn.conf.compressors.registry[head.compressor].type_name:<8} ')
        return head

    async def recv_data(self):
        data_len = 0
        buff = tmp_file()
        try:
            with buff.open('wb') as fh:
                while chunk_size := from_uint(await self.conn.read(4)):
                    if chunk_size > MAX_IN_MEMORY:
                        data_len += await self._recv_large_chunk(fh, chunk_size)
                    else:
                        data_len += await self._recv_small_chunk(fh, chunk_size)

            if data_len > self.conn.conf.max_plain_payload:
                if FileCodec != self.data_type:
                    raise ProtocolViolation(f'Attempted to send message larger than '
                                            f'{format_amount(self.conn.conf.max_plain_payload)}', conn=self.conn)
                decode = buff
            elif FileCodec != self.data_type:
                with buff.open('rb') as _fh:
                    decode = _fh.read()
            self.data = await self.conf.codecs.decode(self.data_type, decode, self.headers, self.conn.options)
            self.data_len = data_len
        finally:
            self.conn.lock_read.release()
            buff.unlink(missing_ok=True)

    async def _recv_large_chunk(self, fh, chunk_size):
        conn = self.conn
        left = chunk_size
        part, dst = tmp_file(), tmp_file()
        try:
            with part.open('wb') as tmp:
                while left > 0:
                    chunk = await conn.read(min(left, MAX_CHUNK_READ), partial=True)
                    conn.debug(f'[RECV {conn.address}] [{int2hex(self.message_id):<4}] <- {bytes2hex(chunk[:64])}...')
                    left -= len(chunk)
                    tmp.write(chunk)
            await self.conf.compressors.decompress_file(self.compressor, part, dst, self.headers, conn.options)
            data_len = dst.stat().st_size
            with dst.open('rb') as tmp:
                while i := tmp.read(MAX_IN_MEMORY):
                    fh.write(i)
            return data_len
        finally:
            part.unlink(missing_ok=True)
            dst.unlink(missing_ok=True)

    async def _recv_small_chunk(self, fh, chunk_size):
        left = chunk_size
        part = bytearray()
        while left > 0:
            chunk = await self.conn.read(min(left, MAX_CHUNK_READ), partial=True)
            self.conn.debug(f'[RECV {self.conn.address}] [{int2hex(self.message_id):<4}] <- {bytes2hex(chunk[:64])}...')
            left -= len(chunk)
            part += chunk
        part = await self.conf.compressors.decompress(self.compressor, part, self.headers, self.conn.options)
        fh.write(part)
        return len(part)

    async def prepare(self):
        if self._prepared:
            return True
        data = self.data

        assert hasattr(data, '__iter__') or hasattr(data, '__aiter__'), \
            'StreamResponse payload is not (Async)Generator[Bytes, None, None]'

        self.data = self._async_gen(data, self.conn.options.download_speed)

    async def send(self, conn) -> None:
        self.conn = conn
        await self.prepare()
        compressor = self.conf.compressors.find_strict(self.compressor)
        header = self.type_id + self.Head(
            self.handler_id,
            self.message_id,
            time_ns() // 1000_000,
            self.data_type,
            compressor.type_id
        ).pack()
        message_headers = self.headers.encode()

        async with conn.lock_write:
            await conn.write(header + to_uint(len(message_headers), 4) + message_headers)
            conn.debug(f'[SEND {conn.address}] Stream   '
                       f'H: {int2hex(self.handler_id):<4} '
                       f'M: {int2hex(self.message_id):<4} '
                       f'T: {self.conf.codecs.registry[self.data_type].type_name:<8} '
                       f'C: {compressor.type_name:<8} ')
            conn.debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> HEADERS {self.headers}')
            await self._write_data_to_stream()

    async def _write_data_to_stream(self):
        conn = self.conn
        offset = self.offset
        delay = Delay(self.conn.options.download_speed)
        compressor = self.conf.compressors.find_strict(self.compressor)

        async for chunk in self.data:
            if offset > 0:
                offset -= (i := min(offset, len(chunk)))
                chunk = chunk[i:]
            if not chunk:
                continue
            if not isinstance(chunk, Bytes):
                raise MalformedData('Provided data chunk is not binary', data=self.data)

            chunk = await compressor.compress(chunk, self.headers, self.conn.options)
            chunk_size = len(chunk)
            if chunk_size >= 1 << 32:
                raise MalformedData('Provided data chunk exceeded max chunk size', data=self.data)

            await delay(chunk_size + 4)
            await conn.write(to_uint(chunk_size, 4))
            await conn.write(chunk)
            conn.debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> {bytes2hex(chunk[:64])}...')
        await conn.write(b'\x00\x00\x00\x00')

    async def _async_gen(self, gen, chunk_size):
        size = max(chunk_size, MAX_IN_MEMORY) or MAX_IN_MEMORY
        if hasattr(gen, '__iter__'):
            for item in gen:
                for i in range(math.ceil(len(item) / size)):
                    yield item[i * size:]
        else:
            async for item in gen:
                for i in range(math.ceil(len(item) / size)):
                    yield item[i * size:]

    def __repr__(self) -> str:
        return f'{type(self).__qualname__}(data={str(self.data)[:256]}, headers={self.headers}, ' \
               f'status={self.status}, message_id={self.message_id}, ' \
               f'data_type={self.data_type}, compressor={self.compressor}'
