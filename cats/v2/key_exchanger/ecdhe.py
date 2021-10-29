from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf import KeyDerivationFunction, hkdf
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from cats.v2.key_exchanger.base import KeyExchanger

__all__ = [
    'ECDHE',
]


class ECDHE(KeyExchanger):
    __slots__ = ('curve', 'kdf')
    type_id = 0
    type_name = 'ECDHE'

    def __init__(self, curve: ec.EllipticCurve = ec.SECP384R1(), kdf: KeyDerivationFunction = None):
        super().__init__()
        self.curve: ec.EllipticCurve = curve
        self.private_key: ec.EllipticCurvePrivateKey | None = None
        self.peer_key: ec.EllipticCurvePublicKey | None = None
        self.kdf: KeyDerivationFunction = kdf or hkdf.HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=None)

    def public_bytes(self) -> bytes:
        return self.private_key.public_key().public_bytes(Encoding.X962, PublicFormat.CompressedPoint)

    def generate(self):
        self.private_key = ec.generate_private_key(self.curve)
        self.peer_key = b''
        self.shared_key = b''
        self.derived_key = b''

    def derive(self, public_key: bytes) -> bytes:
        self.peer_key = ec.EllipticCurvePublicKey.from_encoded_point(self.curve, public_key)
        self.shared_key = self.private_key.exchange(ec.ECDH(), self.peer_key)
        self.derived_key = self.kdf.derive(self.shared_key)
        return self.derived_key
