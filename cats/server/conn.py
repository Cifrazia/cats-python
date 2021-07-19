import asyncio
from asyncio import Future
from contextlib import asynccontextmanager, contextmanager
from functools import partial
from logging import getLogger
from random import randint
from typing import Any, Iterable, Optional, TypeVar

from sentry_sdk import Scope, add_breadcrumb, capture_exception
from tornado.iostream import IOStream, StreamClosedError

from cats.errors import HandshakeError, ProtocolError
from cats.identity import Identity
from cats.server.action import *
from cats.server.handlers import HandlerItem
from cats.types import BytesAnyGen

__all__ = [
    'ConnType',
    'Connection',
]

logging = getLogger('CATS.conn')
ConnType = TypeVar('ConnType', bound='Connection')


class Connection:
    MAX_PLAIN_DATA_SIZE = 1 << 24
    STREAM_ERRORS = (asyncio.TimeoutError, asyncio.CancelledError, asyncio.InvalidStateError, StreamClosedError)
    IGNORE_ERRORS = (*STREAM_ERRORS, HandshakeError, ProtocolError, KeyboardInterrupt)

    __slots__ = (
        '_closed', 'stream', 'address', 'api_version', '_app', 'scope', 'download_speed',
        '_identity', '_credentials', 'loop', 'input_deq', '_idle_timer', 'message_pool', 'is_sending',
        'debug', 'recv_fut',
    )

    def __init__(self, stream: IOStream, address: tuple[str, int], api_version: int, app, debug=False):
        logging.debug(f'New connection established: {address}')
        self._closed = False
        self.stream = stream
        self.address: tuple[str, int] = address
        self.api_version = api_version
        self._app = app
        self.scope = Scope()
        self._identity: Optional[Identity] = None
        self._credentials = None
        self.loop = asyncio.get_event_loop()
        self.input_deq: dict[int, Input] = {}
        self._idle_timer: Optional[asyncio.Future] = None
        self.message_pool: list[int] = []
        self.is_sending = False
        self.download_speed = 0
        self.debug = debug
        self.recv_fut: Optional[asyncio.Future] = None

    @property
    def host(self) -> str:
        return self.address[0]

    @property
    def port(self) -> int:
        return self.address[1]

    @property
    def is_open(self):
        return not self._closed and not self.stream.closed()

    @property
    def app(self):
        return self._app

    async def init(self):
        logging.debug(f'{self} initialized')

    async def start(self, ping=False):
        if ping:
            self.loop.create_task(self.ping())

        while self.is_open:
            if self.recv_fut is not None:
                await self.recv_fut

            self.recv_fut = Future()
            task = self.loop.create_task(self.tick())
            task.add_done_callback(self.on_tick_done)

    @contextmanager
    def preserve_message_id(self, message_id: int):
        if message_id in self.message_pool:
            raise ProtocolError('Provided message_id already in use')

        try:
            self.message_pool.append(message_id)
            yield
        finally:
            try:
                self.message_pool.remove(message_id)
            except (KeyError, ValueError):
                pass

    async def recv(self):
        self.reset_idle_timer()
        action_type_id = await self.stream.read_bytes(1)
        action_class = BaseAction.get_class_by_type_id(action_type_id)
        if action_class is None:
            raise ProtocolError(f'Received unknown Action Type ID [{action_type_id.hex()}]')

        action = await action_class.init(self)
        if hasattr(action, 'recv_data'):
            await action.recv_data()
        return action

    async def tick(self):
        self.reset_idle_timer()
        action_type_id = await self.stream.read_bytes(1)
        action_class = BaseAction.get_class_by_type_id(action_type_id)
        if action_class is None:
            raise ProtocolError(f'Received unknown Action Type ID [{action_type_id.hex()}]')

        try:
            action = await action_class.init(self)
            await action.handle()
        except self.IGNORE_ERRORS as err:
            self.close(err)
        except Exception as err:
            capture_exception(err, scope=self.scope)
            self.close(err)

    def on_tick_done(self, task):
        exc = None
        try:
            exc = task.exception()
        except (asyncio.CancelledError, asyncio.InvalidStateError) as err:
            exc = err
        if exc:
            self.close(exc)

    def dispatch(self, handler_id):
        handlers = self.app.get_handlers_by_id(handler_id)
        if isinstance(handlers, HandlerItem):
            return handlers.handler

        elif isinstance(handlers, list):
            for item in handlers:
                item: HandlerItem
                end_version = self.api_version if item.end_version is None else item.end_version
                if item.version <= self.api_version <= end_version:
                    return item.handler

        raise ProtocolError(f'Handler with id {handler_id} not found')

    async def ping(self):
        if not self._app.idle_timeout:
            return
        wait = max(0.1, round(self._app.idle_timeout / 2, 2))
        pong = PingAction()
        while self.is_open:
            await asyncio.sleep(wait)
            await pong.send(self)

    async def set_download_speed(self, speed=0):
        await self.stream.write(b'\x05')
        await self.stream.write(speed.to_bytes(4, 'big', signed=False))

    async def send(self, handler_id: int, data=None, message_id=None, compression=None, *,
                   headers=None, status=None):
        action = Action(data=data, headers=headers, status=status,
                        message_id=self._get_free_message_id() if message_id is None else message_id,
                        handler_id=handler_id, compression=compression)
        await action.send(self)

    async def send_stream(self, handler_id: int, data: BytesAnyGen, data_type: int,
                          message_id=None, compression=None, *,
                          headers=None, status=None):
        action = StreamAction(data=data, headers=headers, status=status,
                              message_id=self._get_free_message_id() if message_id is None else message_id,
                              handler_id=handler_id, data_type=data_type, compression=compression)
        await action.send(self)

    def attach_to_channel(self, channel: str):
        self.app.attach_conn_to_channel(self, channel=channel)

    def detach_from_channel(self, channel: str):
        self.app.detach_conn_from_channel(self, channel=channel)

    @property
    def conns_with_same_identity(self) -> Iterable['Connection']:
        return self.app.channel(f'model_{self._identity.model_name}:{self._identity.id}')

    @property
    def conns_with_same_model(self) -> Iterable['Connection']:
        return self.app.channel(f'model_{self._identity.model_name}')

    @property
    def identity(self) -> Optional[Identity]:
        return self._identity

    @property
    def credentials(self) -> Optional[Any]:
        return self._credentials

    @property
    def identity_scope_user(self):
        if not self.signed_in():
            return {'ip': self.host}

        return self.identity.sentry_scope

    def signed_in(self) -> bool:
        return self._identity is not None

    def sign_in(self, identity: Identity, credentials=None):
        self._identity: Optional[Identity] = identity
        self._credentials = credentials

        model_group = f'model_{identity.model_name}'
        auth_group = f'{model_group}:{identity.id}'
        self.attach_to_channel(model_group)
        self.attach_to_channel(auth_group)

        self.scope.set_user(self.identity_scope_user)
        add_breadcrumb(message='Sign in', data={
            'id': identity.id,
            'model': identity.__class__.__name__,
            'instance': repr(identity),
        })

        logging.debug(f'Signed in as {identity.__class__.__name__} <{self.host}:{self.port}>')

    def sign_out(self):
        logging.debug(f'Signed out from {self.identity.__class__.__name__} <{self.host}:{self.port}>')
        if self.signed_in():
            self._sign_out_and_remove_from_channels()
        self.scope.set_user(self.identity_scope_user)
        add_breadcrumb(message='Sign out')

        return self

    def _sign_out_and_remove_from_channels(self):
        model_group = f'model_{self.identity.model_name}'
        auth_group = f'{model_group}:{self._identity.id}'

        self.detach_from_channel(auth_group)
        self.detach_from_channel(model_group)

        self._identity = None
        self._credentials = None

    def close(self, exc=None):
        if self._closed:
            return

        self._closed = True

        self.sign_out()
        if exc and not isinstance(exc, self.IGNORE_ERRORS):
            logging.error(exc)
            capture_exception(exc, scope=self.scope)

        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        if self.recv_fut is not None:
            self.recv_fut.cancel()
            self.recv_fut = None
        self.stream.close(exc)

    def __str__(self) -> str:
        return f'CATS.Connection: {self.host}:{self.port} api@{self.api_version}'

    def reset_idle_timer(self):
        if self.app.idle_timeout > 0:
            if self._idle_timer is not None:
                self._idle_timer.cancel()

            self._idle_timer = self.loop.call_later(self.app.idle_timeout, partial(self.close, asyncio.TimeoutError()))

    def _get_free_message_id(self) -> int:
        while True:
            message_id = randint(17783, 35565)
            if message_id not in self.message_pool:
                break

        return message_id

    @asynccontextmanager
    async def lock_write(self):
        while self.is_sending:
            await asyncio.sleep(0.05)
        self.is_sending = True
        yield
        self.is_sending = False
