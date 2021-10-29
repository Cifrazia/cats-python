from dataclasses import dataclass
from io import BytesIO
from os.path import getsize
from pathlib import Path
from typing import IO, TypeAlias

from cats.v2.codecs.base import Codec
from cats.v2.errors import CodecError, InvalidCodec, InvalidData, MalformedHeaders
from cats.v2.headers import Header, T_Headers
from cats.v2.options import Options
from cats.v2.utils import tmp_file

__all__ = [
    'FileInfo',
    'Files',
    'FILE_TYPES',
    'FileCodec',
]


@dataclass
class FileInfo:
    name: str
    path: Path
    size: int
    mime: str | None = None


class Files(dict):
    def __init__(
        self, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        for k, v in self.items():
            if not isinstance(k, str):
                raise InvalidData('File key must be string', data=self)
            elif not isinstance(v, FileInfo):
                raise InvalidData('File value must be FileInfo', data=self)

    def __del__(self):
        try:
            for v in self.values():
                v.path.unlink(missing_ok=True)
        except AttributeError:
            pass


FILE_TYPES: TypeAlias = Path | list[Path] | dict[str, Path] | FileInfo | list[FileInfo] | dict[str, FileInfo]


class FileCodec(Codec):
    __slots__ = ('encoding',)
    type_id = 0x02
    type_name = 'files'

    def __init__(self, encoding: str = 'utf-8'):
        self.encoding = encoding

    async def encode(
        self, data: FILE_TYPES, headers: T_Headers, options: Options
    ) -> Path:
        tmp = tmp_file()
        offset = headers.get(Header.offset, 0)
        try:
            buff = tuple(self.normalize_input(data).items())
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
                        while buff := f_fh.read(min(left, 1 << 24)):
                            fh.write(buff)
                            left -= len(buff)
            headers['Files'] = header
            return tmp

        except (KeyError, ValueError, TypeError, AttributeError) as err:
            tmp.unlink(missing_ok=True)
            raise InvalidCodec(f'{self} does not support {type(data)}',
                               data=data, headers=headers, options=options) from err

    async def decode(
        self, data: Path | bytes | bytearray, headers, options: Options
    ) -> Files:
        result = Files()
        buff = data.open('rb') if isinstance(data, Path) else BytesIO(data)

        try:
            if 'Files' not in headers:
                raise MalformedHeaders('Failed to parse Files meta data from headers', headers=headers)

            header = headers['Files']

            if not isinstance(header, list):
                raise MalformedHeaders(f'Files headers must be list, {type(header)} provided', headers=headers)

            for i, node in enumerate(header):
                if not isinstance(node, dict):
                    raise MalformedHeaders(f'Files header item[{i}] must be dict, {type(node)} provided',
                                           headers=headers)

                tmp = await self._unpack_file(buff, node)
                result[node['key']] = FileInfo(
                    name=node['name'],
                    path=tmp,
                    size=node['size'],
                    mime=node.get('type'),
                )

            return result
        except MalformedHeaders:
            raise
        except (KeyError, ValueError, TypeError) as err:
            for v in result.values():
                v.path.unlink(missing_ok=True)
            raise CodecError('Failed to parse Files from data', data=data, headers=headers, options=options) from err
        finally:
            buff.close()

    def path_to_file_info(
        self, path: Path | FileInfo
    ) -> FileInfo:
        if isinstance(path, FileInfo):
            return path
        elif isinstance(path, Path):
            return FileInfo(path.name, path, getsize(path.as_posix()), None)
        raise TypeError

    def normalize_input(
        self, data: FILE_TYPES
    ) -> dict[str, FileInfo]:
        if isinstance(data, Path):
            data = self.path_to_file_info(data)
        elif isinstance(data, list):
            data = [self.path_to_file_info(i) for i in data]

        elif isinstance(data, dict):
            res = {}
            for k, v in data.items():
                if not isinstance(k, str):
                    raise TypeError
                res[k] = self.path_to_file_info(v)
            data = res
        elif not isinstance(data, FileInfo):
            raise TypeError

        if isinstance(data, FileInfo):
            return {data.name: data}
        elif isinstance(data, list):
            return {i.name: i for i in data}
        else:
            return data

    async def _unpack_file(
        self, fh: IO, node
    ) -> Path:
        tmp = tmp_file()
        left = node['size']
        with tmp.open('wb') as node_fh:
            while left > 0:
                buff = fh.read(min(left, 1 << 24))
                if not len(buff):
                    raise ValueError('Failed to unpack file: not enough bytes')
                node_fh.write(buff)
                left -= len(buff)
        return tmp
