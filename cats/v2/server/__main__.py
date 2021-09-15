def main(host: str, port: int,
         handshake: bytes | None,
         api: int,
         input_timeout: float,
         idle_timeout: float,
         tls: bool,
         debug: bool):
    import logging
    from tornado.ioloop import IOLoop
    from cats.v2 import Config, SHA256TimeHandshake
    from cats.v2.server import Api, Application, Handler, Server

    logging.basicConfig(level='DEBUG' if debug else 'INFO', force=True)

    api = Api()

    class EchoHandler(Handler, api=api, id=0xFFFF):  # noqa
        async def handle(self):
            return self.action

    if handshake is not None:
        handshake = SHA256TimeHandshake(secret_key=handshake, valid_window=1, timeout=5.0)
    config = Config(
        idle_timeout=idle_timeout,
        input_timeout=input_timeout,
        input_limit=5,
        debug=debug,
        handshake=handshake
    )
    ssl_options = None
    if tls:
        from ssl import SSLContext, PROTOCOL_TLS_CLIENT, CERT_REQUIRED
        ssl_options = SSLContext(protocol=PROTOCOL_TLS_CLIENT)
        ssl_options.verify_mode = CERT_REQUIRED
        ssl_options.load_default_certs()

    app = Application([api], config=config)
    cats_server = Server(app, ssl_options=ssl_options)
    cats_server.bind(port, host)
    cats_server.start(1)
    IOLoop.current().start()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', '-H', dest='host', type=str,
                        default='0.0.0.0', help='CATS.v2.server host. Default: 0.0.0.0')
    parser.add_argument('--port', '-P', dest='port', type=int,
                        default=9191, help='CATS.v2.server port. Default: 9191')
    parser.add_argument('--handshake', dest='handshake', type=bytes,
                        default=None, help='Handshake secret key. Default: [disabled]')
    parser.add_argument('--input-timeout', dest='input_timeout', type=float,
                        default=120.0, help='Input timeout. Default: 120.0')
    parser.add_argument('--api', '-A', dest='api', type=int,
                        default=1, help='API version. Default: 1')
    parser.add_argument('--idle-timeout', dest='idle_timeout', type=float,
                        default=120.0, help='Idle timeout. Default: 120.0')
    parser.add_argument('--tls', '-T', dest='tls', action='store_true',
                        default=False, help='Enable TLS. Default: False')
    parser.add_argument('--debug', '-D', dest='debug', action='store_true',
                        default=False, help='Enable debug. Default: False')
    args = vars(parser.parse_args())
    try:
        main(**args)
    except KeyboardInterrupt:
        print()
