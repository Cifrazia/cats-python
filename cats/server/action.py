import asyncio
import math
from dataclasses import dataclass
from functools import partial
from io import BytesIO
from logging import getLogger
from pathlib import Path
from struct import Struct
from time import time_ns
from typing import NamedTuple, Type

from sentry_sdk import capture_exception

from cats.codecs import Codec, T_FILE, T_JSON
from cats.compression import Compressor
from cats.errors import MalformedDataError, ProtocolError
from cats.struct import O_NETWORK, uInt1, uInt2, uInt4, uInt8
from cats.types import Headers
from cats.utils import Delay, bytes2hex, filter_json, format_amount, int2hex, tmp_file

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
debug = logging.debug

MAX_IN_MEMORY = 1 << 24
MAX_CHUNK_READ = 1 << 20
PROPOSAL_PLACEHOLDER = bytes(5000)

to_uint = partial(int.to_bytes, byteorder='big', signed=False)
as_uint = partial(int.from_bytes, byteorder='big', signed=False)


class Input:
    __slots__ = ('future', 'conn', 'message_id', 'bypass_count', 'timer')

    def __init__(self,
                 future,
                 conn,
                 message_id,
                 bypass_count=False,
                 timeout=None):
        self.timer = None
        self.future = future
        self.conn = conn
        self.message_id = message_id
        self.bypass_count = bypass_count
        if timeout:
            self.timer = asyncio.get_event_loop().call_later(timeout, self.cancel)

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        if not self.future.done():
            self.future.cancel()
        self.conn.input_deq.pop(self.message_id, None)


class BaseAction(dict):
    __slots__ = ('data', 'headers', 'message_id', 'conn')
    __registry__ = {}
    HEADER_SEPARATOR = b'\x00\x00'

    type_id: bytes
    head_struct: Struct
    head_tuple: Type[NamedTuple]

    def __init__(self, data=None, *, headers=None, status=None,
                 message_id=None):
        assert type(self) is not BaseAction, 'Creation of BaseAction instances are prohibited'

        if headers is not None and not isinstance(headers, dict):
            raise MalformedDataError('Invalid Headers provided')

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
    def status(self):
        return self.headers.get('Status', 200)

    @status.setter
    def status(self, value=None):
        if value is None:
            value = 200
        elif not isinstance(value, int):
            raise MalformedDataError('Invalid status type')
        self.headers['Status'] = value

    @status.deleter
    def status(self):
        self.headers['Status'] = 200

    @property
    def offset(self) -> int:
        return self.headers.get('Offset', 0)

    @offset.setter
    def offset(self, value: int = None):
        if value is None:
            value = 0
        elif not isinstance(value, int):
            raise MalformedDataError('Invalid offset type')
        self.headers['Offset'] = value

    @offset.deleter
    def offset(self):
        self.headers['Offset'] = 0

    @classmethod
    def get_class_by_type_id(cls, type_id):
        return cls.__registry__.get(type_id)

    async def ask(self, data=None, data_type=None, compression=None, *,
                  headers=None, status=None,
                  bypass_limit=False, bypass_count=False,
                  timeout=None):
        if not self.conn:
            raise ValueError('Connection is not set')
        fut = asyncio.Future()
        timeout = self.conn.app.input_timeout if timeout is None else timeout

        if not bypass_limit:
            amount = sum(not i.bypass_count for i in self.conn.input_deq.values())
            if amount > self.conn.app.INPUT_LIMIT:
                k = min(self.conn.input_deq.keys())
                self.conn.input_deq[k].cancel()

        inp = Input(fut, self.conn, self.message_id, bypass_count, timeout)
        if self.message_id in self.conn.input_deq:
            raise ProtocolError(f'Input query with MID {self.message_id} already exists')

        self.conn.input_deq[self.message_id] = inp
        action = InputAction(data, headers=headers, status=status, message_id=self.message_id,
                             data_type=data_type, compression=compression)
        await action.send(self.conn)
        return await fut

    @classmethod
    async def init(cls, conn):
        raise NotImplementedError

    @classmethod
    async def _recv_head(cls, conn):
        raise NotImplementedError

    async def dump_data(self, size: int) -> None:
        while size > 0:
            size -= len(await self.conn.stream.read_bytes(min(size, MAX_CHUNK_READ), partial=True))
        if fut := self.conn.recv_fut:
            fut.set_result(None)

    async def handle(self):
        raise NotImplementedError

    async def send(self, conn):
        raise NotImplementedError


class BasicAction(BaseAction, abstract=True):
    __slots__ = ('data_len', 'data_type', 'compression', 'encoded')

    def __init__(self, data=None, *, headers=None, status=None,
                 message_id=None, data_len=None, data_type=None, compression=None, encoded=None):
        self.data_len = data_len
        self.data_type = data_type
        self.compression = compression
        self.encoded = encoded
        super().__init__(data, headers=headers, status=status, message_id=message_id)

    @classmethod
    async def init(cls, conn):
        raise NotImplementedError

    @classmethod
    async def _recv_head(cls, conn):
        raise NotImplementedError

    async def handle(self):
        raise NotImplementedError

    async def send(self, conn):
        raise NotImplementedError

    async def recv_data(self):
        if self.data_len > MAX_IN_MEMORY:
            if self.data_type != T_FILE:
                raise ProtocolError(f'Attempted to send message larger than '
                                    f'{format_amount(MAX_IN_MEMORY)}')
            await self._recv_large_data()
        else:
            await self._recv_small_data()

        if fut := self.conn.recv_fut:
            fut.set_result(None)

    async def _recv_small_data(self):
        left = self.data_len
        buff = bytearray()
        while left > 0:
            chunk, left = await self._recv_chunk(left)
            buff.extend(chunk)

        buff = await Compressor.decompress(buff, self.headers, compression=self.compression)
        self.data = await Codec.decode(buff, self.data_type, self.headers)
        if self.data_type == T_JSON:
            debug(f'[RECV {self.conn.address}] [{int2hex(self.message_id):<4}] <- {filter_json(self.data)}')

    async def _recv_large_data(self):
        left = self.data_len
        src, dst = tmp_file(), tmp_file()

        try:
            with src.open('wb') as fh:
                while left > 0:
                    chunk, left = await self._recv_chunk(left)
                    fh.write(chunk)

            await Compressor.decompress_file(src, dst, self.headers, compression=self.compression)
            self.data = await Codec.decode(dst, self.data_type, self.headers)
        except Exception:
            dst.unlink(missing_ok=True)
            raise
        finally:
            src.unlink(missing_ok=True)

    async def _recv_chunk(self, left):
        chunk = await self.conn.stream.read_bytes(min(left, MAX_CHUNK_READ), partial=True)
        debug(f'[RECV {self.conn.address}] [{int2hex(self.message_id):<4}] <- {bytes2hex(chunk[:64])}...')
        self.conn.reset_idle_timer()
        left -= len(chunk)
        return chunk, left

    async def _encode(self):
        if self.encoded is None:
            data, data_type = await Codec.encode(self.data, self.headers, self.offset)
        else:
            data = self.data
            data_type = self.encoded
        if isinstance(data, Path):
            data, buff = tmp_file(), data
            compression = await Compressor.compress_file(buff, data, self.headers, self.compression)
            data_len = data.stat().st_size
        else:
            data, compression = await Compressor.compress(data, self.headers, self.compression)
            data_len = len(data)
        return data, data_len, data_type, compression

    async def _write_data_to_stream(self, conn, data, data_len, data_type, compression):
        if isinstance(data, Path):
            fh = data.open('rb')
            left = data.stat().st_size
        else:
            fh = BytesIO(data)
            left = len(data)

        try:
            max_chunk_size = min(MAX_IN_MEMORY, conn.download_speed) or MAX_IN_MEMORY
            with Delay(conn.download_speed) as delay:
                while left > 0:
                    size = min(left, max_chunk_size)
                    chunk = fh.read(size)
                    left -= size
                    await delay(size)
                    conn.reset_idle_timer()
                    debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> {bytes2hex(chunk[:64])}...')
                    await conn.stream.write(chunk)
        finally:
            fh.close()
            if data_type == T_JSON:
                debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> {filter_json(self.data)}')


class Action(BasicAction):
    __slots__ = ('handler_id', 'send_time')

    type_id = b'\x00'
    head_struct = Struct(f'{O_NETWORK}2{uInt2}{uInt8}2{uInt1}{uInt4}')

    @dataclass
    class Head:
        handler_id: int
        message_id: int
        send_time: int
        data_type: int
        compression: int
        data_len: int

    def __init__(self, data=None, *, headers=None, status=None, message_id=None,
                 handler_id=None, data_len=None, data_type=None, compression=None,
                 send_time=None, encoded=None):
        assert compression is None or isinstance(compression, int), 'Invalid compression type'
        assert data_type is None or isinstance(data_type, int), 'Invalid data type provided'

        self.handler_id = handler_id
        self.send_time = send_time or (time_ns() // 1000000)
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         data_len=data_len, data_type=data_type, compression=compression, encoded=encoded)

    @classmethod
    async def init(cls, conn):
        conn.reset_idle_timer()
        head = await cls._recv_head(conn)

        headers = await conn.stream.read_until(cls.HEADER_SEPARATOR, head.data_len)
        head.data_len -= len(headers)
        headers = Headers.decode(headers[:-2])
        debug(f'[RECV {conn.address}] [{int2hex(head.message_id):<4}] <- HEADERS {headers}')
        conn.reset_idle_timer()

        inst = cls(**vars(head), headers=headers)
        inst.conn = conn
        return inst

    async def handle(self):
        with self.conn.preserve_message_id(self.message_id):
            handler = self.conn.dispatch(self.handler_id)
            fn = handler(self)
            for middleware in self.conn.app.middleware:
                fn = partial(middleware, fn)

            try:
                result = await asyncio.shield(fn())
                if result is not None:
                    if not isinstance(result, Action):
                        raise ProtocolError('Returned invalid response')

                    result.handler_id = self.handler_id
                    result.message_id = self.message_id
                    result.offset = self.offset
                    await result.send(self.conn)
            except self.conn.IGNORE_ERRORS:
                raise
            except Exception as err:
                capture_exception(err, scope=self.conn.scope)
                raise

    @classmethod
    async def _recv_head(cls, conn):
        conn.reset_idle_timer()
        buff = await conn.stream.read_bytes(cls.head_struct.size)
        head = cls.Head(*cls.head_struct.unpack(buff))
        debug(f'[RECV {conn.address}] Request  '
              f'H: {int2hex(head.handler_id):<4} '
              f'M: {int2hex(head.message_id):<4} '
              f'L: {format_amount(head.data_len):<8}'
              f'T: {Codec.codecs[head.data_type].type_name:<8} '
              f'C: {Compressor.compressors[head.compression].type_name:<8}')
        return head

    async def send(self, conn):
        data, data_len, data_type, compression = await self._encode()

        try:
            message_headers = self.headers.encode() + self.HEADER_SEPARATOR

            _data_len = data_len + len(message_headers)
            header = self.type_id + self.head_struct.pack(
                self.handler_id,
                self.message_id,
                time_ns() // 1000000,
                data_type,
                compression,
                _data_len
            ) + message_headers

            async with conn.lock_write():
                conn.reset_idle_timer()
                await conn.stream.write(header)
                debug(f'[SEND {conn.address}] Response '
                      f'H: {int2hex(self.handler_id):<4} '
                      f'M: {int2hex(self.message_id):<4} '
                      f'L: {format_amount(_data_len):<8}'
                      f'T: {Codec.codecs[data_type].type_name:<8} '
                      f'C: {Compressor.compressors[compression].type_name:<8} ')
                debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> HEADERS {self.headers}')
                await self._write_data_to_stream(conn, data, data_len, data_type, compression)
        finally:
            if isinstance(data, Path):
                data.unlink(missing_ok=True)


class StreamAction(Action):
    type_id = b'\x01'
    head_struct = Struct(f'{O_NETWORK}2{uInt2}{uInt8}2{uInt1}')

    @dataclass
    class Head:
        handler_id: int
        message_id: int
        send_time: int
        data_type: int
        compression: int

    def __init__(self, data=None, *, headers=None, status=None, message_id=None,
                 handler_id=None, data_type=None, compression=None,
                 send_time=None):
        super().__init__(data, headers=headers, status=status, message_id=message_id,
                         handler_id=handler_id, data_type=data_type, compression=compression,
                         send_time=send_time)

    @classmethod
    async def init(cls, conn):
        head = await cls._recv_head(conn)
        headers_size = as_uint(await conn.stream.read_bytes(4))
        headers = Headers.decode(await conn.stream.read_bytes(headers_size))
        conn.reset_idle_timer()
        debug(f'[RECV {conn.address}] [{int2hex(head.message_id):<4}] <- HEADERS {headers}')

        action = cls(**vars(head), headers=headers)
        action.conn = conn
        return action

    @classmethod
    async def _recv_head(cls, conn):
        conn.reset_idle_timer()
        buff = await conn.stream.read_bytes(cls.head_struct.size)
        head = cls.Head(*cls.head_struct.unpack(buff))
        debug(f'[RECV {conn.address}] Stream   '
              f'H: {int2hex(head.handler_id):<4} '
              f'M: {int2hex(head.message_id):<4} '
              f'T: {Codec.codecs[head.data_type].type_name:<8} '
              f'C: {Compressor.compressors[head.compression].type_name:<8} ')
        return head

    async def recv_data(self):
        data_len = 0
        buff = tmp_file()
        try:
            with buff.open('wb') as fh:
                while chunk_size := as_uint(await self.conn.stream.read_bytes(4)):
                    self.conn.reset_idle_timer()
                    if chunk_size > MAX_IN_MEMORY:
                        data_len += await self._recv_large_chunk(fh, chunk_size)
                    else:
                        data_len += await self._recv_small_chunk(fh, chunk_size)

            if data_len > self.conn.MAX_PLAIN_DATA_SIZE:
                if self.data_type != T_FILE:
                    raise ProtocolError(f'Attempted to send message larger than '
                                        f'{format_amount(self.conn.MAX_PLAIN_DATA_SIZE)}')
                decode = buff
            elif self.data_type != T_FILE:
                with buff.open('rb') as _fh:
                    decode = _fh.read()
            self.data = await Codec.decode(decode, self.data_type, self.headers)
            self.data_len = data_len
        finally:
            if fut := self.conn.recv_fut:
                fut.set_result(None)
            buff.unlink(missing_ok=True)

    async def _recv_large_chunk(self, fh, chunk_size):
        left = chunk_size
        part, dst = tmp_file(), tmp_file()
        try:
            with part.open('wb') as tmp:
                while left > 0:
                    chunk = await self.conn.stream.read_bytes(min(left, MAX_CHUNK_READ), partial=True)
                    debug(f'[RECV {self.conn.address}] [{int2hex(self.message_id):<4}] <- {bytes2hex(chunk[:64])}...')
                    left -= len(chunk)
                    tmp.write(chunk)
            await Compressor.decompress_file(part, dst, self.headers, compression=self.compression)
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
            chunk = await self.conn.stream.read_bytes(min(left, MAX_CHUNK_READ), partial=True)
            debug(f'[RECV {self.conn.address}] [{int2hex(self.message_id):<4}] <- {bytes2hex(chunk[:64])}...')
            left -= len(chunk)
            part += chunk
        part = await Compressor.decompress(part, self.headers, compression=self.compression)
        fh.write(part)
        return len(part)

    async def _encode_gen(self, conn):
        data = self.data
        compression = self.compression
        if compression is None:
            compression = await Compressor.propose_compression(PROPOSAL_PLACEHOLDER)

        assert hasattr(data, '__iter__') or hasattr(data, '__aiter__'), \
            'StreamResponse payload is not (Async)Generator[Bytes, None, None]'
        data = self._async_gen(data, conn.download_speed)
        return data, compression

    async def send(self, conn):
        data, compression = await self._encode_gen(conn)

        header = self.type_id + self.head_struct.pack(
            self.handler_id,
            self.message_id,
            time_ns() // 1000000,
            self.data_type,
            compression
        )
        message_headers = self.headers.encode()

        async with conn.lock_write():
            conn.reset_idle_timer()
            await conn.stream.write(header)
            await conn.stream.write(to_uint(len(message_headers), 4))
            await conn.stream.write(message_headers)
            debug(f'[SEND {conn.address}] Stream   '
                  f'H: {int2hex(self.handler_id):<4} '
                  f'M: {int2hex(self.message_id):<4} '
                  f'T: {Codec.codecs[self.data_type].type_name:<8} '
                  f'C: {Compressor.compressors[compression].type_name:<8} ')
            debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> HEADERS {self.headers}')
            await self._write_data_to_stream(conn, data, compression=compression)

    async def _write_data_to_stream(self, conn, data, *_, compression):
        offset = self.offset
        with Delay(conn.download_speed) as delay:
            async for chunk in data:
                if offset > 0:
                    offset -= (i := min(offset, len(chunk)))
                    chunk = chunk[i:]
                if not chunk:
                    continue
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise MalformedDataError('Provided data chunk is not binary')

                chunk, _ = await Compressor.compress(chunk, self.headers, compression)
                chunk_size = len(chunk)
                if chunk_size >= 1 << 32:
                    raise ProtocolError('Provided data chunk exceeded max chunk size')

                await delay(chunk_size + 4)
                conn.reset_idle_timer()
                await conn.stream.write(to_uint(chunk_size, 4))
                await conn.stream.write(chunk)
                debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> {bytes2hex(chunk[:64])}...')
        await conn.stream.write(b'\x00\x00\x00\x00')

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


class InputAction(BasicAction):
    type_id = b'\x02'
    head_struct = Struct(f'{O_NETWORK}{uInt2}2{uInt1}{uInt4}')

    @dataclass
    class Head:
        message_id: int
        data_type: int
        compression: int
        data_len: int

    @classmethod
    async def init(cls, conn):
        head = await cls._recv_head(conn)
        headers = await conn.stream.read_until(cls.HEADER_SEPARATOR, head.data_len)
        conn.reset_idle_timer()
        head.data_len -= len(headers)
        headers = Headers.decode(headers[:-2])
        debug(f'[RECV {conn.address}] [{int2hex(head.message_id):<4}] <- HEADERS {headers}')

        action = cls(**vars(head), headers=headers)
        action.conn = conn
        return action

    @classmethod
    async def _recv_head(cls, conn):
        conn.reset_idle_timer()
        buff = await conn.stream.read_bytes(cls.head_struct.size)
        head = cls.Head(*cls.head_struct.unpack(buff))
        debug(f'[RECV {conn.address}] Answer   '
              f'M: {int2hex(head.message_id):<4} '
              f'L: {format_amount(head.data_len):<8}'
              f'T: {Codec.codecs[head.data_type].type_name:<8} '
              f'C: {Compressor.compressors[head.compression].type_name:<8} ')
        return head

    async def handle(self):
        await self.recv_data()
        if inp := self.conn.input_deq.get(self.message_id, None):
            inp.future.set_result(self)
            inp.cancel()
        else:
            raise ProtocolError('Received answer but input does`t exists')

    async def send(self, conn):
        data, data_len, data_type, compression = await self._encode()
        try:
            message_headers = self.headers.encode() + self.HEADER_SEPARATOR
            _data_len = data_len + len(message_headers)
            header = self.type_id + self.head_struct.pack(
                self.message_id,
                data_type,
                compression,
                _data_len
            ) + message_headers

            async with conn.lock_write():
                conn.reset_idle_timer()
                await conn.stream.write(header)
                debug(f'[SEND {conn.address}] Input    '
                      f'M: {int2hex(self.message_id):<4} '
                      f'L: {format_amount(_data_len):<8}'
                      f'T: {Codec.codecs[data_type].type_name:<8} '
                      f'C: {Compressor.compressors[compression].type_name:<8} ')
                debug(f'[SEND {conn.address}] [{int2hex(self.message_id):<4}] -> HEADERS {self.headers}')
                await self._write_data_to_stream(conn, data, data_len, data_type, compression)
        finally:
            if isinstance(data, Path):
                data.unlink(missing_ok=True)

    async def reply(self, data=None, data_type=None, compression=None, *,
                    headers=None, status=None):
        action = InputAction(data, headers=headers, status=status, message_id=self.message_id,
                             data_type=data_type, compression=compression)
        action.offset = self.offset
        await action.send(self.conn)

    async def cancel(self):
        res = CancelInputAction(self.message_id)
        await res.send(self.conn)


class DownloadSpeedAction(BaseAction):
    type_id = b'\x05'
    head_struct = Struct(f'{O_NETWORK}{uInt4}')

    @dataclass
    class Head:
        speed: int

    def __init__(self, speed):
        super().__init__()
        self.speed = speed

    @classmethod
    async def init(cls, conn):
        conn.reset_idle_timer()
        buff = await conn.stream.read_bytes(cls.head_struct.size)
        head = cls.Head(*cls.head_struct.unpack(buff))
        debug(f'[RECV {conn.address}] SET Download speed: {format_amount(head.speed)}')
        action = cls(**vars(head))
        action.conn = conn
        return action

    async def handle(self):
        limit = self.speed
        if not limit or (1024 <= limit <= 33_554_432):
            self.conn.download_speed = limit
        else:
            raise ProtocolError('Unsupported download speed limit')
        await self.dump_data(0)

    async def send(self, conn):
        async with conn.lock_write():
            conn.reset_idle_timer()
            speed: int = self.data
            await conn.stream.write(self.type_id + to_uint(speed, 4))
            debug(f'[SEND {conn.address}] SET Download speed: {format_amount(speed)}')


class CancelInputAction(BaseAction):
    type_id = b'\x06'
    head_struct = Struct(f'{O_NETWORK}{uInt2}')

    @dataclass
    class Head:
        message_id: int

    @classmethod
    async def init(cls, conn):
        conn.reset_idle_timer()
        buff = await conn.stream.read_bytes(cls.head_struct.size)
        head = cls.Head(*cls.head_struct.unpack(buff))
        debug(f'[RECV {conn.address}] CANCEL Input M: {int2hex(head.message_id):<4}')
        action = cls(**vars(head))
        action.conn = conn
        return action

    async def handle(self):
        if self.message_id in self.conn.input_deq:
            self.conn.input_deq[self.message_id].cancel()
        await self.dump_data(0)

    async def send(self, conn):
        async with conn.lock_write():
            conn.reset_idle_timer()
            message_id: int = self.data
            await conn.stream.write(self.type_id + to_uint(message_id, 2))
            debug(f'[SEND {conn.address}] CANCEL Input M: {message_id}')


class PingAction(BaseAction):
    type_id = b'\xFF'
    head_struct = Struct(f'{O_NETWORK}{uInt8}')

    @dataclass
    class Head:
        send_time: int

    def __init__(self, send_time=None):
        super().__init__()
        self.recv_time = time_ns() // 1000000
        self.send_time = send_time or self.recv_time

    @classmethod
    async def init(cls, conn):
        conn.reset_idle_timer()
        buff = await conn.stream.read_bytes(cls.head_struct.size)
        head = cls.Head(*cls.head_struct.unpack(buff))
        debug(f'[PING {conn.address}] {head.send_time}')

        action = cls(**vars(head))
        action.conn = conn
        return action

    async def handle(self):
        debug(f'Ping {self.send_time} [-] {self.recv_time}')
        await self.send(self.conn)
        await self.dump_data(0)

    async def send(self, conn):
        async with conn.lock_write():
            conn.reset_idle_timer()
            now = time_ns() // 1000000
            await conn.stream.write(self.type_id + to_uint(now, 8))
            debug(f'[SEND {conn.address}] PONG {now}')
