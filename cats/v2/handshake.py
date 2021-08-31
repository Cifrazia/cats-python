import asyncio
import hashlib
from time import time

from cats.errors import HandshakeError
from cats.utils import bytes2hex

__all__ = [
    'Handshake',
    'SHA256TimeHandshake',
]


class Handshake:
    async def validate(self, conn) -> None:
        """
        Read stream, check for valid handshake
        If valid: send 0x01 to stream
        Otherwise: send 0x00 to stream and close
        :param conn:
        :return:
        """
        raise NotImplementedError

    async def send(self, conn) -> None:
        """
        Send valid handshake to stream and read answer
        If 0x01 - passing
        Otherwise: raising HandshakeError
        :param conn:
        :return:
        """
        raise NotImplementedError


class SHA256TimeHandshake(Handshake):
    __slots__ = ('secret_key', 'valid_window', 'timeout')

    def __init__(self, secret_key: bytes, valid_window: int = None, timeout: int | float = 5.0):
        assert isinstance(secret_key, bytes) and secret_key
        self.secret_key = secret_key
        self.valid_window = valid_window or 1
        self.timeout = timeout
        assert self.valid_window >= 1

    def get_hashes(self, timestamp: float) -> list[bytes]:
        ts = round(timestamp / 10) * 10

        return [
            hashlib.sha256(self.secret_key + str(ts + i * 10).encode('utf-8')).digest()
            for i in range(-self.valid_window, self.valid_window + 1)
        ]

    async def validate(self, conn) -> None:
        handshake: bytes = await asyncio.wait_for(conn.read(32), self.timeout)
        conn.debug(f'[RECV {conn.address}] Handshake: {bytes2hex(handshake)}')
        try:
            if handshake not in self.get_hashes(time()):
                await conn.write(b'\x00')
                conn.debug(f'[SEND {conn.address} Handshake failed')
                raise HandshakeError('Invalid handshake')
        except UnicodeDecodeError:
            await conn.write(b'\x00')
            raise HandshakeError('Malformed handshake')
        else:
            await conn.write(b'\x01')
            conn.debug(f'[SEND {conn.address}] Handshake passed')

    async def send(self, conn) -> None:
        await conn.write(self.get_hashes(conn.time_delta + time())[1])
        result = await conn.read(1)
        if result == b'\x01':
            conn.debug(f'[SEND {conn.address}] Handshake passed')
            return
        raise HandshakeError('Invalid handshake')
