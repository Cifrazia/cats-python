from cats.v2.codecs.base import Codec
from cats.v2.errors import CodecError, InvalidCodec
from cats.v2.forms import BaseModel, BaseSerializer, ModelSchema, SubForms, form_dump
from cats.v2.headers import T_Headers
from cats.v2.options import Options
from cats.v2.types import Data, List

__all__ = [
    'SchemeCodec',
]


class SchemeCodec(Codec):
    type_id = 0x01
    type_name = 'scheme'

    async def encode(
        self, data: Data | SubForms | list[SubForms], headers: T_Headers, options: Options
    ) -> bytes:
        try:
            if data is None or isinstance(data, str | int | float | bool | dict):
                result = data
            elif isinstance(data, (BaseModel, BaseSerializer, ModelSchema)):
                result = form_dump(type(data), data, many=False, plain=True)
            elif isinstance(data, List):
                result = list(data)
                if isinstance(data[0], (BaseModel, BaseSerializer, ModelSchema)):
                    result = form_dump(type(result[0]), result, many=True, plain=True)
            else:
                raise TypeError
            return options.scheme.dumps(result)
        except TypeError as err:
            raise InvalidCodec(f'{self} does not support {type(data)}',
                               data=data, headers=headers, options=options) from err

    async def decode(
        self, data: bytes, headers, options: Options
    ) -> Data:
        if not data:
            return {}

        try:
            return options.scheme.loads(data)
        except ValueError as err:
            raise CodecError('Failed to parse scheme from data', data=data, headers=headers, options=options) from err
