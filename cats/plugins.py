from typing import Type, Union

try:
    from django.db.models import QuerySet
except ImportError:
    QuerySet = type('QuerySet', (list,), {})

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
    'BaseSerializer',
    'BaseModel',
    'Scheme',
    'SchemeTypes',
    'Form',
    'FormTypes',
    'scheme_load',
    'scheme_dump',
]

Scheme = Union[Type[BaseModel], Type[BaseSerializer]]
SchemeTypes = (BaseModel, BaseSerializer)
Form = Union[BaseModel, BaseSerializer]
FormTypes = (BaseModel, BaseSerializer)


def load_drf_serializer(s: Type[BaseSerializer], data, plain: bool):
    f = s(data=data)
    f.is_valid(raise_exception=True)
    return f if plain else f.validated_data


def dump_drf_serializer(s: Type[BaseSerializer], data, plain: bool):
    return data.data if plain else s(data).data


def load_pydantic_scheme(s: Type[BaseModel], data, plain: bool):
    res = s.parse_obj(data)
    return res if plain else res.dict()


def dump_pydantic_scheme(s: Type[BaseModel], data, plain: bool):
    return data.dict() if plain else s.parse_obj(data).dict()


def scheme_load(scheme: Scheme, data, *, many: bool = False, plain: bool = False):
    if issubclass(scheme, BaseSerializer):
        fn = load_drf_serializer
    elif issubclass(scheme, BaseModel):
        fn = load_pydantic_scheme
    else:
        raise TypeError('Unsupported scheme')

    if many:
        return [fn(scheme, i, plain) for i in data]

    return fn(scheme, data, plain)


def scheme_dump(scheme: Scheme, data, *, many: bool = False, plain: bool = False):
    if issubclass(scheme, BaseSerializer):
        fn = dump_drf_serializer
    elif issubclass(scheme, BaseModel):
        fn = dump_pydantic_scheme
    else:
        raise TypeError('Unsupported scheme')

    if many:
        return [fn(scheme, i, plain) for i in data]

    return fn(scheme, data, plain)
