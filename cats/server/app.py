from collections import defaultdict
from typing import DefaultDict, Iterable, Optional, Union

from cats.server.conn import Connection
from cats.server.handlers import Api, Handler, HandlerItem
from cats.server.middleware import Middleware, default_error_handler

__all__ = [
    'Application',
]


class Application:
    __slots__ = ('_handlers', '_middleware', '_channels', 'idle_timeout', 'input_timeout')
    INPUT_LIMIT: int = 3

    def __init__(self, apis: list[Api], middleware: list[Middleware] = None, *,
                 idle_timeout: Union[int, float] = None, input_timeout: Union[int, float] = None):
        if middleware is None:
            middleware = [
                default_error_handler,
            ]

        self._middleware = middleware
        self._channels: DefaultDict[str, list[Connection]] = defaultdict(list)
        self.idle_timeout: Union[int, float] = idle_timeout or 0
        self.input_timeout: Union[int, float] = input_timeout or 0

        api = Api()
        for i in apis:
            api.update(i)

        self._handlers = api.compute()

    def get_handlers_by_id(self, handler_id: int) -> Optional[Union[list[HandlerItem], HandlerItem]]:
        return self._handlers.get(handler_id)

    def get_handler_id(self, handler: Handler) -> Optional[int]:
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

    @property
    def middleware(self) -> Iterable[Middleware]:
        return iter(self._middleware)
