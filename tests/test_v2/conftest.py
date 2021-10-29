import asyncio
import logging
import platform

from pytest import fixture

from cats.v2 import Auth, Handshake, SHA256TimeHandshake
from cats.v2.server import Api, Middleware, default_error_handler

logging.basicConfig(level='DEBUG', force=True)


@fixture(scope='session')
def event_loop():
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    yield asyncio.new_event_loop()


@fixture(scope='session')
def cats_handshake() -> Handshake:
    yield SHA256TimeHandshake(b'secret_key', 1)


@fixture(scope='session')
def cats_apis() -> list[Api]:
    from tests.test_v2.handlers import api
    yield [
        api,
    ]


@fixture(scope='session')
def cats_middleware() -> list[Middleware]:
    return [
        default_error_handler,
    ]


@fixture(scope='session')
def cats_api_version() -> int:
    yield 1


@fixture(scope='session')
def cats_auth() -> Auth | None:
    yield None
