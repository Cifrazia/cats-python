from enum import IntEnum
from typing import TypeAlias

import msgpack
import toml
import ujson
import yaml

__all__ = [
    'Data',
    'SchemeType',
    'Scheme',
    'JSON',
    'YAML',
    'TOML',
    'MsgPack',
]

Data: TypeAlias = int | float | bool | str | None
Data: TypeAlias = Data | list[Data] | dict[str, Data]


class SchemeType(IntEnum):
    json = 1
    yaml = 2
    toml = 3
    msgpack = 4


class Scheme:
    id: SchemeType

    @classmethod
    def loads(cls, buff: bytes | str) -> Data:
        """
        Parse byte/str buffer to data (primitives or list/dict of primitives)
        :param buff: Encoded buffer
        :type buff: bytes | str
        :return: Decoded buffer
        """
        raise NotImplementedError

    @classmethod
    def dumps(cls, data: Data) -> bytes:
        """
        Encode data into byte buffer
        :param data: primitives or list/dict of primitives
        :type data: Data
        :return: Encoded buffer
        """
        raise NotImplementedError


class JSON(Scheme):
    id = SchemeType.json

    @classmethod
    def loads(cls, data: bytes | str) -> Data:
        return ujson.loads(data)

    @classmethod
    def dumps(cls, data: Data) -> bytes:
        return ujson.dumps(data).encode('utf-8')


class YAML(Scheme):
    id = SchemeType.yaml

    @classmethod
    def loads(cls, buff: bytes | str) -> Data:
        return yaml.safe_load(buff)

    @classmethod
    def dumps(cls, data: Data) -> bytes:
        return yaml.safe_dump(data, encoding='utf-8')


class TOML(Scheme):
    id = SchemeType.toml

    @classmethod
    def loads(cls, buff: bytes | str) -> Data:
        return toml.loads(buff)

    @classmethod
    def dumps(cls, data: Data) -> bytes:
        return toml.dumps(data).encode('utf-8')


class MsgPack(Scheme):
    id = SchemeType.msgpack

    @classmethod
    def loads(cls, buff: bytes) -> Data:
        return msgpack.loads(buff)

    @classmethod
    def dumps(cls, data: Data) -> bytes:
        return msgpack.dumps(data)
