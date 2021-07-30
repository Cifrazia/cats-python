import asyncio
import socket
import ssl
import time
from logging import getLogger
from typing import Any, Optional, Union

from tornado.iostream import IOStream, StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.testing import bind_unused_port

from cats.handshake import Handshake
from cats.server.app import Application
from cats.server.conn import ConnType, Connection

__all__ = [
    'Server',
]

logging = getLogger('CATS.Server')


class Server(TCPServer):
    __slots__ = ('app', 'handshake', 'port', 'connections', 'debug')
    CONNECTION: ConnType = Connection
    instance: 'Server'

    def __new__(cls, *args, **kwargs):
        try:
            return cls.instance
        except AttributeError:
            cls.instance = super().__new__(cls)
            return cls.instance

    def __init__(self, app: Application, handshake: Handshake = None,
                 ssl_options: Optional[Union[dict[str, Any], ssl.SSLContext]] = None,
                 max_buffer_size: Optional[int] = None, read_chunk_size: Optional[int] = None,
                 debug: bool = False) -> None:
        self.app = app
        self.handshake = handshake
        self.port: Optional[int] = None
        self.connections: list[Connection] = []
        self.debug = debug
        super().__init__(ssl_options, max_buffer_size, read_chunk_size)

    # TCP Connection entry point
    async def handle_stream(self, stream: IOStream, address: tuple[str, int]) -> None:
        conn = None
        try:
            self.debug and logging.debug(f'[INIT {address}]')
            conn = await self.init_connection(stream, address)
            conn.attach_to_channel('__all__')
            self.connections.append(conn)
            await conn.start()
        except (KeyboardInterrupt, asyncio.CancelledError, asyncio.TimeoutError):
            raise
        except Exception as err:
            if isinstance(err, StreamClosedError):
                err = None
            if conn is not None:
                conn.close(exc=err)
            stream.close(err)
        else:
            stream.close()
        finally:
            if conn is not None:
                self.app.remove_conn_from_channels(conn)
                try:
                    self.connections.remove(conn)
                except (KeyError, ValueError):
                    pass

    async def init_connection(self, stream: IOStream, address: tuple[str, int]) -> Connection:
        api_version = int.from_bytes(await stream.read_bytes(4), 'big', signed=False)
        self.debug and logging.debug(f'[RECV {address}] API Version: {api_version}')

        current_time = time.time_ns() // 1000000
        await stream.write(current_time.to_bytes(8, 'big', signed=False))
        self.debug and logging.debug(f'[SEND {address}] Server time: {current_time}')

        conn = self.CONNECTION(stream, address, api_version, self.app, debug=self.debug)
        if self.handshake is not None:
            await self.handshake.validate(self, conn)

        await conn.init()
        return conn

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

    def start(self, num_processes: Optional[int] = 1, max_restarts: Optional[int] = None) -> None:
        super().start(num_processes, max_restarts)

    def bind_unused_port(self):
        sock, port = bind_unused_port()
        self.add_socket(sock)
        self.port = port

    def bind(self, port: int, address: Optional[str] = None, family: socket.AddressFamily = socket.AF_UNSPEC,
             backlog: int = 128, reuse_port: bool = False) -> None:
        super().bind(port, address, family, backlog, reuse_port)
        self.port = port

    def listen(self, port: int, address: str = "") -> None:
        super().listen(port, address)
        self.port = port
