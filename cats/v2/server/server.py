import asyncio
import socket
import ssl
from contextlib import asynccontextmanager
from logging import getLogger
from typing import Callable

from tornado.iostream import IOStream
from tornado.tcpserver import TCPServer
from tornado.testing import bind_unused_port

from cats.errors import CatsError
from cats.utils import as_uint, to_uint
from cats.v2.connection import ConnType, Connection
from cats.v2.server.application import Application
from cats.v2.server.connection import Connection as ServerConnection

__all__ = [
    'Server',
]

from cats.v2.server.proxy import handle_with_proxy

logging = getLogger('CATS.Server')


class Server(TCPServer):
    __slots__ = ('app', 'port', 'connections')
    protocols: tuple[int, int] = 2, 2
    instances: list['Server'] = []

    def __init__(self, app: Application,
                 ssl_options: dict[str] | ssl.SSLContext | None = None,
                 max_buffer_size: int | None = None,
                 read_chunk_size: int | None = None):
        self.app: Application = app
        self.port: int | None = None
        self.connections: list[Connection] = []
        super().__init__(ssl_options=ssl_options, max_buffer_size=max_buffer_size, read_chunk_size=read_chunk_size)

    @classmethod
    async def broadcast(cls, channel: str, handler_id: int, data=None, message_id: int = None, compression: int = None,
                        *, headers=None, status: int = None):
        return await asyncio.gather(*(
            conn.send(handler_id, data, message_id, compression, headers=headers, status=status)
            for server in cls.running_servers()
            for conn in server.app.channel(channel)
        ))

    @classmethod
    async def conditional_broadcast(cls, channel: str, _filter: Callable[['Server', Connection], bool],
                                    handler_id: int, data=None, message_id: int = None,
                                    compression: int = None, *, headers=None, status: int = None):
        return await asyncio.gather(*(
            conn.send(handler_id, data, message_id, compression, headers=headers, status=status)
            for server in cls.running_servers()
            for conn in server.app.channel(channel)
            if _filter(server, conn)
        ))

    @handle_with_proxy
    async def handle_stream(self, stream: IOStream, address: tuple[str, int]) -> None:
        try:
            protocol_version = as_uint(await stream.read_bytes(4))
            if not self.protocols[0] <= protocol_version <= self.protocols[1]:
                await stream.write(to_uint(self.protocols[1], 4))
                stream.close(CatsError('Unsupported protocol version'))
                return
            await stream.write(bytes(4))
            async with self.create_connection(stream, address, protocol_version) as conn:
                conn: ServerConnection
                conn.debug(f'[INIT {address}]')
                await conn.init()
                await conn.start()
            conn.debug(f'[STOP {address}]')
        except self.app.config.stream_errors:
            pass

    @asynccontextmanager
    async def create_connection(self, stream: IOStream, address: tuple[str, int], protocol: int) -> ConnType:
        conn_class = self.app.ConnectionClass or ServerConnection
        conn = conn_class(stream, address, protocol, self.app.config, self.app)
        try:
            self.connections.append(conn)
            self.app.attach_conn_to_channel(conn, '__all__')
            async with conn:
                yield conn
        except (KeyboardInterrupt, asyncio.CancelledError, asyncio.TimeoutError):
            raise
        except self.app.config.ignore_errors:
            pass
        finally:
            self.app.remove_conn_from_channels(conn)
            try:
                self.connections.remove(conn)
            except ValueError:
                pass

    @classmethod
    def running_servers(cls) -> list['Server']:
        return [server for server in cls.instances if server.is_running]

    @property
    def is_running(self) -> bool:
        return self._started and not self._stopped

    async def shutdown(self, exc=None):
        for conn in self.connections:
            conn.close(exc=exc)

        self.app.clear_all_channels()
        self.connections.clear()
        logging.info('Shutting down TCP Server')
        self.stop()

    def start(self, num_processes: int = 1, max_restarts: int = None) -> None:
        super().start(num_processes, max_restarts)

    def bind_unused_port(self):
        sock, port = bind_unused_port()
        self.add_socket(sock)
        self.port = port
        logging.info(f'Starting server at 127.0.0.1:{port}')

    def bind(self, port: int, address: str = None, family: socket.AddressFamily = socket.AF_UNSPEC,
             backlog: int = 128, reuse_port: bool = False) -> None:
        super().bind(port, address, family, backlog, reuse_port)
        self.port = port
        logging.info(f'Starting server at {address}:{port}')

    def listen(self, port: int, address: str = "") -> None:
        super().listen(port, address)
        self.port = port
        logging.info(f'Starting server at {address}:{port}')

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        cls.instances.append(obj)
        return obj

    def __del__(self):
        self.instances.remove(self)
