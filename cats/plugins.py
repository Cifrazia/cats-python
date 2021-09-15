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

try:
    from djantic import ModelSchema
except ImportError:
    ModelSchema = type('ModelSchema', (object,), {})

__all__ = [
    'QuerySet',
    'Model',
    'BaseSerializer',
    'BaseModel',
    'ModelSchema',
    'Scheme',
    'SchemeTypes',
    'Form',
    'without_missing',
    'scheme_load',
    'scheme_dump',
    'scheme_json',
]

Scheme: TypeAlias = Type[BaseModel] | Type[BaseSerializer] | Type[ModelSchema]
SchemeTypes = BaseModel, BaseSerializer, ModelSchema
PydanticModel = TypeVar('PydanticModel', bound=BaseModel)
DRFModel = TypeVar('DRFModel', bound=BaseSerializer)
DjanticModel = TypeVar('DjanticModel', bound=ModelSchema)
Form: TypeAlias = PydanticModel | DRFModel | DjanticModel


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

        res = s.parse_obj(data)
        if plain:
            return res

        return without_missing(res.dict())

    @classmethod
    def dump(cls, s: Type[BaseModel], data: Json | PydanticModel, *, many: bool = False, plain: bool = False) -> Json:
        if many:
            return [cls.dump(s, i, many=False, plain=plain) for i in data]

        if plain:
            assert isinstance(data, s)
        elif isinstance(data, (QuerySet, Model)):
            data = s.from_orm(data)
        else:
            data = s.parse_obj(data)
        return data.dict()

    @classmethod
    def json(cls, s: Type[BaseModel], data: Json | PydanticModel, *, many: bool = False, plain: bool = False) -> bytes:
        if many:
            return b'[' + b','.join(cls.json(s, i, many=False, plain=plain) for i in data) + b']'

        if plain:
            assert isinstance(data, s)
        elif isinstance(data, (QuerySet, Model)):
            data = s.from_orm(data)
        else:
            data = s.parse_obj(data)
        res = data.json()
        if isinstance(res, bytes):
            return res
        return res.encode('utf-8')


class Djantic(Pydantic):
    @classmethod
    def dump(cls, s: Type[ModelSchema], data: Json, *, many: bool = False, plain: bool = False) -> Json | DjanticModel:
        if many:
            return [cls.dump(s, i, many=False, plain=plain) for i in data]

        if not isinstance(data, (QuerySet, Model)):
            return super().dump(s, data, many=many, plain=plain)

        if plain:
            assert isinstance(data, s)
        else:
            data = s.from_django(data)
        return data.json()

    @classmethod
    def json(cls, s: Type[ModelSchema], data: Json | DjanticModel, *, many: bool = False, plain: bool = False) -> bytes:
        if many:
            return b'[' + b','.join(cls.json(s, i, many=False, plain=plain) for i in data) + b']'

        if not isinstance(data, (QuerySet, Model)):
            return super().json(s, data, many=many, plain=plain)

        if plain:
            assert isinstance(data, s)
        else:
            data = s.from_django(data)
        res = data.json()
        if isinstance(res, bytes):
            return res
        return res.encode('utf-8')


def _resolve_scheme_type(scheme: Scheme) -> Type[DRF] | Type[Djantic] | Type[Pydantic]:
    if issubclass(scheme, BaseSerializer):
        return DRF
    elif issubclass(scheme, ModelSchema):
        return Djantic
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
