from abc import ABC

from cats.v2.registry import Item

__all__ = [
    'KeyExchanger',
]


class KeyExchanger(Item, ABC):
    __slots__ = ('private_key', 'peer_key', 'shared_key', 'derived_key')

    def __init__(self):
        self.private_key = None
        self.peer_key = None
        self.shared_key: bytes = b''
        self.derived_key: bytes = b''

    def public_bytes(self) -> bytes:
        raise NotImplementedError

    def generate(self):
        raise NotImplementedError

    def derive(self, public_key: bytes) -> bytes:
        raise NotImplementedError
