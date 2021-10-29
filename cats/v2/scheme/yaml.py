import yaml

from cats.v2.errors import MalformedData
from cats.v2.scheme.base import Scheme
from cats.v2.types import Data

__all__ = [
    'YAML',
]


class YAML(Scheme):
    type_id = 2
    type_name = 'yaml'

    def loads(self, buff: bytes | str) -> Data:
        try:
            return yaml.safe_load(buff)
        except (ValueError, yaml.YAMLError) as err:
            raise MalformedData(f'Failed to parse YAML from buffer', data=buff) from err

    def dumps(self, data: Data) -> bytes:
        r: bytes = yaml.safe_dump(data, encoding='utf-8')
        return r.removesuffix(b'...\n').removesuffix(b'\n')
