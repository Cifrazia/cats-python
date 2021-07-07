import asyncio
import re
import tempfile
import warnings
from importlib import import_module
from logging import getLogger
from pathlib import Path
from time import time
from typing import Union

import math
import orjson

from cats.types import Json

__all__ = [
    'Delay',
    'require',
    'tmp_file',
    'int2hex',
    'bytes2hex',
    'format_amount',
    'enable_stream_debug',
    'filter_json',
]

logging = getLogger('CATS.utils')


class Delay:
    def __init__(self, speed: int = 0):
        self.speed = speed
        self.start = time()
        self.sent = 0

    def __enter__(self):
        self.start = time()
        self.sent = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...

    async def __call__(self, length: int = 0):
        if not self.speed:
            return

        went = time() - self.start + 0.01
        self.start = time()
        self.sent = max(0, length + self.sent - self.speed * went)
        if not self.sent:
            return
        await asyncio.sleep(self.sent / self.speed)


def tmp_file(**kwargs) -> Path:
    kwargs['delete'] = kwargs.get('delete', False)
    return Path(tempfile.NamedTemporaryFile(**kwargs).name)


def require(dotted_path: str, /, *, strict: bool = True):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        try:
            module_path, class_name = dotted_path.rsplit('.', 1)
        except ValueError as err:
            raise ImportError(f"{dotted_path} doesn't look like a module path") from err

        module = import_module(module_path)

        try:
            return getattr(module, class_name)
        except AttributeError as err:
            raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute/class') from err
    except ImportError as err:
        logging.error(f'Failed to import {dotted_path}')
        if strict:
            raise err
        return None


def int2hex(number: int, chars: int = 2) -> str:
    a = hex(number)[2:].upper()
    chars = max(len(a) // 2, chars)
    return ('00' * chars + a)[-chars * 2:]


def bytes2hex(buffer: Union[bytes, bytearray, memoryview], *, separator: str = ' ', prefix: bool = False) -> str:
    """
    Converts byte-like to HEX string

    :param buffer: what to encode
    :param separator: separator string
    :param prefix: use 0x prefix
    :return: HEX style string
    :raise TypeError:
    """
    if not isinstance(buffer, (bytes, bytearray, memoryview)):
        raise TypeError(f'Invalid buffer type = {type(buffer)}')

    hexadecimal = buffer.hex().upper()
    parts = (hexadecimal[i: i + 2] for i in range(0, len(hexadecimal), 2))
    if prefix:
        parts = ('0x' + part for part in parts)
    return separator.join(parts)


def format_amount(num: int, *, base: int = 1024, prefix: str = '', suffix: str = 'B') -> str:
    """
    Humanize any amount to string
    format_amount(0) == "0B"
    format_amount(1750) == "1.7KB"
    format_amount(1234567890) == "1.1GB"
    format_amount(2000, base=10, suffix='r') == "2Gr"

    :param num: numeric amount
    :param base: how much does the step takes (default 1024 as for bytes)
    :param prefix: type prefix (default '')
    :param suffix: type suffix (default B as for bytes)
    :return: Formatted amount string
    :raise TypeError:
    """
    if not num:
        return f'0{suffix}'

    if not isinstance(num, int):
        raise TypeError(f'Invalid num type = {type(num)}')

    if not isinstance(base, int):
        raise TypeError(f'Invalid base type = {type(base)}')

    sign = '-' if num < 0 else ''
    num = abs(num)

    magnitude = int(math.floor(math.log(num, base)))
    val = float(num / math.pow(base, magnitude))

    if magnitude > 7:
        val = f'{val:.0f}' if val.is_integer() else f'{val:.1f}'
        return f'{sign}{val}{"Y"}{prefix}{suffix}'

    val = f'{val:.0f}' if val.is_integer() else f'{val:3.1f}'
    return f'{sign}{val}{["", "K", "M", "G", "T", "P", "E", "Z"][magnitude]}{prefix}{suffix}'


def enable_stream_debug():
    warnings.warn("enable_stream_debug will be deprecated in version 4.0. "
                  "Use Server(debug=True) or Connection(debug=True) instead", PendingDeprecationWarning)
    from tornado.iostream import IOStream
    rb = IOStream.read_bytes
    ru = IOStream.read_until
    wr = IOStream.write

    async def read_bytes(self: IOStream, num_bytes, partial: bool = False):
        chunk = await rb(self, num_bytes, partial=partial)
        peer = self.socket.getpeername() if self.socket else ('0.0.0.0', 0)
        logging.info(f'[RECV {peer}] {bytes2hex(chunk)}')
        return chunk

    async def read_until(self: IOStream, delimiter: bytes, max_bytes: int = None):
        chunk = await ru(self, delimiter, max_bytes=max_bytes)
        peer = self.socket.getpeername() if self.socket else ('0.0.0.0', 0)
        logging.info(f'[RECV {peer}] {bytes2hex(chunk)}')
        return chunk

    async def write(self: IOStream, data):
        peer = self.socket.getpeername() if self.socket else ('0.0.0.0', 0)
        logging.info(f'[SEND {peer}] {bytes2hex(data)}')
        return await wr(self, data)

    IOStream.read_until = read_until
    IOStream.read_bytes = read_bytes
    IOStream.write = write


_HIDE = re.compile(r'.*(password|key|secret|jwt|pwd|пароль|ключ|секрет).*', re.IGNORECASE | re.UNICODE)


def filter_json(json: Json, max_len: int = 16, max_size: int = 64, indent: bool = False) -> str:
    option = 0
    if indent:
        option |= orjson.OPT_INDENT_2
    if isinstance(json, (bytes, bytearray, memoryview)):
        json = orjson.loads(json)
    return orjson.dumps(f_json(json, max_len, max_size), option=option).decode('utf-8')


def f_json(json: Json, max_len: int = 16, max_size: int = 64) -> Json:
    if isinstance(json, dict):
        return {
            k: '<masked>' if _HIDE.match(k) else f_json(v, max_len, max_size)
            for k, v in (*tuple(json.items())[:max_size], ('<more>', f'{len(json) - max_len} items'))[:len(json)]
        }
    if isinstance(json, list):
        return [
            f_json(v, max_len, max_size)
            for v in (*json[:max_size], f'{len(json) - max_len} more')[:len(json)]
        ]
    if isinstance(json, str) and len(json) > max_len:
        return json[:max_len] + '...'
    return json
