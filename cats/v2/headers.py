from typing import TypeAlias

from cats.v2.errors import MalformedHeaders
from cats.v2.scheme import JSON

__all__ = [
    'Header',
    'Headers',
    'T_Headers',
]


class Header:
    offset = 'Offset'
    skip = 'Skip'


class Headers(dict):
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        v = self._convert(*args, **kwargs)
        if (offset := v.get(Header.offset, None)) and (not isinstance(offset, int) or offset < 0):
            raise MalformedHeaders('Invalid "Offset" header', headers=v)
        if (skip := v.get(Header.skip, None)) and (not isinstance(skip, int) or skip < 0):
            raise MalformedHeaders('Invalid "Skip" header', headers=v)
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

    # def encode(self, scheme: type[BaseScheme]) -> bytes:
    def encode(self) -> bytes:
        return JSON().dumps(self)

    @classmethod
    # def decode(cls, headers: str | bytes, scheme: type[BaseScheme]) -> 'Headers':
    def decode(cls, headers: str | bytes) -> 'Headers':
        try:
            headers = JSON().loads(headers)
        except ValueError:
            headers = None
        return cls(headers or {})


T_Headers: TypeAlias = Headers | dict[str]
