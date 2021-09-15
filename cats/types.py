from pathlib import Path
from types import GeneratorType
from typing import AsyncIterable, Iterable, TypeAlias

import ujson

from cats.errors import MalformedHeadersError

try:
    from django.db.models import QuerySet, Model
except ImportError:
    QuerySet = type('QuerySet', (list,), {})
    Model = type('Model', (list,), {})

__all__ = [
    'Bytes',
    'BytesGen',
    'BytesAsyncGen',
    'BytesAnyGen',
    'Byte',
    'Json',
    'File',
    'List',
    'Missing',
    'MISSING',
    'QuerySet',
    'Model',
    'T_Headers',
    'Headers',
]

Bytes: TypeAlias = bytes | bytearray | memoryview
BytesGen: TypeAlias = Iterable[Bytes]
BytesAsyncGen: TypeAlias = AsyncIterable[Bytes]
BytesAnyGen: TypeAlias = BytesGen | BytesAsyncGen

Byte: TypeAlias = Bytes
Json: TypeAlias = str | int | float | dict | list | bool | None
File: TypeAlias = Path | str
List = list | tuple | set | GeneratorType | QuerySet


class Missing(str):
    """
    Custom Missing type is required for Pydantic to work properly. IDK
    """
    __slots__ = ()

    def __init__(self):
        super().__init__()

    def __eq__(self, other):
        return isinstance(other, Missing)

    def __bool__(self):
        return False


MISSING = Missing()


class Headers(dict):
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        v = self._convert(*args, **kwargs)
        if (offset := v.get('offset', None)) and (not isinstance(offset, int) or offset < 0):
            raise MalformedHeadersError('Invalid offset header', headers=v)
        super().__init__(v)

    @classmethod
    def _key(cls, key: str) -> str:
        return key.replace(' ', '-').title()

    def __getitem__(self, item):
        return super().__getitem__(self._key(item))

    def __setitem__(self, key, value):
        return super().__setitem__(self._key(key), value)

    def __delitem__(self, key):
        return super().__delitem__(self._key(key))

    def __contains__(self, item):
        return super().__contains__(self._key(item))

    @classmethod
    def _convert(cls, *args, **kwargs):
        return {cls._key(k): v for k, v in dict(*args, **kwargs).items() if isinstance(k, str)}

    def update(self, *args, **kwargs) -> None:
        super().update(self._convert(*args, **kwargs))

    def encode(self) -> bytes:
        return ujson.dumps(self, ensure_ascii=False, escape_forward_slashes=False).encode('utf-8')

    @classmethod
    def decode(cls, headers: Bytes) -> 'Headers':
        try:
            headers = ujson.loads(headers)
        except ValueError:  # + UnicodeDecodeError
            headers = None
        return cls(headers or {})


T_Headers: TypeAlias = Headers | dict[str]
