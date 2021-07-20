from pathlib import Path
from types import GeneratorType
from typing import Any, AsyncIterable, Iterable, Type, Union

import orjson

from cats.errors import ProtocolError

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
    'NULL',
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

Bytes = Union[bytes, bytearray, memoryview]
BytesGen = Iterable[Bytes]
BytesAsyncGen = AsyncIterable[Bytes]
BytesAnyGen = Union[BytesGen, BytesAsyncGen]

NULL = type('NULL', (object,), {})
Byte = Bytes
Json = Union[str, int, float, dict, list, bool, type(None), Type[NULL]]
File = Union[Path, str]
List = (list, tuple, set, GeneratorType, QuerySet)

T_Headers = Union[dict[str, Any], 'Headers']


class Missing(str):
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
            raise ProtocolError('Invalid offset header')
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
        return orjson.dumps(self)

    @classmethod
    def decode(cls, headers: Bytes) -> 'Headers':
        try:
            headers = orjson.loads(headers)
        except ValueError:  # + UnicodeDecodeError
            headers = None
        return cls(headers or {})
