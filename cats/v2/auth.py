import asyncio
import inspect
from collections import defaultdict
from typing import Any, Type

from cats.errors import CatsError
from cats.identity import IdentityObject
from cats.utils import require

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
    def __init__(self, methods: list[Type[AuthMethod] | str]):
        self.methods: dict[frozenset, list[Type[AuthMethod]]] = defaultdict(list)
        for method_path in methods:
            if isinstance(method_path, str):
                method = require(method_path, strict=True)
            else:
                method = method_path
            assert isinstance(method, type) and issubclass(method, AuthMethod)
            params = frozenset(inspect.signature(method.sign_in).parameters.keys())
            self.methods[frozenset(params)].append(method)

    async def sign_in(self, **kwargs) -> tuple[IdentityObject, Any, int | float | None]:
        prev_err = None
        for method in self.methods.get(frozenset(kwargs.keys()), []):
            try:
                return await method.sign_in(**kwargs)
            except (KeyboardInterrupt, asyncio.CancelledError, asyncio.TimeoutError):
                raise
            except Exception as exc:
                try:
                    raise exc from prev_err
                except BaseException as err:
                    prev_err = err
        raise AuthError('Unable to authenticate') from prev_err

    async def sign_in_silent(self, **kwargs) -> tuple[IdentityObject | None, Any | None, int | float | None]:
        try:
            return await self.sign_in(**kwargs)
        except AuthError:
            return None, None, None
