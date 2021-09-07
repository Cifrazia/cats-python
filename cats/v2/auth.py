import asyncio
from typing import Any, Type

from cats.identity import IdentityObject
from cats.utils import require

__all__ = [
    'AuthError',
    'AuthMethod',
    'Auth',
]


class AuthError(ValueError):
    pass


class AuthMethod:
    @classmethod
    async def sign_in(cls, **kwargs) -> tuple[IdentityObject, Any]:
        """
        Returns tuple[identity, credentials]. Consider to use returned credentials, instead of passed in
        :raises AuthError:
        """
        raise NotImplementedError


class Auth:
    def __init__(self, methods: list[Type[AuthMethod] | str]):
        self.methods: list[Type[AuthMethod]] = []
        for method_path in methods:
            if isinstance(method_path, str):
                method = require(method_path, strict=True)
            else:
                method = method_path
            assert isinstance(method, type) and issubclass(method, AuthMethod)
            self.methods.append(method)

    async def sign_in(self, **kwargs) -> tuple[IdentityObject, Any]:
        for method in self.methods:
            try:
                return await method.sign_in(**kwargs)
            except (KeyboardInterrupt, asyncio.CancelledError, asyncio.TimeoutError):
                raise
            except (AuthError, TypeError):
                pass
        raise AuthError('Unable to authenticate')

    async def sign_in_silent(self, **kwargs) -> tuple[IdentityObject | None, Any | None]:
        try:
            return await self.sign_in(**kwargs)
        except AuthError:
            return None, None
