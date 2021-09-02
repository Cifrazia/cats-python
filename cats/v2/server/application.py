from collections import defaultdict
from functools import partial
from typing import Awaitable, Iterable, Type

from cats.v2.action import ActionLike
from cats.v2.config import Config
from cats.v2.connection import Connection
from cats.v2.server.handlers import Api, Handler, HandlerItem
from cats.v2.server.middleware import Forward, Middleware, default_error_handler

__all__ = [
    'Application',
]


class Application:
    __slots__ = ('config', 'ConnectionClass', '_handlers', '_channels', '_runner')

    def __init__(self, apis: list[Api], middleware: list[Middleware] = None, *, config: Config = None,
                 connection: Type[Connection] = None):
        self.config = Config() if config is None else config
        self.ConnectionClass = connection
        if middleware is None:
            middleware = [
                default_error_handler,
            ]
        self._channels: dict[str, list[Connection]] = defaultdict(list)

        api = Api()
        for i in apis:
            api.update(i)

        self._handlers = api.compute()
        self._runner: Forward = self._run
        if middleware:
            for md in middleware:
                self._runner = partial(md, forward=self._runner)

    async def _run(self, handler: Handler) -> ActionLike | None:
        return await handler()

    def run(self, handler: Handler) -> Awaitable[ActionLike | None]:
        return self._runner(handler)

    def get_handlers_by_id(self, handler_id: int) -> list[HandlerItem] | HandlerItem | None:
        return self._handlers.get(handler_id)

    def get_handler_id(self, handler: Handler) -> int | None:
        return handler.handler_id

    def channels(self) -> list[str]:
        return list(self._channels.keys())

    def channel(self, name: str) -> Iterable[Connection]:
        return iter(self._channels.get(name, []))

    def attach_conn_to_channel(self, conn: Connection, channel: str) -> None:
        if conn not in self._channels[channel]:
            self._channels[channel].append(conn)

    def detach_conn_from_channel(self, conn: Connection, channel: str) -> None:
        try:
            self._channels[channel].remove(conn)
        except (KeyError, ValueError):
            pass

    def clear_channel(self, channel: str) -> None:
        self._channels[channel].clear()

    def clear_all_channels(self) -> None:
        self._channels.clear()

    def remove_conn_from_channels(self, conn: Connection) -> None:
        for channel_name in self.channels():
            self.detach_conn_from_channel(conn, channel_name)
