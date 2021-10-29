from pydantic import BaseModel
from pytest import mark, raises

from cats.v2.codecs.scheme import SchemeCodec
from cats.v2.errors import CodecError, InvalidCodec


class Form(BaseModel):
    foo: str = 'bar'


@mark.asyncio
async def test_encode_success(headers, options):
    assert await SchemeCodec.encode(None, headers, options) == b'null'  # noqa
    assert await SchemeCodec.encode(1, headers, options) == b'1'
    assert await SchemeCodec.encode([1, 2, 3], headers, options) == b'[1,2,3]'

    assert await SchemeCodec.encode(Form(), headers, options) == b'{"foo":"bar"}'
    assert await SchemeCodec.encode([Form(), Form()], headers, options) == b'[{"foo":"bar"},{"foo":"bar"}]'


@mark.asyncio
async def test_decode_success(headers, options):
    assert await SchemeCodec.decode(None, headers, options) == {}  # noqa
    assert await SchemeCodec.decode(b'', headers, options) == {}
    assert await SchemeCodec.decode(b'[1,2,3]', headers, options) == [1, 2, 3]
    assert await SchemeCodec.decode(b'"Hello world"', headers, options) == 'Hello world'


@mark.asyncio
async def test_decode_not_scheme(headers, options):
    with raises(CodecError):
        await SchemeCodec.decode(b'\xFF\x00', headers, options)


@mark.asyncio
async def test_encode_type_error(headers, options):
    with raises(InvalidCodec):
        await SchemeCodec.encode(object(), headers, options)  # noqa
    with raises(InvalidCodec):
        await SchemeCodec.encode(bytes(), headers, options)  # noqa
