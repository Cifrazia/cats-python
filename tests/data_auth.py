from typing import Any

from cats.v2.auth import AuthError, AuthMethod
from cats.v2.identity import IdentityObject


class TestAuthToken(AuthMethod):
    @classmethod
    async def sign_in(cls, token: str) -> tuple[IdentityObject, Any, int | float | None]:
        raise AuthError('Invalid credentials')
