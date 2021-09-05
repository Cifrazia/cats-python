import asyncio
import logging
import platform

import uvloop
from pytest import fixture

from cats.v2 import Handshake, SHA256TimeHandshake
from cats.v2.server import Api

logging.basicConfig(level='DEBUG', force=True)


@fixture(scope='session')
def event_loop():
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        uvloop.install()
    return asyncio.get_event_loop()


@fixture(scope='session')
def cats_handshake() -> Handshake:
    return SHA256TimeHandshake(b'secret_key', 1)


@fixture(scope='session')
def cats_apis() -> list[Api]:
    from tests.handlers import api
    return [
        api,
    ]
