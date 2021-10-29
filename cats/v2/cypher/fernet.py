from cryptography.fernet import Fernet

from cats.v2.cypher.base import Cypher
from cats.v2.errors import InvalidCypher

__all__ = [
    'FernetCypher',
]


class FernetCypher(Cypher):
    type_id = 0
    type_name = 'fernet'

    async def encrypt(
        self, data: bytes, key: bytes
    ) -> bytes:
        fernet = Fernet(key)
        if not key:
            raise InvalidCypher
        return fernet.encrypt(data)

    async def decrypt(
        self, data: bytes, key: bytes
    ) -> bytes:
        fernet = Fernet(key)
        if not key:
            raise InvalidCypher
        return fernet.decrypt(data)
