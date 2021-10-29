from cats.v2 import Data, Registry, Selector
from cats.v2.scheme.base import Scheme


class SchemeAPI(Registry):
    item_type = Scheme
    registry: dict[int, Scheme]
    named_registry: dict[str, Scheme]

    def loads(self, buff: bytes | str) -> Data: ...

    def dumps(self, selector: Selector, data: Data) -> bytes: ...

    def find(self, selector: Selector = None) -> Scheme | None: ...

    def find_strict(self, selector: Selector = None) -> Scheme: ...
