from typing import Type, Union

try:
    from django.db.models import QuerySet, Model
except ImportError:
    QuerySet = type('QuerySet', (list,), {})
    Model = type('Model', (list,), {})

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
    'BaseSerializer',
    'BaseModel',
    'Scheme',
    'SchemeTypes',
    'Form',
    'scheme_load',
    'scheme_dump',
]

Scheme = Union[Type[BaseModel], Type[BaseSerializer], Type[ModelSchema]]
SchemeTypes = (BaseModel, BaseSerializer, ModelSchema)
Form = Union[BaseModel, BaseSerializer, ModelSchema]


class DRF:
    @classmethod
    def load(cls, s: Type[BaseSerializer], data, *, many: bool = False, plain: bool = False):
        f = s(data=data, many=many)
        f.is_valid(raise_exception=True)
        return f if plain else f.validated_data

    @classmethod
    def dump(cls, s: Type[BaseSerializer], data, *, many: bool = False, plain: bool = False):
        if plain:
            assert isinstance(data, s)
            return data.data
        return s(data, many=many).data


class Pydantic:
    @classmethod
    def load(cls, s: Type[BaseModel], data, *, many: bool = False, plain: bool = False):
        if many:
            return [cls.load(s, i, many=False, plain=plain) for i in data]

        res = s.parse_obj(data)
        return res if plain else res.dict()

    @classmethod
    def dump(cls, s: Type[BaseModel], data, *, many: bool = False, plain: bool = False):
        if many:
            return [cls.dump(s, i, many=False, plain=plain) for i in data]

        if plain:
            assert isinstance(data, s)
        elif isinstance(data, (QuerySet, Model)):
            data = s.from_orm(data)
        else:
            data = s.parse_obj(data)
        return data.dict()


class Djantic(Pydantic):
    @classmethod
    def dump(cls, s: Type[ModelSchema], data, *, many: bool = False, plain: bool = False):
        if many:
            return [cls.dump(s, i, many=False, plain=plain) for i in data]

        if not isinstance(data, (QuerySet, Model)):
            return super().dump(s, data, many=many, plain=plain)

        if plain:
            assert isinstance(data, s)
        else:
            data = s.from_django(data)
        return data.dict()


def _resolve_scheme_type(scheme: Scheme):
    if issubclass(scheme, BaseSerializer):
        return DRF
    elif issubclass(scheme, ModelSchema):
        return Djantic
    elif issubclass(scheme, BaseModel):
        return Pydantic
    else:
        raise TypeError('Unsupported scheme')


def scheme_load(scheme: Scheme, data, *, many: bool = False, plain: bool = False):
    return _resolve_scheme_type(scheme).load(scheme, data, many=many, plain=plain)


def scheme_dump(scheme: Scheme, data, *, many: bool = False, plain: bool = False):
    return _resolve_scheme_type(scheme).dump(scheme, data, many=many, plain=plain)
