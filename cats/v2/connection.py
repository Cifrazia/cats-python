import asyncio
from contextlib import asynccontextmanager
from logging import Logger
from typing import TypeVar

import sentry_sdk
from tornado.iostream import IOStream

from cats.errors import ProtocolError
from cats.identity import Identity
from cats.types import BytesAnyGen
from cats.v2 import C_NONE, Compressor
from cats.v2.action import BaseAction, Input
from cats.v2.config import Config

try:
    from uvloop.loop import TimerHandle as UVTimerHandle
except ImportError:
    class UVTimerHandle:
        pass

__all__ = [
    'ConnType',
    'Connection',
]

ConnType = TypeVar('ConnType', bound='Connection')


class Connection:
    """
    Base connection interface, that used by both client and server side
    """
    __slots__ = (
        'download_speed',
        'scope',
        'input_pool',
        'send_queue',
        'send_task',
        'recv_future',
        'locker',
        'conf',
        'allowed_compressors',
        'default_compressor',
        '_closed',
        '_loop',
        '_identity',
        '_credentials',
        '_message_pool',
    )

    PASS_EXCEPTIONS = (
        KeyboardInterrupt,
        asyncio.CancelledError,
        asyncio.TimeoutError,
        asyncio.InvalidStateError,
    )

    address: tuple[str, int]
    _stream: IOStream
    logging: Logger

    def __init__(self, conf: Config):
        self.conf: Config = conf
        self.download_speed: int = 0
        self.scope: sentry_sdk.Scope = sentry_sdk.Scope()
        self.input_pool: dict[int, Input] = {}
        self.send_queue: asyncio.Queue = asyncio.Queue()
        self.send_task: asyncio.Task | None = None
        self.recv_future: asyncio.Future | None = None
        self.locker: asyncio.Future | None = None
        self.allowed_compressors: set[int] = {C_NONE}
        self.default_compressor: int = C_NONE
        self._closed: bool = False
        self._loop = asyncio.get_event_loop()
        self._identity = None
        self._credentials = None
        self._message_pool: list[int] = []

    def set_compressors(self, allowed: list[str], default: str = None):
        allowed = [a.lower() for a in allowed]
        self.allowed_compressors = {Compressor.codes[a] for a in allowed if a in Compressor.codes}
        self.allowed_compressors.add(C_NONE)
        if default is None or default.lower() not in Compressor.codes:
            self.default_compressor = C_NONE
        else:
            self.default_compressor = Compressor.codes[default.lower()]

    @property
    def is_open(self):
        return not self._closed and not self._stream.closed()

    @property
    def host(self) -> str:
        return self.address[0]

    @property
    def port(self) -> int:
        return self.address[1]

    async def start(self) -> None:
        """
        Init connection and start the reading loop
        :return:
        """
        await self.init()

        self.send_task = self._loop.create_task(self.send_loop())
        self.send_task.add_done_callback(self.on_tick_done)

        await self.recv_loop()

    async def init(self):
        """Init connection state"""
        raise NotImplementedError

    async def send_loop(self):
        while self.is_open:
            waiter, self.locker = await self.send_queue.get()
            waiter.set_result(None)
            await self.locker

    async def recv_loop(self):
        while self.is_open:
            if self.recv_future is not None:
                await self.recv_future

            self.recv_future = asyncio.Future()
            task = self._loop.create_task(self.tick())
            task.add_done_callback(self.on_tick_done)

    async def tick(self):
        action_type_id = await self.read(1)
        action_class = BaseAction.get_class_by_type_id(action_type_id)
        if action_class is None:
            raise ProtocolError(f'Received unknown Action Type ID [{action_type_id.hex()}]')

        try:
            await self.handle(await action_class.init(self))
        except self.conf.ignore_errors as err:
            self.close(err)
        except Exception as err:
            sentry_sdk.capture_exception(err, scope=self.scope)
            self.close(err)

    def on_tick_done(self, task):
        try:
            if exc := task.exception():
                self.close(exc)
        except (asyncio.CancelledError, asyncio.InvalidStateError) as err:
            self.close(err)

    async def handle(self, action: BaseAction):
        """
        Do whatever you need with incoming actions
        :param action:
        :return:
        """
        raise NotImplementedError

    async def send(self, handler_id: int, data=None, message_id=None, compression=None, *,
                   headers=None, status=None):
        raise NotImplementedError

    async def send_stream(self, handler_id: int, data: BytesAnyGen, data_type: int,
                          message_id=None, compression=None, *,
                          headers=None, status=None):
        raise NotImplementedError

    async def read(self, num_bytes: int, partial: bool = False) -> bytes:
        """
        Should read from stream, may log something, reset timers, etc.
        :param num_bytes:
        :param partial:
        :return:
        """
        return await self._stream.read_bytes(num_bytes, partial=partial)

    async def read_until(self, delimiter: bytes, max_bytes: int | None) -> bytes:
        """
        Should read from stream, may log something, reset timers, etc.
        :param delimiter:
        :param max_bytes:
        :return:
        """
        return await self._stream.read_until(delimiter, max_bytes=max_bytes)

    async def write(self, data: bytes | bytearray | memoryview):
        """
        Should write to stream, may log something, reset timers, etc.
        :param data:
        :return:
        """
        return await self._stream.write(data)

    def get_free_message_id(self) -> int:
        raise NotImplementedError

    @asynccontextmanager
    async def preserve_message_id(self, message_id: int):
        """
        Lock message_id from being used
        e.g. next preserve_message_id() with the same message_id won't run until previous stop
        """
        try:
            while message_id in self._message_pool:
                await asyncio.sleep(0.5)
            self._message_pool.append(message_id)
            yield
        finally:
            try:
                self._message_pool.remove(message_id)
            except ValueError:
                pass

    @asynccontextmanager
    async def lock_write(self):
        """
        Lock write ability until previously called are done
        """
        waiter = asyncio.Future()
        locker = asyncio.Future()
        await self.send_queue.put((waiter, locker))
        await waiter
        yield
        locker.set_result(None)

    @property
    def identity(self) -> Identity | None:
        return self._identity

    @property
    def credentials(self):
        return self._credentials

    @property
    def identity_scope_user(self):
        if not self.signed_in():
            return {'ip': self.host}

        return self.identity.sentry_scope

    def signed_in(self) -> bool:
        return self._identity is not None

    def set_identity(self, identity: Identity, credentials=None):
        """
        Mark connection as Signed In with identity [and credentials used]
        :param identity:
        :param credentials:
        :return:
        """
        raise NotImplementedError

    def sign_out(self):
        """
        Mark connection as Signed Out
        :return:
        """
        raise NotImplementedError

    def close(self, exc: BaseException = None) -> None:
        """
        Close stream if opened, log exceptions, clear caches, etc.
        :param exc: Exception that caused closing
        :return:
        """
        if self._closed:
            return

        self._closed = True
        self.sign_out()
        if exc and not isinstance(exc, self.conf.ignore_errors):
            self.logging.error(f'{exc.__class__.__qualname__} {exc}')
            sentry_sdk.capture_exception(exc, scope=self.scope)
        self._stream.close(exc)
        for task in self._close_tasks():
            if task is None:
                continue
            if isinstance(task, (asyncio.TimerHandle, UVTimerHandle)):
                task.cancel()
            elif not task.done():
                if exc and not isinstance(task, asyncio.Task):
                    task.set_exception(exc)
                else:
                    task.cancel()

    def _close_tasks(self):
        yield self.locker
        yield self.recv_future
        yield self.send_task

    def debug(self, msg: str, *args, **kwargs):
        if self.conf.debug:
            self.logging.debug(msg, *args, **kwargs)

    async def __aenter__(self) -> 'ConnType':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close(exc_val)
