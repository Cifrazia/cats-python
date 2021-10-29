from cats.v2.key_exchanger.base import KeyExchanger
from cats.v2.registry import Registry

__all__ = [
    'KeyExchangerAPI',
]


class KeyExchangerAPI(Registry):
    item_type = KeyExchanger
