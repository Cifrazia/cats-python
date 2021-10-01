from pytest import mark

from cats.v2 import ByteCodec


class TestBytesCodec:
    @mark.parametrize('inp, res', (
            (b'Hello', b'Hello'),
            (bytearray([10]), b'\x0A'),
            (memoryview(b'Hello'), b'Hello')
    ))
    @mark.asyncio
    async def test_encode_success(self, inp, res):
        assert await ByteCodec.encode(inp, {}) == res

    @mark.asyncio
    async def test_decode_success(self):
        assert await ByteCodec.decode(b'Hello', {}) == b'Hello'
