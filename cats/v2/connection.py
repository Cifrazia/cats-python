import asyncio
import traceback
from contextlib import asynccontextmanager
from logging import Logger
from typing import Generator, TypeVar

import sentry_sdk
from tornado.iostream import IOStream

from cats.v2.action import BaseAction, Input
from cats.v2.config import Config
from cats.v2.errors import ProtocolViolation
from cats.v2.identity import Identity
from cats.v2.options import Options
from cats.v2.types import BytesAnyGen

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
        '_closed',
        '_credentials',
        '_identity',
        '_identity_timer',
        '_loop',
        '_message_id_pool',
        'conf',
        'input_pool',
        'lock_write',
        'lock_read',
        'options',
        'scope',
        'send_queue',
        'send_task',
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
        self._closed: bool = False
        self._credentials = None
        self._identity: Identity | None = None
        self._identity_timer: asyncio.TimerHandle | None = None
        self._loop = asyncio.get_running_loop()
        self._message_id_pool: list[int] = []
        self.conf: Config = conf
        self.input_pool: dict[int, Input] = {}
        self.lock_write: asyncio.Lock = asyncio.Lock()
        self.lock_read: asyncio.Lock = asyncio.Lock()
        self.options: Options = Options()
        self.scope: sentry_sdk.Scope = sentry_sdk.Scope()

    def set_compressors(self, allowed: list[str], default: str = None):
        compressors = self.conf.compressors
        self.options.allowed_compressors = [
            compressor
            for type_name in allowed
            if (compressor := compressors.find(type_name.lower()))
        ]
        self.options.default_compressor = compressors.find((default or '').lower())

    def set_scheme(self, scheme_format: str):
        self.options.scheme = self.conf.schemes.find_strict(scheme_format)

    @property
    def is_open(self):
        return not self._closed and not self._stream.closed()

    @property
    def host(self) -> str:
        return self.address[0]

    @property
    def port(self) -> int:
        return self.address[1]

    async def init(self):
        """Init connection state"""
        raise NotImplementedError

    async def start(self) -> None:
        """
        Init connection and start the reading loop
        :return:
        """
        await self.recv_loop()

    async def recv_loop(self):
        while self.is_open:
            await self.lock_read.acquire()
            if not self.is_open:
                return
            task = self._loop.create_task(self.tick())
            task.add_done_callback(self.on_tick_done)

    async def tick(self):
        action_type_id = await self.read(1)
        action_class = BaseAction.get_type_by_id(action_type_id)
        if action_class is None:
            raise ProtocolViolation(f'Received unknown Action Type ID [{action_type_id.hex()}]', conn=self)

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

    async def send(self, handler_id: int, data=None, message_id=None, compressor=None, *,
                   headers=None, status=None):
        raise NotImplementedError

    async def send_stream(self, handler_id: int, data: BytesAnyGen, data_type: int,
                          message_id=None, compressor=None, *,
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
            while message_id in self._message_id_pool:
                await asyncio.sleep(0.5)
            self._message_id_pool.append(message_id)
            yield
        finally:
            try:
                self._message_id_pool.remove(message_id)
            except ValueError:
                pass

    @property
    def identity(self) -> Identity | None:
        return self._identity

    @property
    def credentials(self):
        return self._credentials

    @property
    def identity_scope_user(self):
        if not self.signed_in:
            return {'ip': self.host}

        return self.identity.sentry_scope

    @property
    def signed_in(self) -> bool:
        return self._identity is not None

    def set_identity(self, identity: Identity, credentials=None, timeout: int | float | None = None) -> None:
        """
        Mark connection as Signed In with identity [and credentials used]
        :param identity: Identity subclass object
        :param credentials: anything that was used to get identity, may be JWT, dict, key, etc.
        :param timeout: How long in seconds should identity be stored. 0 | None for always
        :return:
        """
        self._identity: Identity | None = identity
        self._credentials = credentials

        self.scope.set_user(self.identity_scope_user)
        sentry_sdk.add_breadcrumb(message='Sign in', data={
            'id': identity.id,
            'model': identity.__class__.__name__,
            'instance': repr(identity),
        })
        self.prolong_identity(timeout)

        self.debug(f'Signed in as {self.identity_scope_user} <{self.host}:{self.port}>')

    def prolong_identity(self, timeout: int | float | None = None) -> None:
        """
        Recreates identity removal timer with new timeout. If timeout is None, no timer is created
        :param timeout:
        :return: How long in seconds should identity be stored. 0 | None for always
        """
        if self._identity_timer is not None:
            self._identity_timer.cancel()
            self._identity_timer = None
        if timeout:
            self._identity_timer = self._loop.call_later(timeout, self.sign_out)

    def sign_out(self) -> None:
        """
        Mark connection as Signed Out
        :return:
        """
        if not self.signed_in:
            return
        self.prolong_identity(None)
        self._identity = None
        self._credentials = None
        self.scope.set_user(self.identity_scope_user)
        sentry_sdk.add_breadcrumb(message='Sign out')
        self.debug(f'Signed out from {self.identity_scope_user} <{self.host}:{self.port}>')

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
            tb = "\n".join([i for i in traceback.format_tb(exc.__traceback__)])
            self.logging.error(f'{exc!r} \n{tb}')
            sentry_sdk.capture_exception(exc, scope=self.scope)
        self._stream.close(exc)
        for task in self._close_tasks():
            if task is None:
                continue
            if isinstance(task, asyncio.TimerHandle):
                if not task.cancelled():
                    task.cancel()
            elif isinstance(task, asyncio.Lock):
                if task.locked():
                    task.release()
            elif not task.done():
                if exc and not isinstance(task, asyncio.Task):
                    task.set_exception(exc)
                else:
                    task.cancel()

    def _close_tasks(self) -> Generator[asyncio.Task | asyncio.TimerHandle | asyncio.Future | asyncio.Lock, None, None]:
        yield self.lock_read
        yield self.lock_write

    def debug(self, msg: str, *args, **kwargs):
        if self.conf.debug:
            self.logging.debug(msg, *args, **kwargs)

    async def __aenter__(self) -> 'ConnType':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close(exc_val)
