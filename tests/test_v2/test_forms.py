from django.contrib.sites.models import Site
from djantic import ModelSchema
from pydantic import BaseModel, ValidationError as PydanticError, constr
from pytest import mark, raises
from rest_framework.exceptions import ValidationError as DRFError
from rest_framework.serializers import CharField, Serializer

from cats.v2.errors import UnsupportedForm
from cats.v2.forms import form_dump, form_load, without_missing
from cats.v2.types import MISSING


class DRFForm(Serializer):  # noqa
    domain = CharField(min_length=1, max_length=24)
    name = CharField(min_length=1, max_length=24, required=False, allow_blank=True)


class PydanticForm(BaseModel):
    domain: constr(min_length=1, max_length=24)
    name: constr(min_length=1, max_length=24) = MISSING


class DjanticForm(ModelSchema):
    name: constr(min_length=1, max_length=24) = MISSING

    class Config:
        model = Site


def test_without_missing():
    assert without_missing({'domain': MISSING, 'name': 10}) == {'name': 10}
    assert without_missing([MISSING, 1, {'domain': MISSING}]) == [1, {}]
    assert without_missing((MISSING, 1, {'domain': MISSING})) == [1, {}]
    assert without_missing(1) == 1
    assert without_missing(MISSING) is None


def test_unsupported_form_fails():
    with raises(UnsupportedForm):
        form_load(object, {'a': 3})  # noqa
    with raises(UnsupportedForm):
        form_dump(object, {'a': 3})  # noqa


@mark.parametrize('data', (
    {'domain': 'example.com', 'name': 'Cifrazia'},
    {'domain': 'example.org'},
))
def test_drf_load(data):
    form = DRFForm(data=data)
    form.is_valid()

    assert form_load(DRFForm, data, plain=True).data == form.data
    assert form_load(DRFForm, data) == data


def test_drf_dump():
    assert form_dump(DRFForm, DRFForm(data={'domain': 'example.com', 'name': 'Cifrazia'}), plain=True) \
           == {'domain': 'example.com', 'name': 'Cifrazia'}
    assert form_dump(DRFForm, DRFForm(data={'domain': 'example.com'}), plain=True) \
           == {'domain': 'example.com'}
    assert form_dump(DRFForm, {'domain': 'example.com', 'name': 'Cifrazia'}) \
           == {'domain': 'example.com', 'name': 'Cifrazia'}
    assert form_dump(DRFForm, {'domain': 'example.com'}) \
           == {'domain': 'example.com'}
    assert form_dump(DRFForm, Site(domain='example.com', name='Cifrazia')) \
           == {'domain': 'example.com', 'name': 'Cifrazia'}
    assert form_dump(DRFForm, Site(domain='example.com')) \
           == {'domain': 'example.com', 'name': ''}


def test_pydantic_load():
    assert form_load(PydanticForm, {'domain': 'example.com', 'name': 'Cifrazia'}, plain=True) \
           == PydanticForm(domain='example.com', name='Cifrazia')
    assert form_load(PydanticForm, {'domain': 'example.com'}, plain=True) \
           == PydanticForm(domain='example.com')
    assert form_load(PydanticForm, {'domain': 'example.com', 'name': 'Cifrazia'}) \
           == {'domain': 'example.com', 'name': 'Cifrazia'}
    assert form_load(PydanticForm, {'domain': 'example.com'}) \
           == {'domain': 'example.com'}
    data = [
        {'domain': 'example.com', 'name': 'Cifrazia'},
        {'domain': 'example.org', 'name': 'Cifrazia'},
        {'domain': 'example.org'},
    ]
    assert form_load(PydanticForm, data, many=True) == data


def test_pydantic_dump():
    assert form_dump(PydanticForm, PydanticForm(domain='example.com', name='Cifrazia'), plain=True) \
           == {'domain': 'example.com', 'name': 'Cifrazia'}
    assert form_dump(PydanticForm, PydanticForm(domain='example.com'), plain=True) \
           == {'domain': 'example.com'}
    data = [
        {'domain': 'example.com', 'name': 'Cifrazia'},
        {'domain': 'example.org', 'name': 'Cifrazia'},
        {'domain': 'example.org'},
    ]
    assert form_dump(PydanticForm, data, many=True) == data


def test_djantic_load():
    assert form_load(DjanticForm, {'domain': 'example.com', 'name': 'Cifrazia'}, plain=True) \
           == DjanticForm.parse_obj({'domain': 'example.com', 'name': 'Cifrazia'})


def test_djantic_dump():
    assert form_dump(DjanticForm, DjanticForm.parse_obj({'id': 0, 'domain': 'example.com', 'name': 'Cifrazia'}),
                     plain=True) == {'id': 0, 'domain': 'example.com', 'name': 'Cifrazia'}
    assert form_dump(DjanticForm, Site(domain='example.com', name='Cifrazia'), ) \
           == {'id': None, 'domain': 'example.com', 'name': 'Cifrazia'}
    assert form_dump(DjanticForm, [
        {'domain': 'example.com', 'name': 'Cifrazia'},
        {'domain': 'example.org', 'name': 'Cifrazia'},
        {'domain': 'example.org'},
    ], many=True) == [
               {'id': None, 'domain': 'example.com', 'name': 'Cifrazia'},
               {'id': None, 'domain': 'example.org', 'name': 'Cifrazia'},
               {'id': None, 'domain': 'example.org'},
           ]


@mark.parametrize('form, err', (
    (PydanticForm, PydanticError),
    (DjanticForm, PydanticError),
    (DRFForm, (DRFError, KeyError)),
))
def test_validation_error(form, err):
    with raises(err):
        form_load(form, {})
    with raises(err):
        form_dump(form, {})
