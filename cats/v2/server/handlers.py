import asyncio
from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger
from random import random
from time import time
from typing import Awaitable, Type

from cats.errors import ActionError
from cats.identity import Identity, IdentityObject
from cats.plugins import Form, Scheme, SchemeTypes, scheme_json, scheme_load
from cats.types import Json, List, T_Headers
from cats.v2.action import Action, ActionLike, InputAction
from cats.v2.codecs import T_FILE, T_JSON

__all__ = [
    'HandlerItem',
    'Api',
    'Handler',
]

logging = getLogger('CATS')


@dataclass
class HandlerItem:
    id: int
    name: str
    handler: Type['Handler']
    version: int | None = None
    end_version: int | None = None


class Api:
    __slots__ = ('_handlers',)

    def __init__(self):
        self._handlers: dict[int, list[HandlerItem]] = defaultdict(list)

    def register(self, handler: HandlerItem):
        if handler in self._handlers[handler.id]:
            return

        assert handler.version is None or handler.end_version is None or handler.version <= handler.end_version, \
            f'Invalid version range for handler {handler.id}: [{handler.version}..{handler.end_version}]'

        if handler.version is not None or handler.end_version is not None:
            assert handler.version is not None, f'Initial version is not provided for {handler}'

            try:
                last_handler = self._handlers[handler.id][-1]
                assert last_handler.version is not None or last_handler.end_version is not None, \
                    f'Attempted to add versioned {handler} to wildcard'

                if last_handler.end_version is not None:
                    assert last_handler.end_version < handler.version, \
                        f'Handler {handler} overlap {last_handler} version'
                else:
                    assert last_handler.version < handler.version, \
                        f'Handler {handler} overlap {last_handler} version'
                    last_handler.end_version = handler.version - 1
            except IndexError:
                pass
        self._handlers[handler.id].append(handler)

    @property
    def handlers(self):
        return self._handlers

    def update(self, app: 'Api'):
        self._handlers.update(app.handlers)

    def compute(self) -> dict[int, HandlerItem | list[HandlerItem]]:
        result = {}
        for handler_id, handler_list in self._handlers.items():
            if not handler_list:
                continue

            elif len(handler_list) == 1 and handler_list[0].version is None and handler_list[0].end_version is None:
                result[handler_id] = handler_list[0]
            else:
                result[handler_id] = handler_list

        return result


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
        self.action = action

    # noinspection PyShadowingBuiltins
    def __init_subclass__(cls, /, api: Api = None, id: int = None,
                          name: str = None, version: int = None, end_version: int = None):
        # abstract
        if api is None:
            return

        assert id is not None

        assert cls.Loader is None or (isinstance(cls.Loader, type) and issubclass(cls.Loader, SchemeTypes)), \
            'Handler.Loader must be subclass of BaseSerializer | BaseModel'
        assert cls.Dumper is None or (isinstance(cls.Dumper, type) and issubclass(cls.Dumper, SchemeTypes)), \
            'Handler.Dumper must be subclass of BaseSerializer | BaseModel'

        assert not (cls.require_auth is False and cls.require_models is not None), \
            f'{cls!s}.require_auth is False and {cls!s}.require_models is not None'

        api.register(HandlerItem(id, name, cls, version, end_version))  # noqa, pycharm bug
        cls.handler_id = id

    @property
    def conn(self):
        return self.action.conn

    async def __call__(self) -> ActionLike | None:
        st = time()
        res = await self.prepare()
        if not isinstance(res, Action):
            res = await self.handle()
        if self.fix_exec_time is not None:
            sp = time() - st
            if sp < self.fix_exec_time:
                await asyncio.sleep(self.fix_exec_time - sp - random() / 20)
            elif sp > self.fix_exec_time + 0.2:
                logging.warning(f'{type(self).__qualname__} run time exceeded fixed: {sp:.3f}/{self.fix_exec_time:.3f}')
        return res

    async def prepare(self) -> None:
        """Called before handler() method"""
        try:
            self._check_before_recv()
        except self.action.conn.conf.stream_errors:
            raise
        except BaseException:
            await self.action.dump_data(self.action.data_len)
            raise
        else:
            await self.action.recv_data()
            self._check_after_recv()

    async def handle(self):
        raise NotImplementedError

    async def json_load(self, *, many: bool = False, plain: bool = False) -> Json | Form:
        if self.action.data_type != T_JSON:
            raise TypeError('Unsupported data type. Expected JSON')

        data = self.action.data
        if self.Loader is None:
            return data
        if many is None:
            many = isinstance(data, List)
        return scheme_load(self.Loader, data, many=many, plain=plain)

    async def json_dump(self, data, *, headers: T_Headers = None,
                        status: int = 200, many: bool = None, plain: bool = False) -> ActionLike:
        if self.Dumper is not None:
            if not plain:
                if many is None:
                    many = isinstance(data, List)
                data = scheme_json(self.Dumper, data, many=many, plain=False)
                return Action(data=data, headers=headers, status=status, encoded=T_JSON)
            elif not isinstance(data, self.Dumper):
                raise TypeError('Resulted plain data does not match Dumper')
        return Action(data=data, headers=headers, status=status)

    @property
    def identity(self) -> Identity | IdentityObject | None:
        return self.action.conn.identity

    def ask(self, data=None, data_type: int = None, compression: int = None, *,
            headers: T_Headers = None, status: int = 200,
            bypass_limit=False, bypass_count=False, timeout=None) -> Awaitable['InputAction']:
        return self.action.ask(data, data_type=data_type, compression=compression,
                               headers=headers, status=status,
                               bypass_limit=bypass_limit, bypass_count=bypass_count, timeout=timeout)

    def _check_before_recv(self):
        self._check_data_type()
        self._check_data_len()
        self._check_models()
        self._check_auth()
        self._check_file_size()
        self._check_file_total_size()
        self._check_file_amount()

    def _check_after_recv(self):
        self._check_data_len()

    def _check_data_type(self):
        if (types := self.data_type) is None:
            return
        if isinstance(types, int):
            types = (types,)
        if self.action.data_type not in types:
            raise ActionError('Received payload type is not acceptable', action=self.action)

    def _check_data_len(self):
        if (x := self.action.data_len) is None:
            return
        min_len = self.min_data_len
        max_len = self.max_data_len
        if min_len is not None and x < min_len:
            raise ActionError(f'Received payload data size is less than allowed [{min_len}]', action=self.action)
        if max_len is not None and max_len < x:
            raise ActionError(f'Received payload data size is more than allowed [{max_len}]', action=self.action)

    def _check_models(self):
        model = self.identity.model_name if self.identity else None
        if self.block_models is not None and model in self.block_models:
            raise ActionError(f'Model {model} is forbidden', action=self.action)
        if self.require_models is not None and model not in self.require_models:
            raise ActionError(f'Model {model} is required', action=self.action)

    def _check_auth(self):
        if self.require_auth is None:
            return
        if self.require_auth ^ self.action.conn.signed_in:
            reason = 'required' if self.require_auth else 'forbidden'
            raise ActionError(f'Authentication is {reason}', action=self.action)

    def _check_file_size(self):
        if self.action.data_type != T_FILE:
            return
        for i, file in enumerate(self.action.headers.get('Files', [])):
            x = int(file['size'])
            self._check_min_max(x, self.min_file_size, self.max_file_size, f'File[{i}].size')

    def _check_file_total_size(self):
        if self.action.data_type != T_FILE:
            return

        if self.action.data_len is not None:
            x = self.action.data_len
        else:
            x = sum(file['size'] for file in self.action.headers.get('Files', []))

        self._check_min_max(x, self.min_file_total_size, self.max_file_total_size, '∑ File[n].size')

    def _check_file_amount(self):
        if self.action.data_type != T_FILE:
            return

        x = len(self.action.headers.get('Files', []))
        self._check_min_max(x, self.min_file_amount, self.max_file_amount, 'File amount')

    def _check_min_max(self, size: int, min_size: int | None, max_size: int | None, part: str) -> None:
        if min_size is not None and size < min_size:
            raise ActionError(f'Received {part} is less than allowed [{min_size}]', action=self.action)
        if max_size is not None and max_size < size:
            raise ActionError(f'Received {part} is more than allowed [{max_size}]', action=self.action)
