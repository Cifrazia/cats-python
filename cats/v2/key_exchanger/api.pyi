from cats.v2 import Registry, Selector
from cats.v2.key_exchanger.base import KeyExchanger


class KeyExchangerAPI(Registry):
    item_type = KeyExchanger
    registry: dict[int, KeyExchanger]
    named_registry: dict[str, KeyExchanger]

    def find(self, selector: Selector = None) -> KeyExchanger | None: ...

    def find_strict(self, selector: Selector = None) -> KeyExchanger: ...
