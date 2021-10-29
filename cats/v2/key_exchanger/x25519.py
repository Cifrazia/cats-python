from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf import KeyDerivationFunction, hkdf
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from cats.v2.key_exchanger.base import KeyExchanger

__all__ = [
    'X25519',
]


class X25519(KeyExchanger):
    __slots__ = ('kdf',)
    type_id = 1
    type_name = 'X25519'

    def __init__(self, kdf: KeyDerivationFunction = None):
        super().__init__()
        self.private_key: x25519.X25519PrivateKey | None = None
        self.peer_key: x25519.X25519PublicKey | None = None
        self.kdf: KeyDerivationFunction = kdf or hkdf.HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=None)

    def public_bytes(self) -> bytes:
        return self.private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    def generate(self):
        self.private_key = x25519.X25519PrivateKey.generate()
        self.peer_key = b''
        self.shared_key = b''
        self.derived_key = b''

    def derive(self, public_key: bytes) -> bytes:
        self.peer_key = x25519.X25519PublicKey.from_public_bytes(public_key)
        self.shared_key = self.private_key.exchange(self.peer_key)
        self.derived_key = self.kdf.derive(self.shared_key)
        return self.derived_key
