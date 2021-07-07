from dataclasses import dataclass
from io import BytesIO
from os.path import getsize
from pathlib import Path
from typing import Any, IO, Optional, Union

import orjson

from cats.plugins import BaseModel, BaseSerializer, Form, ModelSchema, scheme_json
from cats.types import Byte, Json, List, T_Headers
from cats.utils import tmp_file

__all__ = [
    'FileInfo',
    'Files',
    'BaseCodec',
    'ByteCodec',
    'JsonCodec',
    'FileCodec',
    'T_BYTE',
    'T_JSON',
    'T_FILE',
    'Codec',
]


@dataclass
class FileInfo:
    name: str
    path: Path
    size: int
    mime: Optional[str]


class Files(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in self.items():
            if not isinstance(k, str):
                raise ValueError('File key must be string')
            elif not isinstance(v, FileInfo):
                raise ValueError('File value must be FileInfo')

    def __del__(self):
        for v in self.values():
            v.path.unlink(missing_ok=True)


class BaseCodec:
    type_id: int
    type_name: str

    @classmethod
    async def encode(cls, data: Any, headers: T_Headers) -> bytes:
        """
        :raise TypeError: Encoder doesn't support this type
        :raise ValueError: Failed to encode
        """
        raise NotImplementedError

    @classmethod
    async def decode(cls, data: Union[bytes, Path], headers: T_Headers) -> Any:
        """
        :raise TypeError: Encoder doesn't support this type
        :raise ValueError: Failed to decode
        """
        raise NotImplementedError


class ByteCodec(BaseCodec):
    type_id = 0x00
    type_name = 'bytes'

    @classmethod
    async def encode(cls, data: Byte, headers: T_Headers, offset: int = 0) -> bytes:
        if data is not None and not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f'{cls.__name__} does not support {type(data).__name__}')

        return (bytes(data) if data else bytes())[offset:]

    @classmethod
    async def decode(cls, data: bytes, headers: T_Headers) -> bytes:
        return bytes(data) if data else bytes()


JSON = Union[Json, Form, list[Form]]


class JsonCodec(BaseCodec):
    type_id = 0x01
    type_name = 'json'

    @classmethod
    async def encode(cls, data: JSON, headers: T_Headers, offset: int = 0) -> bytes:
        if data:
            if isinstance(data, (BaseModel, BaseSerializer, ModelSchema)):
                return scheme_json(type(data), data, many=False, plain=True)
            elif isinstance(data, List):
                data = list(data)
                if isinstance(data[0], (BaseModel, BaseSerializer, ModelSchema)):
                    return scheme_json(type(data[0]), data, many=True, plain=True)
        return await cls._encode(data, offset=offset)

    @classmethod
    async def _encode(cls, data: Json, offset: int = 0) -> bytes:
        if not isinstance(data, (str, int, float, dict, list, bool, type(None))):
            raise TypeError(f'{cls.__name__} does not support {type(data).__name__}')

        return orjson.dumps(data)[offset:]

    @classmethod
    async def decode(cls, data: bytes, headers) -> Union[dict, Json]:
        if not data:
            return {}

        try:
            return orjson.loads(data)
        except ValueError:
            raise ValueError('Failed to parse JSON from data')


FILE_TYPES = Union[
    Path, list[Path], dict[str, Path],
    FileInfo, list[FileInfo], dict[str, FileInfo],
]


class FileCodec(BaseCodec):
    type_id = 0x02
    type_name = 'files'
    encoding = 'utf-8'

    @classmethod
    def path_to_file_info(cls, path: Path) -> FileInfo:
        if not isinstance(path, Path):
            raise TypeError
        return FileInfo(path.name, path, getsize(path.as_posix()), None)

    @classmethod
    def normalize_input(cls, data: FILE_TYPES) -> dict[str, FileInfo]:
        if isinstance(data, Path):
            data = cls.path_to_file_info(data)
        elif isinstance(data, list):
            res = []
            for i in data:
                if not isinstance(i, (FileInfo, Path)):
                    raise TypeError
                res.append(i if isinstance(i, FileInfo) else cls.path_to_file_info(i))

        elif isinstance(data, dict):
            res = {}
            for k, v in data.items():
                if not isinstance(k, str) or not isinstance(v, (FileInfo, Path)):
                    raise TypeError
                res[k] = v if isinstance(v, FileInfo) else cls.path_to_file_info(v)
        elif not isinstance(data, FileInfo):
            raise TypeError

        if isinstance(data, FileInfo):
            return {data.name: data}
        elif isinstance(data, list):
            return {i.name: i for i in data}
        else:
            return data

    @classmethod
    async def encode(cls, data: FILE_TYPES, headers: T_Headers, offset: int = 0) -> Path:
        tmp = tmp_file()
        try:
            buff = tuple(cls.normalize_input(data).items())
            header = []
            with tmp.open('wb') as fh:
                for key, info in buff:
                    left = info.size - offset
                    offset = max(0, offset - left)
                    if left < 0:
                        continue
                    header.append({"key": key, "name": info.name, "size": left, "type": info.mime})
                    with info.path.open('rb') as f_fh:
                        f_fh.seek(info.size - left)
                        while left > 0:
                            buff = f_fh.read(1 << 24)
                            if not len(buff):
                                raise ValueError
                            fh.write(buff)
                            left -= len(buff)
            headers['Files'] = header
            return tmp

        except (KeyError, ValueError, TypeError, AttributeError):
            tmp.unlink(missing_ok=True)
            raise TypeError(f'{cls.__name__} does not support {type(data).__name__}')

    @classmethod
    async def decode(cls, data: Union[Path, bytes, bytearray], headers) -> Files:
        result = Files()
        buff = data.open('rb') if isinstance(data, Path) else BytesIO(data)

        try:
            if 'Files' not in headers:
                raise ValueError('Failed to parse Files meta data from headers')

            header = headers['Files']

            if not isinstance(header, list):
                raise ValueError

            for node in header:
                if not isinstance(node, dict):
                    raise ValueError

                tmp = await cls._unpack_file(buff, node)
                result[node['key']] = FileInfo(
                    name=node['name'],
                    path=tmp,
                    size=node['size'],
                    mime=node.get('type'),
                )

            return result
        except (KeyError, ValueError, TypeError):
            for v in result.values():
                v.path.unlink(missing_ok=True)
            raise ValueError('Failed to parse Files form data')
        finally:
            buff.close()

    @classmethod
    async def _unpack_file(cls, fh: IO, node) -> Path:
        tmp = tmp_file()
        left = node['size']
        with tmp.open('wb') as node_fh:
            while left > 0:
                buff = fh.read(min(left, 1 << 24))
                if not len(buff):
                    raise ValueError
                node_fh.write(buff)
                left -= len(buff)
        return tmp


T_BYTE = ByteCodec.type_id
T_JSON = JsonCodec.type_id
T_FILE = FileCodec.type_id


class Codec:
    codecs = {
        T_BYTE: ByteCodec,
        T_JSON: JsonCodec,
        T_FILE: FileCodec,
    }

    @classmethod
    async def encode(cls, buff: Union[Byte, Json, FILE_TYPES], headers: T_Headers, offset: int = 0) -> (bytes, int):
        """
        Takes any supported data type and returns tuple (encoded: bytes, type_id: int)
        """
        for type_id, codec in cls.codecs.items():
            try:
                encoded = await codec.encode(buff, headers, offset)
                return encoded, type_id
            except TypeError:
                continue

        raise TypeError(f'Failed to encode data: Type {type(buff).__name__} not supported')

    @classmethod
    async def decode(cls, buff: Union[Byte, Path], data_type: int, headers: T_Headers) -> Union[Byte, Json, Files]:
        """
        Takes byte buffer, type_id and try to decode it to internal data types
        """
        if data_type not in cls.codecs:
            raise TypeError(f'Failed to decode data: Type {data_type} not supported')

        return await cls.codecs[data_type].decode(buff, headers)

    def get_codec_name(self, type_id: int, default: str = 'unknown') -> str:
        """
        Returns Type Name by it's id (w/ fallback to default)
        :param type_id:
        :param default:
        :return:
        """
        try:
            return self.codecs[type_id].type_name
        except KeyError:
            return default
