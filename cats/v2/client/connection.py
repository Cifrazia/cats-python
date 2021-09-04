import asyncio
import inspect
from logging import getLogger
from random import randint
from time import time, time_ns
from typing import Awaitable, Callable

import sentry_sdk
from tornado.iostream import IOStream
from tornado.tcpclient import TCPClient

from cats.errors import ProtocolError
from cats.identity import Identity
from cats.types import BytesAnyGen
from cats.utils import as_uint, to_uint
from cats.v2.action import Action, ActionLike, BaseAction, PingAction, StreamAction
from cats.v2.config import Config
from cats.v2.connection import Connection as BaseConnection
from cats.v2.statement import ClientStatement, ServerStatement

__all__ = [
    'Connection',
]


class Connection(BaseConnection):
    __slots__ = (
        'api_version',
        'time_delta',
        'subscriptions',
        'address',
        '_stream',
        '_listener',
        '_recv_pool',
    )
    PROTOCOL_VERSION: int = 2
    logging = getLogger('CATS.Client')

    def __init__(self, conf: Config, api_version: int):
        super().__init__(conf)
        self.api_version: int = api_version
        self.time_delta: float = 0.0
        self.subscriptions: dict[int, Callable[[Action], Awaitable[None] | None]] = {}
        self._listener: asyncio.Task | None = None
        self._recv_pool: dict[int, asyncio.Future] = {}
        self._stream: IOStream | None = None
        self.address: tuple[str, int] = '0.0.0.0', 0

    async def connect(self, host: str, port: int, **kwargs):
        client = TCPClient()
        self._stream = await client.connect(host, port, **kwargs)
        self.address = host, port
        self._listener = asyncio.get_event_loop().create_task(self.start())
        self._listener.add_done_callback(self.on_tick_done)
        self.debug(f'New connection established: {self.address}')

    async def start(self) -> None:
        await self.init()
        self._loop.create_task(self.send_loop()).add_done_callback(self.on_tick_done)
        self._loop.create_task(self.ping()).add_done_callback(self.on_tick_done)
        await self.recv_loop()

    async def init(self):
        await self.write(to_uint(self.PROTOCOL_VERSION, 4))
        result = await self.read(4)
        if result != bytes(4):
            raise ProtocolError(f'Unsupported protocol version. Please upgrade your client to: {as_uint(result)}')

        client_stmt = ClientStatement(
            api=self.api_version,
            clientTime=time_ns() // 1000_000,
            schemeFormat='JSON',
            compressors=['gzip', 'zlib'],
            defaultCompression='zlib',
        )
        self.set_compressors(['gzip', 'zlib'], 'zlib')
        await self.write(client_stmt.pack())
        stmt: ServerStatement = ServerStatement.unpack(
            await self.read(as_uint(await self.read(4)))
        )
        self.time_delta = (stmt.serverTime / 1000) - time()

        if self.conf.handshake is not None:
            await self.conf.handshake.send(self)

        self.debug(f'{self} initialized')

    async def handle(self, action: BaseAction):
        if isinstance(action, PingAction):
            self.debug(f'Pong {action.send_time} [-] {action.recv_time}')
            await action.dump_data(0)
        elif isinstance(action, Action):
            await action.recv_data()
            if action.message_id >= 0x8000:
                # Broadcast
                if action.handler_id in self.subscriptions:
                    fn = self.subscriptions[action.handler_id]
                    res = fn(action)
                    if inspect.isawaitable(res):
                        await res
            elif action.message_id in self._recv_pool:
                # Reply
                future = self._recv_pool.pop(action.message_id)
                future.set_result(action)
            else:
                self.debug(f'Received unexpected action {action = }')
        else:
            self.debug(f'Received unsupported Action: {type(action).__qualname__}')

    def subscribe(self, handler_id: int, handler: Callable[[Action], Awaitable[None] | None]):
        self.subscriptions[handler_id] = handler

    def unsubscribe(self, handler_id: int):
        if handler_id in self.subscriptions:
            self.subscriptions.pop(handler_id)

    async def set_download_speed(self, speed=0):
        await self.write(b'\x05')
        await self.write(to_uint(speed, 4))

    async def send(self, handler_id: int, data=None, message_id=None, compression=None, *,
                   headers=None, status=None) -> ActionLike | None:
        action = Action(data=data, headers=headers, status=status,
                        message_id=self.get_free_message_id() if message_id is None else message_id,
                        handler_id=handler_id, compression=compression)
        await action.send(self)
        return await self.recv(action.message_id)

    async def send_stream(self, handler_id: int, data: BytesAnyGen, data_type: int,
                          message_id=None, compression=None, *,
                          headers=None, status=None) -> ActionLike | None:
        action = StreamAction(data=data, headers=headers, status=status,
                              message_id=self.get_free_message_id() if message_id is None else message_id,
                              handler_id=handler_id, data_type=data_type, compression=compression)
        await action.send(self)
        return await self.recv(action.message_id)

    async def recv(self, message_id: int) -> Action | None:
        future = asyncio.Future()
        self._recv_pool[message_id] = future
        return await future

    def sign_in(self, identity: Identity, credentials=None):
        self._identity: Identity | None = identity
        self._credentials = credentials

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
            self._identity = None
            self._credentials = None
        self.scope.set_user(self.identity_scope_user)
        sentry_sdk.add_breadcrumb(message='Sign out')
        return self

    async def ping(self):
        if not self.conf.idle_timeout:
            return
        wait = max(0.1, round(self.conf.idle_timeout / 2, 2))
        pong = PingAction()
        while self.is_open:
            await asyncio.sleep(wait)
            await pong.send(self)

    def __str__(self) -> str:
        return f'CATS.Connection: {self.host}:{self.port} api@{self.api_version}'

    def get_free_message_id(self) -> int:
        while True:
            message_id = randint(0x0000, 0x7FFF)
            if message_id not in self._message_pool:
                return message_id

    def _close_tasks(self):
        yield from super()._close_tasks()
        yield from self._recv_pool.values()