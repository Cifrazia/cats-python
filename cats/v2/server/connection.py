import asyncio
import functools
from logging import getLogger
from random import randint
from time import time_ns
from typing import Iterable

import sentry_sdk
from tornado.iostream import IOStream

from cats.errors import ProtocolError
from cats.identity import Identity, IdentityObject
from cats.types import BytesAnyGen
from cats.utils import as_uint
from cats.v2.action import *
from cats.v2.auth import AuthError
from cats.v2.config import Config
from cats.v2.connection import Connection as BaseConnection
from cats.v2.server.application import Application
from cats.v2.server.handlers import HandlerItem
from cats.v2.statement import ClientStatement, ServerStatement

__all__ = [
    'Connection',
]


class Connection(BaseConnection):
    __slots__ = (
        'api_version',
        'client',
        'address',
        'protocol',
        '_stream',
        '_app',
        '_idle_timer',
    )

    logging = getLogger('CATS.Connection')

    def __init__(self, stream: IOStream, address: tuple[str, int], protocol: int, conf: Config, app: Application):
        super().__init__(conf)
        self.api_version: int | None = None
        self.address: tuple[str, int] = address
        self.protocol: int = protocol
        self._stream: IOStream = stream
        self._app = app
        self._credentials = None
        self._idle_timer: asyncio.Future | None = None
        self.client: ClientStatement | None = None
        self.debug(f'New connection established: {address}')

    @property
    def app(self):
        return self._app

    async def init(self):
        self.client: ClientStatement = ClientStatement.unpack(
            await self.read(as_uint(await self.read(4)))
        )
        self.api_version = self.client.api
        self.set_compressors(self.client.compressors, self.client.default_compression)
        self.debug(f'[RECV {self.address}] {self.client}')

        server_stmt = ServerStatement(
            server_time=time_ns() // 1000_000,
        )
        await self.write(server_stmt.pack())
        self.debug(f'[SEND {self.address}] {server_stmt}')

        if self.conf.handshake is not None:
            await self.conf.handshake.validate(self)

        self.debug(f'{self} initialized')

    async def handle(self, action: BaseAction):
        if isinstance(action, InputAction):
            await action.recv_data()
            if action.message_id in self.input_pool:
                self.input_pool[action.message_id].done(action)
            else:
                raise ProtocolError('Received answer but input does`t exists')
        elif isinstance(action, CancelInputAction):
            if action.message_id in self.input_pool:
                self.input_pool[action.message_id].cancel()
            await action.dump_data(0)
        elif isinstance(action, DownloadSpeedAction):
            limit = action.speed
            if not limit or (1024 <= limit <= 33_554_432):
                self.download_speed = limit
            else:
                raise ProtocolError('Unsupported download speed limit')
            await action.dump_data(0)
        elif isinstance(action, PingAction):
            self.debug(f'Ping {action.send_time} [-] {action.recv_time}')
            await action.send(self)
            await action.dump_data(0)
        elif isinstance(action, Action):
            async with self.preserve_message_id(action.message_id):
                handler = self.dispatch(action.handler_id)
                try:
                    result = await self.app.run(handler(action))
                    if result is not None:
                        if not isinstance(result, Action):
                            raise ProtocolError('Returned invalid response')

                        result.handler_id = action.handler_id
                        result.message_id = action.message_id
                        result.offset = action.offset
                        await result.send(self)
                except action.conn.conf.ignore_errors:
                    raise
                except Exception as err:
                    sentry_sdk.capture_exception(err, scope=self.scope)
                    raise

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

    async def send(self, handler_id: int, data=None, message_id=None, compression=None, *,
                   headers=None, status=None):
        action = Action(data=data, headers=headers, status=status,
                        message_id=self.get_free_message_id() if message_id is None else message_id,
                        handler_id=handler_id, compression=compression)
        await action.send(self)

    async def send_stream(self, handler_id: int, data: BytesAnyGen, data_type: int,
                          message_id=None, compression=None, *,
                          headers=None, status=None):
        action = StreamAction(data=data, headers=headers, status=status,
                              message_id=self.get_free_message_id() if message_id is None else message_id,
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

    async def sign_in(self, silent: bool = False, **kwargs) -> IdentityObject | None:
        try:
            identity, credentials = await self._app.auth.sign_in(**kwargs)
            self.set_identity(identity, credentials=credentials)
            return identity
        except AuthError:
            if not silent:
                raise

    def set_identity(self, identity: Identity, credentials=None):
        self._identity: Identity | None = identity
        self._credentials = credentials

        model_group = f'model_{identity.model_name}'
        auth_group = f'{model_group}:{identity.id}'
        self.attach_to_channel(model_group)
        self.attach_to_channel(auth_group)

        self.scope.set_user(self.identity_scope_user)
        sentry_sdk.add_breadcrumb(message='Sign in', data={
            'id': identity.id,
            'model': identity.__class__.__name__,
            'instance': repr(identity),
        })
        self.debug(f'Signed in as {self.identity_scope_user} <{self.host}:{self.port}>')

    def sign_out(self):
        self.debug(f'Signed out from {self.identity_scope_user} <{self.host}:{self.port}>')
        if self.signed_in():
            self._sign_out_and_remove_from_channels()
        self.scope.set_user(self.identity_scope_user)
        sentry_sdk.add_breadcrumb(message='Sign out')

        return self

    def _sign_out_and_remove_from_channels(self):
        model_group = f'model_{self.identity.model_name}'
        auth_group = f'{model_group}:{self._identity.id}'

        self.detach_from_channel(auth_group)
        self.detach_from_channel(model_group)

        self._identity = None
        self._credentials = None

    def __str__(self) -> str:
        return f'CATS.Connection: {self.host}:{self.port} api@{self.api_version}'

    async def read(self, num_bytes: int, partial: bool = False) -> bytes:
        res = await self._stream.read_bytes(num_bytes, partial=partial)
        self.reset_idle_timer()
        return res

    async def read_until(self, delimiter: bytes, max_bytes: int | None) -> bytes:
        res = await self._stream.read_until(delimiter, max_bytes=max_bytes)
        self.reset_idle_timer()
        return res

    async def write(self, data: bytes | bytearray | memoryview) -> None:
        res = await self._stream.write(data)
        self.reset_idle_timer()
        return res

    def reset_idle_timer(self):
        if not self.conf.idle_timeout > 0:
            return
        if self._idle_timer is not None:
            self._idle_timer.cancel()

        self._idle_timer = self._loop.call_later(
            self.conf.idle_timeout,
            functools.partial(self.close, asyncio.TimeoutError())
        )

    def get_free_message_id(self) -> int:
        while True:
            message_id = randint(0x8000, 0xFFFF)
            if message_id not in self._message_pool:
                return message_id

    def _close_tasks(self):
        yield self._idle_timer
        yield from super()._close_tasks()
