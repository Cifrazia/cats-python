from pytest import fixture

from cats.v2.options import Options
from cats.v2.compressors import GzipCompressor, ZlibCompressor
from cats.v2.scheme import JSON
from cats.v2.utils import temp_file


@fixture
def headers():
    yield {}


@fixture
def options():
    yield Options(
        scheme=JSON,
        allowed_compressors=[GzipCompressor.type_id, ZlibCompressor.type_id],
        default_compressor=ZlibCompressor.type_id,
    )


@fixture
def test_file():
    with temp_file() as file:
        with file.open('w') as _fh:
            _fh.write('Hello world!')
        yield file


@fixture
def test_file2():
    with temp_file() as file:
        with file.open('w') as _fh:
            _fh.write('Welcome back!')
        yield file


@fixture
def test_file3():
    with temp_file() as file:
        with file.open('wb') as _fh:
            _fh.write(bytes(10240))
        yield file
