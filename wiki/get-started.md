# Getting Started

## Install

Using **poetry**

```shell
poetry add cats-python -E pydantic
```

Using **pip**

```shell
pip install cats-python[pydantic]
```

### Extras

+ `django` - Installs `Django` and `djangorestframework`, enables DRF schemes support
+ `pydantic` - Installs `pydantic`, enables Pydantic models support
+ `djantic` - Installs `djantic`, enables Djantic models support

## First steps

### CATS Server

Write your first server

```shell test server
python -m cats.v2.server -h
```

```python server.py
from tornado.ioloop import IOLoop

from cats.v2 import Config, SHA256TimeHandshake
from cats.v2.server import Api, Application, Handler, Server

api = Api()


class EchoHandler(Handler, api=api, id=0xFFFF):
    async def handle(self):
        return self.action


def main():
    handshake = SHA256TimeHandshake(secret_key=b't0ps3cr3t', valid_window=1, timeout=5.0)
    config = Config(
        idle_timeout=120.0,
        input_timeout=120.0,
        input_limit=5,
        debug=True,
        handshake=handshake
    )
    app = Application([api], config=config)
    server = Server(app)
    server.bind(9095, '0.0.0.0')
    server.start(1)
    IOLoop.current().start()


if __name__ == '__main__':
    main()

```

### CATS client

Write your first client

```shell test client
python -m cats.v2.client -h
```

```python client.py
import asyncio

from cats.v2 import Config, SHA256TimeHandshake
from cats.v2.client import Connection


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
    await conn.connect('localhost', 9095)
    while data := input('Message: '):
        print()
        result = await conn.send(0xFFFF, data)
        print(f'{result = }')


if __name__ == '__main__':
    asyncio.run(main())

```