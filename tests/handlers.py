import os
from asyncio import sleep

from pydantic import BaseModel, Field

from cats.codecs import T_BYTE
from cats.server import Action, Api, Handler, StreamAction

__all__ = [
    'api',
    'EchoHandler',
    'VoidHandler',
    'VersionedHandler',
    'VersionedHandler2',
    'VersionedHandler3',
    'DelayedHandler',
    'InputHandler',
    'InputJSONHandler',
    'JsonFormHandler',
]

api = Api()


class EchoHandler(Handler, api=api, id=0x0000, name='echo handler'):
    async def handle(self):
        return self.action


class VoidHandler(Handler, api=api, id=0x0001, name='no response'):
    async def handle(self):
        return


class VersionedHandler(Handler, api=api, id=0x0002, version=1):
    async def handle(self):
        return Action({'version': 1})


class VersionedHandler2(Handler, api=api, id=0x0002, version=3, end_version=4):
    async def handle(self):
        return Action({'version': 2})


class VersionedHandler3(Handler, api=api, id=0x0002, version=6):
    async def handle(self):
        return Action({'version': 3})


class DelayedHandler(Handler, api=api, id=0xFFFF, name='delayed response'):
    async def gen(self):
        yield b'hello'
        await sleep(0.1)
        yield b' world'
        await sleep(0.1)
        yield b'!'

    async def handle(self):
        return StreamAction(self.gen(), data_type=T_BYTE)


class InputHandler(Handler, api=api, id=0xFFA0, name='internal requests'):
    async def handle(self):
        reply = await self.ask(b'Are you ok?')
        if reply.data == b'yes':
            return Action(b'Nice!')
        else:
            return Action(b'Sad!')


class InputJSONHandler(Handler, api=api, id=0xFFA1, name='internal json requests'):
    async def handle(self):
        reply = await self.ask('Are you ok?')
        if reply.data == 'yes':
            return Action('Nice!')
        else:
            return Action('Sad!')


class JsonFormHandler(Handler, api=api, id=0xFFB0):
    class Loader(BaseModel):
        id: int = Field(ge=0, le=10)
        name: str = Field(min_length=3, max_length=16)

    class Dumper(BaseModel):
        token: str = Field(min_length=64, max_length=64)
        code: str = Field(min_length=6, max_length=6)

    async def handle(self):
        user = await self.json_load()
        assert isinstance(user, dict)
        assert isinstance(user['id'], int) and 0 <= user['id'] <= 10
        assert isinstance(user['name'], str) and 3 <= len(user['name']) <= 16

        return await self.json_dump({
            'token': os.urandom(32).hex(),
            'code': os.urandom(3).hex(),
        })
