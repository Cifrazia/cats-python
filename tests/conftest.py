import asyncio
import logging
import platform

from pytest import fixture, mark

from cats.v2 import Config, Handshake, SHA256TimeHandshake
from cats.v2.client import Connection
from cats.v2.server import Api, Application, Middleware, Server, default_error_handler

logging.basicConfig(level='DEBUG', force=True)


@fixture(scope='session')
def event_loop():
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop()


@fixture(scope='session')
def cats_api_list() -> list[Api]:
    from tests.handlers import api
    return [
        api,
    ]


@fixture(scope='session')
def cats_middleware() -> list[Middleware]:
    return [
        default_error_handler,
    ]


@fixture(scope='session')
def cats_config(cats_handshake) -> Config:
    return Config(
        handshake=cats_handshake,
        debug=True,
    )


@fixture(scope='session')
def cats_app(cats_api_list, cats_middleware, cats_config) -> Application:
    return Application(cats_api_list, cats_middleware, config=cats_config)


@fixture(scope='session')
def cats_handshake() -> Handshake:
    return SHA256TimeHandshake(b'secret_key', 1)


@fixture(scope='session')
@mark.asyncio
async def cats_server(cats_app, cats_handshake) -> Server:
    cats_server = Server(app=cats_app)
    cats_server.bind_unused_port()
    cats_server.start(1)
    yield cats_server
    await cats_server.shutdown()


@fixture
@mark.asyncio
async def cats_conn(cats_server, cats_config) -> Connection:
    conn = Connection(cats_config, 1)
    await conn.connect('127.0.0.1', cats_server.port)
    async with conn:
        yield conn
