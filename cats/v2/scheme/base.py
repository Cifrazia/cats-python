from abc import ABC

from cats.v2.registry import Item
from cats.v2.types import Data

__all__ = [
    'Scheme',
]


class Scheme(Item, ABC):
    def loads(self, buff: bytes | str) -> Data:
        """
        Parse byte/str buffer to data (primitives or list/dict of primitives)
        :param buff: Encoded buffer
        :type buff: bytes | str
        :return: Decoded buffer
        """
        raise NotImplementedError

    def dumps(self, data: Data) -> bytes:
        """
        Encode data into byte buffer
        :param data: primitives or list/dict of primitives
        :type data: Data
        :return: Encoded buffer
        """
        raise NotImplementedError
