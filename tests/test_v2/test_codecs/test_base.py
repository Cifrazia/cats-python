from abc import ABC

from pytest import mark, raises

from cats.v2.codecs import Codec, ByteCodec
from cats.v2.errors import CodecError, InvalidCodec


def test_ignore_codec_registration():
    class Dummy(Codec, ABC, register=False):
        pass

    assert Dummy not in Codec.registry.values()


def test_unintentional_codec_overwrite():
    with raises(ValueError):
        class Dummy(Codec, ABC):  # noqa
            type_id = 1
            type_name = 'dummy'

    with raises(ValueError):
        class Dummy(Codec, ABC):  # noqa
            type_id = 10
            type_name = 'bytes'


def test_intentional_codec_overwrite():
    _original = ByteCodec

    class Dummy(Codec, ABC, overwrite=True):  # noqa
        type_id = 0
        type_name = 'dummy'

    assert Codec.registry[0] == Dummy
    Codec.registry[0] = _original


@mark.asyncio
async def test_encode_any_finds(headers, options):
    assert await Codec.encode_any(b'Hello world', headers, options) == (b'Hello world', 0)
    assert await Codec.encode_any([1, 2, 3], headers, options) == (b'[1,2,3]', 1)


@mark.asyncio
async def test_encode_any_unsupported(headers, options):
    with raises(CodecError):
        await Codec.encode_any(object(), headers, options)


@mark.asyncio
async def test_decode_by_id(headers, options):
    assert await Codec.decode_by_id(b'Hello world', 0, headers, options) == b'Hello world'


@mark.asyncio
async def test_decode_by_id_unsupported(headers, options):
    with raises(InvalidCodec):
        assert await Codec.decode_by_id(b'Hello world', 69, headers, options)


def test_get_codec_name():
    assert Codec.get_codec_name(0, 'ultra') == 'bytes'
    assert Codec.get_codec_name(1, 'ultra') == 'scheme'
    assert Codec.get_codec_name(2, 'ultra') == 'files'
    assert Codec.get_codec_name(9, 'ultra') == 'ultra'
