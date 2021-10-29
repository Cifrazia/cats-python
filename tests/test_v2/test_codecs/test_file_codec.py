from pathlib import Path

from pytest import mark, raises

from cats.v2 import Header
from cats.v2.codecs.file import FileCodec, FileInfo, Files
from cats.v2.errors import CodecError, InvalidCodec, InvalidData, MalformedHeaders


def test_files_init(test_file):
    res = Files(name=FileInfo('name', test_file, test_file.stat().st_size))
    assert isinstance(res, Files)
    assert 'name' in res
    assert isinstance(res['name'], FileInfo)


def test_files_raise_error_on_init(test_file):
    with raises(InvalidData):
        Files(a=3)
    with raises(InvalidData):
        Files({1: FileInfo('name', test_file, test_file.stat().st_size)})


@mark.asyncio
async def test_encode_single_file(test_file, headers, options):
    f = await FileCodec.encode(test_file, headers, options)
    try:
        assert isinstance(f, Path)
        with f.open('rb') as _fh:
            assert _fh.read() == b'Hello world!'
        assert headers['Files'] == [{'key': test_file.name, 'name': test_file.name, 'size': 12, 'type': None}]
    finally:
        f.unlink(missing_ok=True)


@mark.asyncio
async def test_encode_dict_str_path(test_file, headers, options):
    f = await FileCodec.encode({'test': test_file}, headers, options)
    try:
        assert isinstance(f, Path)
        with f.open('rb') as _fh:
            assert _fh.read() == b'Hello world!'
        assert headers['Files'] == [{'key': 'test', 'name': test_file.name, 'size': 12, 'type': None}]
    finally:
        f.unlink(missing_ok=True)


@mark.asyncio
async def test_encode_file_info(test_file, headers, options):
    f = await FileCodec.encode(FileInfo('test', test_file, test_file.stat().st_size), headers, options)
    try:
        assert isinstance(f, Path)
        with f.open('rb') as _fh:
            assert _fh.read() == b'Hello world!'
        assert headers['Files'] == [{'key': 'test', 'name': 'test', 'size': 12, 'type': None}]
    finally:
        f.unlink(missing_ok=True)


@mark.asyncio
async def test_encode_dict_str_file_info(test_file, headers, options):
    f = await FileCodec.encode({'file': FileInfo('test', test_file, test_file.stat().st_size)}, headers, options)
    try:
        assert isinstance(f, Path)
        with f.open('rb') as _fh:
            assert _fh.read() == b'Hello world!'
        assert headers['Files'] == [{'key': 'file', 'name': 'test', 'size': 12, 'type': None}]
    finally:
        f.unlink(missing_ok=True)


@mark.asyncio
async def test_encode_list_path(test_file, test_file2, headers, options):
    f = await FileCodec.encode([test_file, test_file2], headers, options)
    try:
        assert isinstance(f, Path)
        with f.open('rb') as _fh:
            assert _fh.read() == b'Hello world!Welcome back!'
        assert headers['Files'] == [
            {'key': test_file.name, 'name': test_file.name, 'size': 12, 'type': None},
            {'key': test_file2.name, 'name': test_file2.name, 'size': 13, 'type': None},
        ]
    finally:
        f.unlink(missing_ok=True)


@mark.parametrize('offset', (5, 10, 20))
@mark.asyncio
async def test_encode_with_offset(test_file, headers, options, offset):
    headers[Header.offset] = offset
    f = await FileCodec.encode(test_file, headers, options)
    try:
        with f.open('rb') as src, test_file.open('rb') as dst:
            assert src.read() == dst.read()[offset:]
    finally:
        f.unlink(missing_ok=True)


@mark.asyncio
async def test_encode_dict_raise_type_error(test_file, headers, options):
    with raises(InvalidCodec):
        await FileCodec.encode({1: test_file}, headers, options)  # noqa
    with raises(InvalidCodec):
        await FileCodec.encode({"name": "not a file"}, headers, options)  # noqa


@mark.asyncio
async def test_encode_raise_type_error(test_file, headers, options):
    with raises(InvalidCodec):
        await FileCodec.encode(False, headers, options)  # noqa


@mark.asyncio
async def test_decode_success(headers, options):
    headers['Files'] = [
        {'key': 'test', 'name': 'test.txt', 'size': 12, 'type': None},
        {'key': 'test2', 'name': 'test2.txt', 'size': 13, 'type': None},
    ]
    decoded = await FileCodec.decode(b'Hello world!Welcome back!', headers, options)
    assert isinstance(decoded, Files)
    assert len(decoded) == 2
    test = decoded['test']
    test2 = decoded['test2']
    assert isinstance(test, FileInfo)
    assert isinstance(test2, FileInfo)
    with test.path.open('rb') as _fh:
        assert _fh.read() == b'Hello world!'
    with test2.path.open('rb') as _fh:
        assert _fh.read() == b'Welcome back!'


@mark.asyncio
async def test_decode_no_headers(headers, options):
    with raises(MalformedHeaders):
        await FileCodec.decode(b'', headers, options)
    headers['Files'] = 1
    with raises(MalformedHeaders):
        await FileCodec.decode(b'', headers, options)
    headers['Files'] = ['not a dict']
    with raises(MalformedHeaders):
        await FileCodec.decode(b'', headers, options)


@mark.asyncio
async def test_decode_small_payload(headers, options):
    headers['Files'] = [
        {'key': 'test', 'name': 'test.txt', 'size': 12, 'type': None},
        {'key': 'test2', 'name': 'test2.txt', 'size': 13, 'type': None},
    ]
    with raises(CodecError):
        await FileCodec.decode(b'small payload', headers, options)
