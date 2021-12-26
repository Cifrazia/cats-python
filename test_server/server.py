import asyncio
import os

from pydantic import BaseModel, conint, constr
from tornado.ioloop import IOLoop

from cats.v2 import (
    Action, C_NONE, C_ZLIB, Config, SHA256TimeHandshake, StreamAction,
    T_BYTE,
)
from cats.v2.server import Api, Application, Handler, Server

api = Api()


class VoidHandler(Handler, api=api, id=0x0000, name='no response'):
    async def handle(self):
        return


class EchoPlainHandler(Handler, api=api, id=0x0001, name='echo plain handler'):
    async def handle(self):
        a = self.action
        return Action(a.data, headers=a.headers, compression=C_NONE)


class EchoZlibHandler(Handler, api=api, id=0x0002, name='echo zlib handler'):
    async def handle(self):
        a = self.action
        return Action(a.data, headers=a.headers, compression=C_ZLIB)


class VersionedHandler(Handler, api=api, id=0x0010, version=1):
    async def handle(self):
        return Action({'version': 1})


class VersionedHandler2(Handler, api=api, id=0x0010, version=3, end_version=4):
    async def handle(self):
        return Action({'version': 2})


class VersionedHandler3(Handler, api=api, id=0x0010, version=6):
    async def handle(self):
        return Action({'version': 3})


class DelayedHandler(Handler, api=api, id=0x0020, name='delayed response'):
    async def gen(self):
        yield b'hello'
        await asyncio.sleep(0.01)
        yield b' world'
        await asyncio.sleep(0.01)
        yield b'!'

    async def handle(self):
        return StreamAction(self.gen(), data_type=T_BYTE)


class InputHandler(Handler, api=api, id=0x0030, name='internal requests'):
    async def handle(self):
        reply = await self.ask(b'Are you ok?')
        if reply.data == b'yes':
            return Action(b'Nice!')
        else:
            return Action(b'Sad!')


class InputJSONHandler(Handler, api=api, id=0x0031, name='internal json requests'):
    async def handle(self):
        reply = await self.ask('Are you ok?')
        if reply.data == 'yes':
            return Action('Nice!')
        else:
            return Action('Sad!')


class JsonFormHandler(Handler, api=api, id=0x0040):
    class Loader(BaseModel):
        id: conint(ge=0, le=10)
        name: constr(min_length=3, max_length=16)

    class Dumper(BaseModel):
        token: constr(min_length=64, max_length=64)
        code: constr(min_length=6, max_length=6)

    async def handle(self):
        user = await self.json_load()
        return await self.json_dump(
            {
                'token': os.urandom(32).hex(),
                'code': os.urandom(3).hex(),
            }
        )


class Broadcast(Handler, api=api, id=0x0050):
    async def handle(self):
        raise NotImplementedError


def main():
    import logging
    logging.basicConfig(level=logging.DEBUG, force=True)
    server_core = int(os.environ.get('SERVER_CORE', '1'))
    hash_secret = os.environ.get('HANDSHAKE_SECRET', 't0ps3cr3t').encode('utf-8')

    handshake = SHA256TimeHandshake(
        secret_key=hash_secret,
        valid_window=1,
        timeout=5.0,
    )
    config = Config(
        idle_timeout=120.0,
        input_timeout=120.0,
        input_limit=5,
        debug=True,
        handshake=handshake,
    )
    app = Application([api], config=config)
    server = Server(app)
    server.bind(9095, '0.0.0.0')
    server.start(server_core)

    async def broadcast():
        while True:
            for srv in server.running_servers():
                for conn in srv.connections:
                    await conn.send(Broadcast.handler_id, b'ping!')
            await asyncio.sleep(5)

    loop = IOLoop.current()
    loop.spawn_callback(broadcast)
    loop.start()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('')
        print('Server closed')
