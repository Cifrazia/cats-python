from pathlib import Path
from types import GeneratorType
from typing import AsyncIterable, Iterable, TypeAlias

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
    'File',
    'List',
    'Data',
    'Missing',
    'MISSING',
    'QuerySet',
    'Model',
]

Bytes: TypeAlias = bytes | bytearray
BytesGen: TypeAlias = Iterable[Bytes]
BytesAsyncGen: TypeAlias = AsyncIterable[Bytes]
BytesAnyGen: TypeAlias = BytesGen | BytesAsyncGen

Byte: TypeAlias = Bytes
File: TypeAlias = Path | str
List: TypeAlias = list | tuple | set | frozenset | GeneratorType | QuerySet
Data: TypeAlias = int | float | bool | str | list | dict | None
Data: TypeAlias = Data | list[Data] | dict[str, Data]


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
