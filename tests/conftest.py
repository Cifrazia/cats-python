import asyncio
import logging
import platform
from typing import List

from pytest import fixture, mark
from tornado.iostream import IOStream
from tornado.tcpclient import TCPClient

import cats.server
import cats.server.middleware
from tests.utils import init_cats_conn

logging.basicConfig(level='DEBUG', force=True)


@fixture(scope='session')
def event_loop():
    if platform.system() == 'Windows':
        # noinspection PyUnresolvedReferences
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop()


@fixture(scope='session')
def cats_api_list() -> List[cats.server.Api]:
    from tests.handlers import api
    return [
        api,
    ]


@fixture(scope='session')
def cats_middleware() -> List[cats.server.middleware.Middleware]:
    return [
        cats.server.middleware.default_error_handler,
    ]


@fixture(scope='session')
def cats_app(cats_api_list, cats_middleware) -> cats.server.Application:
    return cats.server.Application(cats_api_list, cats_middleware)


@fixture(scope='session')
def cats_handshake() -> cats.Handshake:
    return cats.SHA256TimeHandshake(b'secret_key', 1)


@fixture(scope='session')
@mark.asyncio
async def cats_server(cats_app, cats_handshake) -> cats.server.Server:
    cats_server = cats.server.Server(app=cats_app, handshake=cats_handshake, debug=True)
    cats_server.bind_unused_port()
    cats_server.start(1)
    yield cats_server
    await cats_server.shutdown()


@fixture
@mark.asyncio
async def cats_client_stream(cats_server) -> IOStream:
    tcp_client = TCPClient()
    stream = await tcp_client.connect('127.0.0.1', cats_server.port)
    yield stream
    stream.close()


@fixture
@mark.asyncio
async def cats_conn(cats_client_stream, cats_server, cats_app) -> cats.server.Connection:
    conn = await init_cats_conn(cats_client_stream, '127.0.0.1', cats_server.port, cats_app, 1, cats_server.handshake)
    yield conn
    conn.close()
