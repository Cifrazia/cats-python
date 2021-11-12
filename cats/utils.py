import asyncio
import importlib
import math
import re
import tempfile
from logging import getLogger
from pathlib import Path
from time import time

import ujson

from cats.types import Bytes, Json

__all__ = [
    'to_uint',
    'as_uint',
    'Delay',
    'require',
    'tmp_file',
    'int2hex',
    'bytes2hex',
    'format_amount',
    'filter_json',
]

logging = getLogger('CATS.utils')


def to_uint(number: int, length: int = None) -> bytes:
    if length is None:
        length = (number.bit_length() + 7) // 8
    return number.to_bytes(length, byteorder='big', signed=False)


def as_uint(data: bytes) -> int:
    return int.from_bytes(data, byteorder='big', signed=False)


class Delay:
    """
    Rate-limiter, that calls asyncio.sleep(N), each time an object called.
    N is calculated based on specified speed, size of latest chunk and ∆time
    """

    def __init__(self, speed: int = 0):
        self.speed: int = speed
        self.start: float = time()
        self.sent: float = 0.0

    async def __call__(self, length: int = 0):
        if not self.speed:
            return

        went = time() - self.start + 0.01
        self.start = time()
        self.sent = max(0.0, length + self.sent - self.speed * went)
        if not self.sent:
            return
        await asyncio.sleep(self.sent / self.speed)


def tmp_file(**kwargs) -> Path:
    """
    Creates NamedTemporaryFile and returns associated pathlib.Path
    :param kwargs: NamedTemporaryFile arguments
    :return: pathlib.Path(temp_file)
    """
    kwargs['delete'] = kwargs.get('delete', False)
    return Path(tempfile.NamedTemporaryFile(**kwargs).name)


def require(dotted_path: str, /, *, strict: bool = True):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.

    :param dotted_path: Path to attribute/class in module
    :param strict: should the error be thrown
    :return: attribute/class
    """
    try:
        try:
            module_path, class_name = dotted_path.rsplit('.', 1)
        except ValueError as err:
            raise ImportError(f"{dotted_path} doesn't look like a module path") from err

        module = importlib.import_module(module_path)

        try:
            return getattr(module, class_name)
        except AttributeError as err:
            raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute/class') from err
    except ImportError:
        logging.error(f'Failed to import {dotted_path}')
        if strict:
            raise
        return None


def int2hex(number: int, chars: int = 2) -> str:
    """
    Converts integers to human-readable HEX
    :param number: integer to convert
    :param chars: minimal amount of chars(bytes) to show
    :return: HEX string w/o prefix
    """
    a = hex(number)[2:].upper()
    chars = max(len(a) // 2, chars)
    return ('00' * chars + a)[-chars * 2:]


def bytes2hex(buffer: Bytes, *, separator: str = ' ', prefix: bool = False) -> str:
    """
    Converts byte-like to HEX string

    :param buffer: what to encode
    :param separator: separator string
    :param prefix: use 0x prefix
    :return: HEX style string
    :raise TypeError:
    """
    if not isinstance(buffer, Bytes):
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


_HIDE = re.compile(r'.*(password|key|secret|jwt|pwd|пароль|ключ|секрет).*', re.IGNORECASE | re.UNICODE)


def filter_json(json: Json | Bytes, max_len: int = 16, max_size: int = 64, indent: bool = False) -> str:
    if isinstance(json, Bytes):
        json = ujson.loads(json)
    result = _filter_json_part(json, max_len, max_size)
    return ujson.dumps(result, ensure_ascii=False, escape_forward_slashes=False, indent=2 if indent else 0)


def _filter_json_part(json: Json, max_len: int = 16, max_size: int = 64) -> Json:
    if isinstance(json, dict):
        return {
            k:
                '<masked>' if (isinstance(k, str) and _HIDE.match(k))
                else v if str(k).lower() in ('error', 'exception')
                else _filter_json_part(v, max_len, max_size)
            for k, v in (*tuple(json.items())[:max_size], ('<more>', f'{len(json) - max_len} items'))[:len(json)]
        }
    if isinstance(json, list):
        return [
            _filter_json_part(v, max_len, max_size)
            for v in (*json[:max_size], f'{len(json) - max_len} more')[:len(json)]
        ]
    if isinstance(json, str) and len(json) > max_len:
        return json[:max_len] + '...'
    return json
