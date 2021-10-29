import asyncio
import inspect
from collections import defaultdict
from typing import Any

import sentry_sdk

from cats.v2.errors import CatsError
from cats.v2.identity import IdentityObject
from cats.v2.utils import require

__all__ = [
    'AuthError',
    'AuthMethod',
    'Auth',
]


class AuthError(CatsError, RuntimeError):
    pass


class AuthMethod:
    @classmethod
    async def sign_in(cls, **kwargs) -> tuple[IdentityObject, Any, int | float | None]:
        """
        Returns tuple[identity, credentials]. Consider to use returned credentials, instead of passed in
        :raises AuthError:
        """
        raise NotImplementedError


class Auth:
    def __init__(self, methods: list[type[AuthMethod] | str]):
        self.methods: dict[frozenset, list[type[AuthMethod]]] = defaultdict(list)
        for method_path in methods:
            if isinstance(method_path, str):
                method = require(method_path, strict=True)
            else:
                method = method_path
            assert isinstance(method, type) and issubclass(method, AuthMethod)
            params = frozenset(inspect.signature(method.sign_in).parameters.keys())
            self.methods[frozenset(params)].append(method)

    async def sign_in(self, **kwargs) -> tuple[IdentityObject, Any, int | float | None]:
        sentry_sdk.add_breadcrumb(message=f'Attempt to sign in', data=kwargs)
        error = None
        args = frozenset(kwargs.keys())
        if args not in self.methods:
            raise ValueError('Invalid credentials arguments')
        for method in self.methods[args]:
            try:
                return await method.sign_in(**kwargs)
            except (KeyboardInterrupt, asyncio.CancelledError, asyncio.TimeoutError):
                raise
            except Exception as err:
                err.__cause__ = error
                error = err
        raise AuthError('Unable to authenticate') from error

    async def sign_in_silent(self, **kwargs) -> tuple[IdentityObject | None, Any | None, int | float | None]:
        try:
            return await self.sign_in(**kwargs)
        except AuthError:
            return None, None, None
