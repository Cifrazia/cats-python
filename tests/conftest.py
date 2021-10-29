# from django.conf import settings
#
# settings.configure()
# settings.TESTING = True
import asyncio
import logging
import platform
from unittest.mock import MagicMock

from pytest import fixture
from pytest_mock import MockerFixture

from cats.v2 import Auth, Handshake, SHA256TimeHandshake
from cats.v2.server import Api

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
def cats_auth() -> Auth | None:
    yield None


@fixture
def no_sleep(mocker: MockerFixture) -> MagicMock:
    yield mocker.patch('asyncio.sleep')


@fixture
def identity():
    from dataclasses import asdict, dataclass

    from cats.v2.identity import Identity

    @dataclass
    class User(Identity):
        username: str
        model_name = 'user'

        @property
        def id(self) -> int:
            return int.from_bytes(self.username.encode('utf-8'), 'big')

        @property
        def sentry_scope(self) -> dict:
            return asdict(self)

    yield User
    if User in Identity.identity_list:
        Identity.identity_list.remove(User)
