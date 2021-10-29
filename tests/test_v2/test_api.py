import asyncio
import os
from time import time

from pytest import mark, raises
from tornado.iostream import StreamClosedError

from cats.v2 import Action, FileInfo, InputAction, StreamAction, temp_file
from cats.v2.client import Connection
from tests.test_v2.handlers import *


@mark.asyncio
async def test_echo_handler(cats_conn: Connection):
    payload = os.urandom(10)
    response = await cats_conn.send(EchoHandler.handler_id, payload)
    assert response.data == payload


@mark.asyncio
async def test_echo_handler_files(cats_conn: Connection):
    with temp_file() as payload:
        response = await cats_conn.send(EchoHandler.handler_id, payload)
        assert isinstance(response.data, dict)
        for key, val in response.data.items():
            assert isinstance(key, str)
            assert isinstance(val, FileInfo)


@mark.asyncio
async def test_no_response(cats_conn: Connection):
    payload = os.urandom(10)
    with raises(asyncio.TimeoutError):
        await asyncio.wait_for(cats_conn.send(VoidHandler.handler_id, payload), 0.1)


@mark.parametrize('api_version, handler_version', [
    [0, None],
    [1, 1],
    [2, 1],
    [3, 2],
    [4, 2],
    [5, None],
    [6, 3],
    [7, 3],
])
@mark.asyncio
async def test_api_version(cats_server, cats_config, api_version: int, handler_version: int):
    conn = Connection(cats_config, api_version)
    await conn.connect('127.0.0.1', cats_server.port)
    async with conn:
        if handler_version is not None:
            response = await conn.send(VersionedHandler.handler_id, b'')
            assert response.data == {'version': handler_version}
        else:
            with raises(StreamClosedError):
                await conn.send(VersionedHandler.handler_id, b'')


@mark.asyncio
async def test_api_stream(cats_conn: Connection):
    result = await cats_conn.send(DelayedHandler.handler_id, None)
    assert isinstance(result, StreamAction)
    assert result.data == b'hello world!'


@mark.parametrize('reply, result', [
    [b'yes', b'Nice!'],
    [b'no', b'Sad!'],
])
@mark.asyncio
async def test_api_internal_request(cats_conn: Connection, reply, result):
    response = await cats_conn.send(InputHandler.handler_id, None)
    assert isinstance(response, InputAction)
    assert response.data == b'Are you ok?'
    response = await response.reply(reply)
    assert isinstance(response, Action)
    assert response.data == result


@mark.parametrize('reply, result', [
    ['yes', 'Nice!'],
    ['no', 'Sad!'],
])
@mark.asyncio
async def test_api_internal_json_request(cats_conn: Connection, reply, result):
    response = await cats_conn.send(InputJSONHandler.handler_id, None)
    assert isinstance(response, InputAction)
    assert response.data == 'Are you ok?'
    response = await response.reply(reply)
    assert isinstance(response, Action)
    assert response.data == result


@mark.asyncio
async def test_api_json_validation(cats_conn: Connection):
    response = await cats_conn.send(JsonFormHandler.handler_id, {'id': 5, 'name': 'adam'})
    assert isinstance(response, Action)

    data = response.data
    assert isinstance(data, dict)
    assert isinstance(data['token'], str) and len(data['token']) == 64
    assert isinstance(data['code'], str) and len(data['code']) == 6


@mark.asyncio
async def test_api_json_invalid(cats_conn: Connection):
    res = await cats_conn.send(JsonFormHandler.handler_id, 'not even a dict')
    assert isinstance(res, Action)
    assert res.status == 400


@mark.asyncio
async def test_api_speed_limiter(cats_conn: Connection):
    payload = os.urandom(100_000)

    start = time()
    res = await cats_conn.send(EchoHandler.handler_id, payload)
    assert 0 <= time() - start <= 0.5
    assert res.data == payload

    await cats_conn.set_download_speed(100_000)

    start = time()
    res = await cats_conn.send(EchoHandler.handler_id, payload)
    assert 0.5 <= time() - start <= 1.5
    assert res.data == payload


@mark.asyncio
async def test_api_payload_offset(cats_conn: Connection):
    payload = b'1234567890'
    response = await cats_conn.send(EchoHandler.handler_id, payload, headers={"Skip": 5})
    assert response.data == b'67890'


@mark.asyncio
async def test_api_payload_offset_files(cats_conn: Connection):
    with temp_file() as payload:
        with payload.open('wb') as fh:
            fh.write(b'1234567890')

        response = await cats_conn.send(EchoHandler.handler_id, payload, headers={"Skip": 5})
        assert isinstance(response.data, dict)
        for key, val in response.data.items():
            assert isinstance(key, str)
            assert isinstance(val, FileInfo)
            assert val.size == 5
            assert val.path.read_bytes() == b'67890'


@mark.asyncio
async def test_cancel_input(cats_conn: Connection):
    response = await cats_conn.send(InputHandler.handler_id, None)
    assert isinstance(response, InputAction)
    assert response.data == b'Are you ok?'
    response = await response.cancel()
    assert isinstance(response, Action)
    assert response.status == 500, response.data
