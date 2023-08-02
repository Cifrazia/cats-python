from typing import Type, TypeAlias, TypeVar

import ujson

from cats.errors import UnsupportedSchemeError
from cats.types import Json, Missing, Model, QuerySet

try:
    from rest_framework.serializers import BaseSerializer
except ImportError:
    BaseSerializer = type('BaseSerializer', (object,), {})

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = type('BaseModel', (object,), {})

__all__ = [
    'QuerySet',
    'Model',
    'BaseSerializer',
    'BaseModel',
    'Scheme',
    'SchemeTypes',
    'Form',
    'without_missing',
    'scheme_load',
    'scheme_dump',
    'scheme_json',
]

Scheme: TypeAlias = Type[BaseModel] | Type[BaseSerializer]
SchemeTypes = BaseModel, BaseSerializer
PydanticModel = TypeVar('PydanticModel', bound=BaseModel)
DRFModel = TypeVar('DRFModel', bound=BaseSerializer)
Form: TypeAlias = PydanticModel | DRFModel


def without_missing(obj) -> Json | None:
    if _items := getattr(obj, 'items', None):
        return {k: without_missing(v) for k, v in _items() if not isinstance(v, Missing)}
    if isinstance(obj, (list, set, tuple)):
        return [without_missing(i) for i in obj if not isinstance(i, Missing)]
    if isinstance(obj, Missing):
        return None
    return obj


class DRF:
    @classmethod
    def load(cls, s: Type[BaseSerializer], data: Json, *, many: bool = False, plain: bool = False) -> Json | DRFModel:
        f = s(data=data, many=many)
        f.is_valid(raise_exception=True)
        if plain:
            return f
        return without_missing(f.validated_data)

    @classmethod
    def dump(cls, s: Type[BaseSerializer], data: Json | DRFModel, *, many: bool = False, plain: bool = False) -> Json:
        if plain:
            assert isinstance(data, s)
            return data.data
        return s(data, many=many).data

    @classmethod
    def json(cls, s: Type[BaseSerializer], data: Json | DRFModel, *, many: bool = False, plain: bool = False) -> bytes:
        obj = cls.dump(s, data, many=many, plain=plain)
        dump: str = ujson.dumps(obj, ensure_ascii=False, escape_forward_slashes=False)
        return dump.encode('utf-8')


class Pydantic:
    @classmethod
    def load(cls, s: Type[BaseModel], data: Json, *, many: bool = False, plain: bool = False) -> Json | PydanticModel:
        if many:
            return [cls.load(s, i, many=False, plain=plain) for i in data]

        res = s.model_validate(data)
        if plain:
            return res

        return without_missing(res.model_dump())

    @classmethod
    def dump(cls, s: Type[BaseModel], data: Json | PydanticModel, *, many: bool = False, plain: bool = False) -> Json:
        if many:
            return [cls.dump(s, i, many=False, plain=plain) for i in data]

        if plain:
            assert isinstance(data, s)
        elif isinstance(data, (QuerySet, Model)):
            s.model_config['from_attributes'] = True
            data = s.model_validate(data)
        else:
            s.model_config['from_attributes'] = False
            data = s.model_validate(data)
        return data.model_dump()

    @classmethod
    def json(cls, s: Type[BaseModel], data: Json | PydanticModel, *, many: bool = False, plain: bool = False) -> bytes:
        if many:
            return b'[' + b','.join(cls.json(s, i, many=False, plain=plain) for i in data) + b']'

        if plain:
            assert isinstance(data, s)
        elif isinstance(data, (QuerySet, Model)):
            s.model_config['from_attributes'] = True
            data = s.model_validate(data)
        else:
            s.model_config['from_attributes'] = False
            data = s.model_validate(data)
        res = data.model_dump_json()
        if isinstance(res, bytes):
            return res
        return res.encode('utf-8')


def _resolve_scheme_type(scheme: Scheme) -> Type[DRF] | Type[Pydantic]:
    if issubclass(scheme, BaseSerializer):
        return DRF
    elif issubclass(scheme, BaseModel):
        return Pydantic
    else:
        raise UnsupportedSchemeError('Unsupported scheme', scheme=scheme)


def scheme_load(scheme: Scheme, data: Json, *, many: bool = False, plain: bool = False) -> Json | Form:
    return _resolve_scheme_type(scheme).load(scheme, data, many=many, plain=plain)


def scheme_dump(scheme: Scheme, data: Json | Form, *, many: bool = False, plain: bool = False) -> Json:
    return _resolve_scheme_type(scheme).dump(scheme, data, many=many, plain=plain)


def scheme_json(scheme: Scheme, data: Json | Form, *, many: bool = False, plain: bool = False) -> bytes:
    return _resolve_scheme_type(scheme).json(scheme, data, many=many, plain=plain)
