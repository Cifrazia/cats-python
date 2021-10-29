from typing import Any

from pytest import fixture, mark, raises

from cats.v2.auth import Auth, AuthError, AuthMethod
from cats.v2.identity import IdentityObject


@fixture
def auth(identity):
    class TestAuth(AuthMethod):
        @classmethod
        async def sign_in(cls, username: str, password: str) -> tuple[IdentityObject, Any, int | float | None]:
            if username == password:
                return identity(username), {'username': username, 'password': password}, None
            raise AuthError('Invalid credentials')

    return Auth([TestAuth, 'tests.data_auth.TestAuthToken'])


@mark.asyncio
async def test_auth_success(auth, identity):
    user, cred, time = await auth.sign_in(username='qwe', password='qwe')
    assert user == identity(username='qwe')
    assert cred == {'username': 'qwe', 'password': 'qwe'}
    assert time is None


@mark.asyncio
async def test_auth_invalid_arguments(auth):
    with raises(ValueError):
        await auth.sign_in(invalid='set of args')
    with raises(ValueError):
        await auth.sign_in_silent(invalid='set of args')


@mark.asyncio
async def test_auth_invalid_credentials(auth):
    with raises(AuthError):
        await auth.sign_in(token='Token')
    with raises(AuthError):
        await auth.sign_in(username='username', password='password')
    assert await auth.sign_in_silent(token='Token') == (None, None, None)
    assert await auth.sign_in_silent(username='username', password='password') == (None, None, None)
