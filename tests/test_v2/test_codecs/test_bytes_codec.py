from pytest import mark, raises

from cats.v2.codecs.byte import ByteCodec
from cats.v2.errors import InvalidCodec


@mark.asyncio
async def test_encode_success(headers, options):
    assert await ByteCodec.encode(None, headers, options) == b''  # noqa
    assert await ByteCodec.encode(b'Hello world', headers, options) == b'Hello world'


@mark.asyncio
async def test_decode_success(headers, options):
    assert await ByteCodec.decode(b'', headers, options) == b''
    assert await ByteCodec.decode(b'Hello world', headers, options) == b'Hello world'


@mark.parametrize('data', (True, False, 1, 2.3, "Hello", [1, 2, 3], {"a": 5}, (1, 2, 3), {1, 2, 3}))
@mark.asyncio
async def test_encode_type_error(data, headers, options):
    with raises(InvalidCodec):
        await ByteCodec.encode(data, headers, options)  # noqa
