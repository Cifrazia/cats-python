import asyncio
import inspect
from collections import defaultdict
from logging import getLogger
from random import randint
from time import time, time_ns
from typing import Awaitable, Callable

from tornado.iostream import IOStream
from tornado.tcpclient import TCPClient

from cats.errors import ProtocolError
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
        '_sub_id',
        '_stream',
        '_listener',
        '_sender',
        '_pinger',
        '_recv_pool',
    )
    PROTOCOL_VERSION: int = 2
    logging = getLogger('CATS.Client')

    def __init__(self, conf: Config, api_version: int):
        super().__init__(conf)
        self.api_version: int = api_version
        self.time_delta: float = 0.0
        self.subscriptions: dict[
            int, dict[int, Callable[[Action], Awaitable[None] | None]]] = defaultdict(
            dict
        )
        self._sub_id: int = 0
        self._listener: asyncio.Task | None = None
        self._sender: asyncio.Task | None = None
        self._pinger: asyncio.Task | None = None
        self._recv_pool: dict[int, asyncio.Future] = {}
        self._stream: IOStream | None = None
        self.address: tuple[str, int] = '0.0.0.0', 0

    async def connect(self, host: str, port: int, **kwargs):
        client = TCPClient()
        self._stream = await client.connect(host, port, **kwargs)
        self.address = host, port
        await self.init()
        self._listener = asyncio.get_running_loop().create_task(self.start())
        self._listener.add_done_callback(self.on_tick_done)
        self.debug(f'New connection established: {self.address}')

    async def start(self) -> None:
        self._sender = self._loop.create_task(self.send_loop())
        self._pinger = self._loop.create_task(self.ping())

        self._sender.add_done_callback(self.on_tick_done)
        self._pinger.add_done_callback(self.on_tick_done)

        await self.recv_loop()

    async def init(self):
        await self.write(to_uint(self.PROTOCOL_VERSION, 4))
        result = await self.read(4)
        if result != bytes(4):
            raise ProtocolError(
                f'Unsupported protocol version. '
                f'Please upgrade your client to: {as_uint(result)}',
                conn=self
            )

        client_stmt = ClientStatement(
            api=self.api_version,
            client_time=time_ns() // 1000_000,
            scheme_format='JSON',
            compressors=['gzip', 'zlib'],
            default_compression='zlib',
        )
        self.set_compressors(['gzip', 'zlib'], 'zlib')
        await self.write(client_stmt.pack())
        stmt: ServerStatement = ServerStatement.unpack(
            await self.read(as_uint(await self.read(4)))
        )
        self.time_delta = (stmt.server_time / 1000) - time()

        if self.conf.handshake is not None:
            await self.conf.handshake.send(self)

        self.debug(f'{self} initialized')

    async def handle(self, action: BaseAction):
        if isinstance(action, PingAction):
            await self.handle_ping_action(action)
        elif isinstance(action, Action):
            await action.recv_data()
            if action.message_id >= 0x8000:
                await self.handle_broadcast(action)
            elif action.message_id in self._recv_pool:
                await self.handle_response(action)
            else:
                self.debug(f'Received unexpected action {action = }')
        else:
            self.debug(f'Received unsupported Action: {type(action).__qualname__}')

    async def handle_response(self, action: Action):
        future = self._recv_pool.pop(action.message_id)
        future.set_result(action)

    async def handle_broadcast(self, action: Action):
        if action.handler_id in self.subscriptions:
            for fn in self.subscriptions[action.handler_id].values():
                res = fn(action)
                if inspect.isawaitable(res):
                    await res

    async def handle_ping_action(self, action: PingAction):
        self.debug(f'Pong {action.send_time} [-] {action.recv_time}')
        await action.dump_data(0)

    def subscribe(
        self,
        handler_id: int,
        handler: Callable[[Action], Awaitable[None] | None]
    ) -> int:
        self._sub_id += 1
        self.subscriptions[handler_id][self._sub_id] = handler
        return self._sub_id

    def unsubscribe(
        self,
        handler_id: int,
        handler: Callable[[Action], Awaitable[None] | None] | int
    ) -> None:
        if handler_id in self.subscriptions:
            if isinstance(handler, int):
                self.subscriptions[handler_id].pop(handler, None)
            else:
                self.subscriptions[handler_id] = {
                    k: v for k, v in self.subscriptions[handler_id]
                    if v is not handler
                }

    async def set_download_speed(self, speed=0):
        await self.write(b'\x05')
        await self.write(to_uint(speed, 4))

    async def send(
        self,
        handler_id: int,
        data=None,
        message_id=None,
        compression=None, *,
        headers=None, status=None
    ) -> ActionLike | None:
        action = Action(
            data=data, headers=headers, status=status,
            message_id=self.get_free_message_id() if message_id is None else message_id,
            handler_id=handler_id, compression=compression
        )
        await action.send(self)
        return await self.recv(action.message_id)

    async def send_stream(
        self,
        handler_id: int,
        data: BytesAnyGen,
        data_type: int,
        message_id=None,
        compression=None, *,
        headers=None,
        status=None
    ) -> ActionLike | None:
        action = StreamAction(
            data=data, headers=headers, status=status,
            message_id=self.get_free_message_id() if message_id is None else message_id,
            handler_id=handler_id, data_type=data_type, compression=compression
        )
        await action.send(self)
        return await self.recv(action.message_id)

    async def recv(self, message_id: int) -> Action | None:
        future = asyncio.Future()
        self._recv_pool[message_id] = future
        return await future

    async def ping(self):
        if not self.conf.idle_timeout:
            return
        wait = max(0.1, round(self.conf.idle_timeout * 0.9, 2))
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
        yield self._pinger
        yield self._sender
