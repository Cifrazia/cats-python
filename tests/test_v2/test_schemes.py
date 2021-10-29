from abc import ABC

from pytest import mark, raises

from cats.v2.scheme import Scheme, JSON, MsgPack, YAML


@mark.parametrize('buff, data', (
    ('null', None),
    ('1', 1),
    ('2.3', 2.3),
    ('true', True),
    ('false', False),
    ('"Hello"', 'Hello'),
    ('[1,2,3]', [1, 2, 3]),
    ('{"a":[1,2,3]}', {'a': [1, 2, 3]}),
    (b'"bytes"', 'bytes')
))
def test_json_loads(buff, data):
    assert JSON.loads(buff) == data


@mark.parametrize('buff, data', (
    (b'null', None),
    (b'1', 1),
    (b'2.3', 2.3),
    (b'true', True),
    (b'false', False),
    (b'"Hello"', 'Hello'),
    (b'[1,2,3]', [1, 2, 3]),
    (b'{"a":[1,2,3]}', {'a': [1, 2, 3]}),
))
def test_json_dumps(buff, data):
    assert JSON.dumps(data) == buff


@mark.parametrize('buff, data', (
    ('null', None),
    ('1', 1),
    ('2.3', 2.3),
    ('true', True),
    ('false', False),
    ('Hello', 'Hello'),
    ('- 1\n- 2\n- 3', [1, 2, 3]),
    ('a:\n- 1\n- 2\n- 3', {'a': [1, 2, 3]}),
    (b'"bytes"', 'bytes')
))
def test_yaml_loads(buff, data):
    assert YAML.loads(buff) == data


@mark.parametrize('buff, data', (
    (b'null', None),
    (b'1', 1),
    (b'2.3', 2.3),
    (b'true', True),
    (b'false', False),
    (b'Hello', 'Hello'),
    (b'- 1\n- 2\n- 3', [1, 2, 3]),
    (b'a:\n- 1\n- 2\n- 3', {'a': [1, 2, 3]}),
))
def test_yaml_dumps(buff, data):
    assert YAML.dumps(data) == buff


@mark.parametrize('buff, data', (
    (b'\xc0', None),
    (b'\x01', 1),
    (b'\xcb\x40\x02\x66\x66\x66\x66\x66\x66', 2.3),
    (b'\xc3', True),
    (b'\xc2', False),
    (b'\xa5Hello', 'Hello'),
    (b'\x93\x01\x02\x03', [1, 2, 3]),
    (b'\x81\xa1a\x93\x01\x02\x03', {'a': [1, 2, 3]}),
))
def test_msgpack_loads_and_dumps(buff, data):
    assert MsgPack.loads(buff) == data
    assert MsgPack.dumps(data) == buff


@mark.parametrize('buff, data', (
    ('{"a":[1,2,3]}', {'a': [1, 2, 3]}),
    (b'a:\n- 1\n- 2\n- 3', {'a': [1, 2, 3]}),
    (b'\x81\xa1a\x93\x01\x02\x03', {'a': [1, 2, 3]}),
))
def test_load_any(buff, data):
    assert Scheme.load_any(buff) == data


def test_load_any_failed():
    with raises(ValueError):
        assert Scheme.load_any(b'\x0F\xFF\xF0')


def test_load_any_no_scheme():
    sc = Scheme.registry.copy()
    Scheme.registry.clear()
    with raises(TypeError):
        assert Scheme.load_any(b'{}')
    Scheme.registry = sc


def test_register_success():
    ln = len(Scheme.registry)

    class TestScheme(Scheme, ABC):
        type_id = 10
        type_name = 'test'

    assert len(Scheme.registry) == ln + 1
    assert TestScheme.type_id in Scheme.registry
    Scheme.unregister(TestScheme)
    assert len(Scheme.registry) == ln
    del TestScheme


def test_register_skip():
    ln = len(Scheme.registry)

    # noinspection PyUnusedLocal
    class TestScheme(Scheme, ABC, register=False):
        type_id = 15
        type_name = 'test'

    assert len(Scheme.registry) == ln


def test_register_exists():
    with raises(ValueError):
        # noinspection PyUnusedLocal
        class TestScheme(Scheme, ABC):
            type_id = 1
            type_name = 'test'
