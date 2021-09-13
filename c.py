import asyncio

from cats.v2 import Config, SHA256TimeHandshake
from cats.v2.client import Connection


# from ssl import PROTOCOL_TLS_CLIENT, SSLContext, CERT_REQUIRED


async def main():
    handshake = SHA256TimeHandshake(secret_key=b't0ps3cr3t', valid_window=1, timeout=5.0)
    config = Config(
        idle_timeout=120.0,
        input_timeout=120.0,
        input_limit=5,
        debug=True,
        handshake=handshake
    )
    conn = Connection(config, api_version=1)
    # ssl_options = SSLContext(protocol=PROTOCOL_TLS_CLIENT)
    # ssl_options.verify_mode = CERT_REQUIRED
    # ssl_options.load_default_certs()
    # await conn.connect('me-testing.cifrazia.com', 17000, ssl_options=ssl_options)
    await conn.connect('185.137.235.92', 17210)
    while data := input('Message: '):
        print()
        result = await conn.send(0xFFFF, data)
        print(f'{result = }')


if __name__ == '__main__':
    asyncio.run(main())
