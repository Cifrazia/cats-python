import hashlib
from asyncio import wait_for
from datetime import datetime, timezone
from logging import getLogger

from cats.errors import HandshakeError
from cats.utils import bytes2hex

__all__ = [
    'Handshake',
    'SHA256TimeHandshake',
]

logging = getLogger('CATS.conn')


class Handshake:
    async def validate(self, server, conn) -> None:
        raise NotImplementedError


class SHA256TimeHandshake(Handshake):
    __slots__ = ('secret_key', 'valid_window', 'timeout')

    def __init__(self, secret_key: bytes, valid_window: int = None, timeout: float = 5.0):
        assert isinstance(secret_key, bytes) and secret_key
        self.secret_key = secret_key
        self.valid_window = valid_window or 1
        self.timeout = timeout
        assert self.valid_window >= 1

    def get_hashes(self) -> list[str]:
        time = round(datetime.now(tz=timezone.utc).timestamp() / 10) * 10

        return [
            hashlib.sha256(self.secret_key + str(time + i * 10).encode('utf-8')).hexdigest()
            for i in range(-self.valid_window, self.valid_window + 1)
        ]

    async def validate(self, server, conn) -> None:
        handshake: bytes = await wait_for(conn.stream.read_bytes(64), self.timeout)
        conn.debug and logging.debug(f'[RECV {conn.address}] Handshake: {bytes2hex(handshake)}')
        try:
            if handshake.decode('utf-8') not in self.get_hashes():
                await conn.stream.write(b'\x00')
                conn.debug and logging.debug(f'[SEND {conn.address} Handshake failed')
                raise HandshakeError('Invalid handshake')
        except UnicodeDecodeError:
            await conn.stream.write(b'\x00')
            raise HandshakeError('Malformed handshake')
        else:
            await conn.stream.write(b'\x01')
            conn.debug and logging.debug(f'[SEND {conn.address}] Handshake passed')
