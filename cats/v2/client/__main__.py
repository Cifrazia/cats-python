from tornado.iostream import StreamClosedError

from cats.errors import HandshakeError, ProtocolError
from cats.v2.action import PingAction


async def main(
    host: str, port: int,
    handshake: bytes | None,
    api: int,
    input_timeout: float,
    idle_timeout: float,
    tls: bool,
    debug: bool
):
    import logging
    from cats.v2 import Config, SHA256TimeHandshake
    from cats.v2.client import Connection

    logging.basicConfig(level='DEBUG' if debug else 'INFO', force=True)

    if handshake is not None:
        handshake = SHA256TimeHandshake(secret_key=handshake, valid_window=1, timeout=5.0)
    config = Config(
        idle_timeout=idle_timeout,
        input_timeout=input_timeout,
        input_limit=5,
        debug=debug,
        handshake=handshake,
    )
    conn = Connection(config, api_version=api)
    ssl_options = None
    if tls:
        from ssl import SSLContext, PROTOCOL_TLS_CLIENT, CERT_REQUIRED
        ssl_options = SSLContext(protocol=PROTOCOL_TLS_CLIENT)
        ssl_options.verify_mode = CERT_REQUIRED
        ssl_options.load_default_certs()

    try:
        await conn.connect(host, port, ssl_options=ssl_options)
        await PingAction().send(conn)
        exit(int(not conn.is_open))
    except (HandshakeError, ProtocolError):
        exit(0)
    except StreamClosedError:
        exit(1)
    except Exception:
        exit(500)
        raise


if __name__ == '__main__':
    import asyncio
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--host', '-H', dest='host', type=str,
        default='127.0.0.1', help='CATS.v2.server host. Default: 127.0.0.1',
    )
    parser.add_argument(
        '--port', '-P', dest='port', type=int,
        default=9191, help='CATS.v2.server port. Default: 9191',
    )
    parser.add_argument(
        '--handshake', dest='handshake', type=bytes,
        default=None, help='Handshake secret key. Default: [disabled]',
    )
    parser.add_argument(
        '--input-timeout', dest='input_timeout', type=float,
        default=120.0, help='Server`s input timeout. Default: 120.0',
    )
    parser.add_argument(
        '--api', '-A', dest='api', type=int,
        default=1, help='API version. Default: 1',
    )
    parser.add_argument(
        '--idle-timeout', dest='idle_timeout', type=float,
        default=120.0, help='Server`s idle timeout. Default: 120.0',
    )
    parser.add_argument(
        '--tls', '-T', dest='tls', action='store_true',
        default=False, help='Enable TLS. Default: False',
    )
    parser.add_argument(
        '--debug', '-D', dest='debug', action='store_true',
        default=False, help='Enable debug. Default: False',
    )
    args = vars(parser.parse_args())
    asyncio.run(main(**args))
