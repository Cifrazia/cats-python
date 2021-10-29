from os import urandom

from pytest import mark, raises

from cats.v2.compressors import GzipCompressor
from cats.v2.errors import CompressorError
from cats.v2.utils import temp_file


@mark.asyncio
async def test_buffer(headers, options):
    data = urandom(512).hex().encode('utf-8')
    compressed = await GzipCompressor.compress(data, headers, options)
    assert isinstance(compressed, bytes)
    assert len(compressed) < len(data)
    decompressed = await GzipCompressor.decompress(compressed, headers, options)
    assert decompressed == data


@mark.asyncio
async def test_file(test_file3, headers, options):
    with temp_file() as tmp1, temp_file() as tmp2:
        await GzipCompressor.compress_file(test_file3, tmp1, headers, options)
        assert tmp1.stat().st_size < test_file3.stat().st_size
        await GzipCompressor.decompress_file(tmp1, tmp2, headers, options)
        assert tmp2.stat().st_size == test_file3.stat().st_size
        with tmp2.open('rb') as src, test_file3.open('rb') as dst:
            assert src.read() == dst.read()


@mark.asyncio
async def test_decompress_broken_failed(headers, options):
    with raises(CompressorError):
        await GzipCompressor.decompress(b'\xFF', headers, options)


@mark.asyncio
async def test_decompress_file_broken_failed(test_file2, headers, options):
    with temp_file() as tmp1, raises(CompressorError):
        await GzipCompressor.decompress_file(test_file2, tmp1, headers, options)
