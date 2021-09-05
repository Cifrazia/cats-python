import warnings
from typing import Type

from pytest import PytestWarning, fixture, mark

from cats.test_utils.client import Connection
from cats.v2 import Config, Handshake
from cats.v2.server import Api, Application, Connection as ServerConnection, Middleware, Server, default_error_handler

__all__ = [
    'cats_handshake',
    'cats_apis',
    'cats_middleware',
    'cats_config',
    'cats_server_connection',
    'cats_api_version',
    'cats_app',
    'cats_server',
    'cats_conn',
]


@fixture(scope='session')
def cats_handshake() -> Handshake:
    raise NotImplementedError('Please, overwrite "cats_handshake" fixture in order for CATS tests to work')


@fixture(scope='session')
def cats_apis() -> list[Api]:
    raise NotImplementedError('Please, overwrite "cats_apis" fixture in order for CATS tests to work')


@fixture(scope='session')
def cats_middleware() -> list[Middleware]:
    warnings.warn(PytestWarning('You may want to overwrite "cats_middleware" fixture'))
    return [
        default_error_handler,
    ]


@fixture(scope='function')
def cats_api_version() -> int:
    warnings.warn(PytestWarning('You may want to overwrite "cats_api_version" fixture'))
    return 1


@fixture(scope='session')
def cats_config(cats_handshake) -> Config:
    return Config(
        idle_timeout=10.0,
        input_timeout=10.0,
        debug=True,
        handshake=cats_handshake,
    )


@fixture(scope='session')
def cats_server_connection() -> Type[ServerConnection] | None:
    return None


@fixture(scope='session')
def cats_app(cats_apis, cats_middleware, cats_config, cats_server_connection):
    return Application(
        apis=cats_apis,
        middleware=cats_middleware,
        config=cats_config,
        connection=cats_server_connection,
    )


@fixture(scope='session')
@mark.asyncio
async def cats_server(cats_app) -> Server:
    """
    Runs an TCP server for each module and return port
    :return:
    """

    server = Server(cats_app)
    server.bind_unused_port()
    server.start(1)
    yield server
    await server.shutdown()


@fixture
@mark.asyncio
async def cats_conn(cats_config, cats_api_version, cats_server) -> Connection:
    """
    Return TCP connection to test TCP server
    """
    conn = Connection(cats_config, cats_api_version)
    await conn.connect('127.0.0.1', cats_server.port, timeout=5)
    async with conn:
        yield conn
