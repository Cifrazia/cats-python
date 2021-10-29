from pytest import raises

from cats.v2.errors import MalformedHeaders
from cats.v2.headers import Headers


def test_headers_parse():
    assert Headers(foo=3) == {'Foo': 3}
    assert Headers({'foo': 3}) == {'Foo': 3}
    assert Headers({'foo': 3}, foo=5) == {'Foo': 5}
    assert Headers({'foo': 3}, bar=5) == {'Foo': 3, 'Bar': 5}
    with raises(TypeError):
        assert Headers(False)


def test_system_header_skip():
    assert Headers(skip=9999) == {'Skip': 9999}
    assert Headers(skip=0) == {'Skip': 0}
    with raises(MalformedHeaders):
        Headers(skip=-1)
    with raises(MalformedHeaders):
        Headers(skip='NotANumber')


def test_system_header_offset():
    assert Headers(offset=9999) == {'Offset': 9999}
    assert Headers(offset=0) == {'Offset': 0}
    with raises(MalformedHeaders):
        Headers(offset=-1)
    with raises(MalformedHeaders):
        Headers(offset='NotANumber')


def test_header_as_dict_behavior():
    headers = Headers(foo='bar')
    assert headers['foo'] == 'bar'
    headers['yahoo'] = 'zip'
    assert 'yahoo' in headers
    del headers['yahoo']
    assert 'yahoo' not in headers
    assert headers.get('morning') is None
    headers.update(foo='baz', bar='boz')
    assert headers == {'Foo': 'baz', 'Bar': 'boz'}


def test_headers_encode():
    assert Headers(foo='bar').encode() == b'{"Foo":"bar"}'


def test_headers_decode():
    assert Headers.decode(b'{"foo":"bar"}') == Headers(foo='bar')
    assert Headers.decode(b'broken') == Headers()
