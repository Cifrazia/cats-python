from cats.v2.registry import Registry, Selector
from cats.v2.scheme.base import Scheme
from cats.v2.types import Data

__all__ = [
    'SchemeAPI',
]


class SchemeAPI(Registry):
    item_type = Scheme

    def loads(
        self, buff: bytes | str
    ) -> Data:
        if not self.registry:
            raise TypeError(f'No scheme is registered')
        error = None
        for scheme in self.registry.values():
            try:
                return scheme.loads(buff)
            except (TypeError, ValueError) as err:
                err.__cause__ = error
                error = err
        raise ValueError(f'Unable to unpack data, no supported scheme found') from error

    def dumps(
        self, selector: Selector, data: Data
    ) -> bytes:
        scheme = self.find_strict(selector)
        return scheme.dumps(data)
