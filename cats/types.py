from pathlib import Path
from typing import Any, AsyncIterable, Iterable, Type, Union

import ujson

from cats.errors import ProtocolError

__all__ = [
    'Bytes',
    'BytesGen',
    'BytesAsyncGen',
    'BytesAnyGen',
    'NULL',
    'Byte',
    'Json',
    'File',
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

T_Headers = Union[dict[str, Any], 'Headers']


class Headers(dict):
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
        return ujson.encode(self, ensure_ascii=False,
                            escape_forward_slashes=False,
                            encode_html_chars=True).encode('utf-8')

    @classmethod
    def decode(cls, headers: Bytes) -> 'Headers':
        return cls(ujson.decode(headers.decode('utf-8') or '{}') or {})
