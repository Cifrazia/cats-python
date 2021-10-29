from typing import TypeAlias, TypeVar

from cats.v2.errors import UnsupportedForm
from cats.v2.types import Data, Missing, Model, QuerySet

try:
    from rest_framework.serializers import BaseSerializer
    from rest_framework.exceptions import APIException as DRFError
except ImportError:
    BaseSerializer = type('BaseSerializer', (object,), {})
    DRFError = type('DRFError', (object,), {})

try:
    from pydantic import BaseModel, ValidationError as PydanticError
except ImportError:
    BaseModel = type('BaseModel', (object,), {})
    Pydantic = type('Pydantic', (object,), {})

try:
    from djantic import ModelSchema
except ImportError:
    ModelSchema = type('ModelSchema', (object,), {})

__all__ = [
    'BaseSerializer',
    'BaseModel',
    'ModelSchema',
    'FormType',
    'Form',
    'SubForms',
    'without_missing',
    'form_load',
    'form_dump',
]

FormType: TypeAlias = type[BaseModel] | type[BaseSerializer] | type[ModelSchema]
Form = BaseModel, BaseSerializer, ModelSchema
PydanticModel = TypeVar('PydanticModel', bound=BaseModel)
DRFModel = TypeVar('DRFModel', bound=BaseSerializer)
DjanticModel = TypeVar('DjanticModel', bound=ModelSchema)
SubForms: TypeAlias = PydanticModel | DRFModel | DjanticModel


def without_missing(obj) -> Data | None:
    if _items := getattr(obj, 'items', None):
        return {k: without_missing(v) for k, v in _items() if not isinstance(v, Missing)}
    if isinstance(obj, (list, set, tuple)):
        return [without_missing(i) for i in obj if not isinstance(i, Missing)]
    if isinstance(obj, Missing):
        return None
    return obj


class DRF:
    @classmethod
    def load(cls, s: type[BaseSerializer], data: Data, *, many: bool = False, plain: bool = False) -> Data | DRFModel:
        f = s(data=data, many=many)
        f.is_valid(raise_exception=True)
        if plain:
            return f
        return f.validated_data

    @classmethod
    def dump(cls, s: type[BaseSerializer], data: Data | DRFModel | QuerySet | Model, *,
             many: bool = False, plain: bool = False) -> Data:
        if not plain:
            if isinstance(data, QuerySet | Model):
                data = s(data, many=many)
            else:
                data = s(data=data, many=many)
        if data.instance is None:
            data.is_valid(raise_exception=True)
        return data.data


class Pydantic:
    @classmethod
    def load(cls, s: type[BaseModel], data: Data, *, many: bool = False, plain: bool = False) -> Data | PydanticModel:
        if many:
            return [cls.load(s, i, many=False, plain=plain) for i in data]

        res = s.parse_obj(data)
        if plain:
            return res

        return without_missing(res.dict())

    @classmethod
    def dump(cls, s: type[BaseModel], data: Data | PydanticModel, *, many: bool = False, plain: bool = False) -> Data:
        if many:
            return [cls.dump(s, i, many=False, plain=plain) for i in data]

        if plain:
            assert isinstance(data, s)
        else:
            data = s.parse_obj(data)
        return without_missing(data.dict())


class Djantic(Pydantic):
    @classmethod
    def dump(cls, s: type[ModelSchema], data: Data | QuerySet | Model, *,
             many: bool = False, plain: bool = False) -> Data | DjanticModel:
        if many:
            return [cls.dump(s, i, many=False, plain=plain) for i in data]

        if not isinstance(data, (QuerySet, Model)):
            return super().dump(s, data, many=many, plain=plain)

        data = s.from_django(data)
        return without_missing(data.dict())


def _resolve_scheme_type(form: FormType) -> type[DRF] | type[Djantic] | type[Pydantic]:
    if issubclass(form, BaseSerializer):
        return DRF
    elif issubclass(form, ModelSchema):
        return Djantic
    elif issubclass(form, BaseModel):
        return Pydantic
    else:
        raise UnsupportedForm('Unsupported form', form=form)


def form_load(form: FormType, data: Data, *, many: bool = False, plain: bool = False) -> Data | SubForms:
    return _resolve_scheme_type(form).load(form, data, many=many, plain=plain)


def form_dump(form: FormType, data: Data | SubForms | QuerySet | Model, *,
              many: bool = False, plain: bool = False) -> Data:
    return _resolve_scheme_type(form).dump(form, data, many=many, plain=plain)
