import os
from pathlib import Path

from pytest import mark, raises

from cats.v2.utils import *


def test_to_uint_returns_bytes():
    assert to_uint(0) == b'\x00'
    assert to_uint(10) == b'\x0A'
    assert to_uint(0xFFFF) == b'\xFF\xFF'


def test_to_uint_returns_padded_bytes():
    assert to_uint(0, 4) == b'\x00\x00\x00\x00'
    assert to_uint(0xFFFF, 4) == b'\x00\x00\xFF\xFF'


def test_to_uint_raise_overflow_error():
    with raises(OverflowError):
        to_uint(0xFFFF, 1)


def test_to_uint_raise_value_error_on_non_positive_length():
    with raises(ValueError):
        to_uint(1, 0)
    with raises(ValueError):
        to_uint(1, -1)


def test_to_uint_raise_value_error_on_negative():
    with raises(ValueError):
        to_uint(-1)
    with raises(ValueError):
        to_uint(-1000, 6)


def test_from_uint_returns_int():
    assert from_uint(b'\x00') == 0
    assert from_uint(b'\xFF\xFF') == 0xFFFF


def test_from_uint_returns_zero_on_empty_string():
    assert from_uint(b'') == 0


@mark.asyncio
async def test_delay_sleep(no_sleep):
    delay = Delay(100)
    await delay(100)
    no_sleep.assert_not_called()
    for _ in range(10):
        await delay(200)
        args, _ = no_sleep.call_args
        assert len(args) == 1
        assert 1.9 <= args[0] <= 3.0
        delay.start -= args[0]


@mark.asyncio
async def test_delay_sleep_partial(no_sleep):
    delay = Delay(1024)
    await delay(128)
    no_sleep.assert_not_called()
    for _ in range(10):
        await delay(128)
        args, _ = no_sleep.call_args
        assert len(args) == 1
        assert 0.1 <= args[0] <= 0.3
        delay.start -= args[0]


@mark.asyncio
async def test_delay_no_sleep(no_sleep):
    delay = Delay(1024)
    await delay(0)
    no_sleep.assert_not_called()
    await delay(256)


@mark.asyncio
async def test_delay_unlimited_speed_no_sleep(no_sleep):
    delay = Delay(0)
    for _ in range(10):
        await delay(1024)
        no_sleep.assert_not_called()


@mark.asyncio
async def test_delay_empty_payload_no_sleep(no_sleep):
    delay = Delay(10)
    await delay(10)
    no_sleep.assert_not_called()
    for _ in range(10):
        await delay(0)
        no_sleep.assert_not_called()


@mark.asyncio
async def test_delay_enough_time_passed_no_sleep(no_sleep):
    delay = Delay(10)
    await delay(10)
    no_sleep.assert_not_called()
    delay.start -= 2.0
    await delay(10)
    no_sleep.assert_not_called()


def test_tmp_file_returns_path_in_tmp_folder():
    tmp = tmp_file()
    assert isinstance(tmp, Path)
    assert tmp.as_posix().startswith(os.environ['TMPDIR'])
    assert tmp.is_file()


def test_require_imports():
    test_class: type = require('tests.data_test_require.TestObject')
    assert isinstance(test_class, type)
    test_object: test_class = require('tests.data_test_require.test_object')
    assert isinstance(test_object, test_class)


def test_require_raise_import_error_on_invalid_path():
    with raises(ImportError):
        require('tests')


def test_require_raise_import_error_if_not_found():
    with raises(ImportError):
        require('not_exising.module')
    with raises(ImportError):
        require('tests.data_test_require.not_existing_attribute')


def test_require_returns_none_if_not_strict():
    assert require('not_existing.module', strict=False) is None


def test_int2hex():
    assert int2hex(-1, 1) == 'X1'
    assert int2hex(0, 1) == '00'
    assert int2hex(128) == '0080'
    assert int2hex(128, 5) == '0000000080'
    assert int2hex(128, -3) == '80'


def test_bytes2hex():
    assert bytes2hex(b'hello') == '68 65 6C 6C 6F'
    assert bytes2hex(b'hello', separator='.') == '68.65.6C.6C.6F'
    assert bytes2hex(b'hello', prefix=True) == '0x68 0x65 0x6C 0x6C 0x6F'


def test_bytes2hex_type_error():
    with raises(TypeError):
        bytes2hex('string')  # noqa


def test_format_amount():
    assert format_amount(0) == "0B"
    assert format_amount(1750) == "1.7KB"
    assert format_amount(1234567890) == "1.1GB"
    assert format_amount(2000, base=10, suffix='r') == "2Gr"
    assert format_amount(2000, base=10, prefix='r') == "2GrB"
    assert format_amount(2048, base=2) == "1YB"


def test_format_amount_errors():
    with raises(TypeError):
        format_amount("not a number")  # noqa
    with raises(TypeError):
        format_amount(10, base="not a number")  # noqa
    with raises(ValueError):
        format_amount(10, base=0)
    with raises(ValueError):
        format_amount(10, base=-1)


def test_filter_json():
    assert filter_json(b'{"foo":"bar"}') == '{"foo":"bar"}'
    assert filter_json({'foo': 'bar'}) == '{"foo":"bar"}'
    assert filter_json({'foo': 'bar'}, indent=True) == '{\n  "foo": "bar"\n}'
    assert filter_json([1, 2, 3], max_size=2) == '[1,2,"1 more"]'
    assert filter_json('string', max_len=2) == '"st..."'
    for key in ('password', 'key', 'secret', 'jwt', 'pwd', 'пароль', 'ключ', 'секрет'):
        assert filter_json({key: 'qwerty'}) == '{"%s":"<masked>"}' % key
    for key in ('password', 'key', 'secret', 'jwt', 'pwd', 'пароль', 'ключ', 'секрет'):
        mod_key = f'_prefix_{key}_suffix_'
        assert filter_json({mod_key: 'qwerty'}) == '{"%s":"<masked>"}' % mod_key

    assert filter_json({
        'username': 'Adam_Bright',
        'password': 'qwerty',
        'email': 'adam@gmail.com'
    }, max_size=2, max_len=2) == '{"username":"Ad...","password":"<masked>","<more>":"1 items"}'
