from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger
from typing import Awaitable, Type

from cats.identity import Identity, IdentityObject
from cats.plugins import Form, Scheme
from cats.types import Json, T_Headers
from cats.v2.action import Action, ActionLike, InputAction
from cats.v2.server import Connection

__all__ = [
    'HandlerItem',
    'Api',
    'Handler',
]

logging = getLogger('CATS')


@dataclass
class HandlerItem(object):
    id: int
    name: str
    handler: Type['Handler']
    version: int | None = None
    end_version: int | None = None


class Api:
    __slots__ = ('_handlers',)

    def __init__(self):
        self._handlers: dict[int, list[HandlerItem]] = defaultdict(list)

    def register(self, handler: HandlerItem) -> None: ...

    @property
    def handlers(self) -> dict[int, list[HandlerItem]]: ...

    def update(self, app: 'Api') -> None: ...

    def compute(self) -> dict[int, HandlerItem | list[HandlerItem]]: ...


class Handler:
    __slots__ = ('action',)
    handler_id: int

    Loader: Scheme | None = None
    Dumper: Scheme | None = None

    data_type: int | tuple[int] | None = None
    min_data_len: int | None = None
    max_data_len: int | None = None
    block_models: tuple[str] | None = None
    require_models: tuple[str] | None = None
    require_auth: bool | None = None
    min_file_size: int | None = None
    max_file_size: int | None = None
    min_file_total_size: int | None = None
    max_file_total_size: int | None = None
    min_file_amount: int | None = None
    max_file_amount: int | None = None
    fix_exec_time: int | float | None = None

    def __init__(self, action: Action):
        self.action: Action = action

    def __init_subclass__(cls, /, api: Api = None, id: int = None,
                          name: str = None, version: int = None, end_version: int = None): ...

    @property
    def conn(self) -> Connection:
        return self.action.conn

    async def __call__(self) -> ActionLike | None: ...

    async def prepare(self) -> None: ...

    async def handle(self):
        raise NotImplementedError

    async def json_load(self, *, many: bool = False, plain: bool = False) -> Json | Form: ...

    async def json_dump(self, data, *, headers: T_Headers = None,
                        status: int = 200, many: bool = None, plain: bool = False) -> ActionLike: ...

    @property
    def identity(self) -> Identity | IdentityObject | None: ...

    def ask(self, data=None, data_type: int = None, compression: int = None, *,
            headers: T_Headers = None, status: int = 200,
            bypass_limit=False, bypass_count=False, timeout=None) -> Awaitable['InputAction']: ...

    def _check_before_recv(self) -> None: ...

    def _check_after_recv(self) -> None: ...

    def _check_data_type(self) -> None: ...

    def _check_data_len(self) -> None: ...

    def _check_models(self) -> None: ...

    def _check_auth(self) -> None: ...

    def _check_file_size(self) -> None: ...

    def _check_file_total_size(self) -> None: ...

    def _check_file_amount(self) -> None: ...

    def _check_min_max(self, size: int, min_size: int | None, max_size: int | None, part: str) -> None: ...
