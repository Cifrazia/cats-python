from abc import ABC
from os import urandom

from pytest import mark, raises

from cats.v2.compressors import Compressor, DummyCompressor, GzipCompressor, ZlibCompressor
from cats.v2.errors import CompressorError, InvalidCompressor
from cats.v2.utils import temp_file


def test_ignore_compressor_registration():
    class Dummy(Compressor, ABC, register=False):
        pass

    assert Dummy not in Compressor.registry.values()


def test_unintentional_compressor_overwrite():
    with raises(ValueError):
        class Dummy(Compressor, ABC):  # noqa
            type_id = 0
            type_name = 'some'

    with raises(ValueError):
        class Dummy(Compressor, ABC):  # noqa
            type_id = 10
            type_name = 'dummy'


def test_intentional_compressor_overwrite():
    _dummy = DummyCompressor

    class Dummy(Compressor, ABC, overwrite=True):  # noqa
        type_id = 0
        type_name = 'dummy'

    assert Compressor.registry[0] == Dummy
    Compressor.registry[0] = _dummy


@mark.asyncio
async def test_propose_compressor(test_file3, headers, options):
    assert await Compressor.propose_compressor(bytes(0), headers, options) == DummyCompressor.type_id
    assert await Compressor.propose_compressor(bytes(10240), headers, options) == ZlibCompressor.type_id
    assert await Compressor.propose_compressor(test_file3, headers, options) == ZlibCompressor.type_id
    with raises(InvalidCompressor):
        await Compressor.propose_compressor(90, headers, options)  # noqa


def test_list_compressors():
    assert list(Compressor.list_compressors(0)) == [DummyCompressor]
    assert list(Compressor.list_compressors([4])) == [DummyCompressor]
    assert list(Compressor.list_compressors([1])) == [GzipCompressor, DummyCompressor]
    assert list(Compressor.list_compressors([1, 2])) == [GzipCompressor, ZlibCompressor, DummyCompressor]


@mark.asyncio
async def test_compress_any_finds(headers, options):
    assert await Compressor.compress_any(b'Hello world', headers, options) == (b'Hello world', 0)
    data = urandom(4096).hex().encode('utf-8')
    compressed, _type = await Compressor.compress_any(data, headers, options)
    assert _type == ZlibCompressor.type_id
    assert len(compressed) < len(data)
    assert await Compressor.decompress_by_id(compressed, ZlibCompressor.type_id, headers, options) == data


@mark.asyncio
async def test_compress_any_unsupported(headers, options):
    with raises(InvalidCompressor):
        await Compressor.compress_any(object(), headers, options)  # noqa


@mark.asyncio
async def test_compress_any_file_finds(test_file, test_file3, headers, options):
    with temp_file() as tmp1, temp_file() as tmp2:
        assert await Compressor.compress_any_file(test_file, tmp1, headers, options) == 0
        with test_file.open('rb') as src, tmp1.open('rb') as dst:
            assert src.read() == dst.read()

        assert await Compressor.compress_any_file(test_file3, tmp1, headers, options) == ZlibCompressor.type_id
        assert tmp1.stat().st_size < test_file3.stat().st_size
        await Compressor.decompress_file_by_id(tmp1, tmp2, ZlibCompressor.type_id, headers, options)
        with test_file3.open('rb') as src, tmp2.open('rb') as dst:
            assert src.read() == dst.read()


@mark.asyncio
async def test_dummy_decompress(headers, options):
    assert await DummyCompressor.decompress(b'Hello world', headers, options) == b'Hello world'


@mark.asyncio
async def test_dummy_decompress_file(test_file, headers, options):
    with temp_file() as tmp1:
        await DummyCompressor.decompress_file(test_file, tmp1, headers, options)
        with test_file.open('rb') as src, tmp1.open('rb') as dst:
            assert src.read() == dst.read()


@mark.asyncio
async def test_compress_any_file_unsupported(headers, options):
    with raises(InvalidCompressor):
        await Compressor.compress_any(object(), headers, options)  # noqa


@mark.asyncio
async def test_decompress_by_id_unsupported(test_file, headers, options):
    with raises(InvalidCompressor):
        await Compressor.decompress_by_id(b'Hello', 69, headers, options)
    with raises(InvalidCompressor):
        await Compressor.decompress_file_by_id(test_file, test_file, 69, headers, options)


def test_get_compressor_name():
    assert Compressor.get_compressor_name(0, 'ultra') == 'dummy'
    assert Compressor.get_compressor_name(1, 'ultra') == 'gzip'
    assert Compressor.get_compressor_name(2, 'ultra') == 'zlib'
    assert Compressor.get_compressor_name(9, 'ultra') == 'ultra'


@mark.asyncio
async def test_broken_compressor(broken_compressor, test_file, headers, options):
    with raises(CompressorError):
        await Compressor.compress_any(b'', headers, options)
    with raises(CompressorError):
        await Compressor.compress_any_file(test_file, test_file, headers, options)
