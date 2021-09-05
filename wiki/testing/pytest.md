# Pytest plugin

`cats-python` contains
[`pytest11` entrypoint](https://docs.pytest.org/en/6.2.x/writing_plugins.html#making-your-plugin-installable-by-others)
, therefore you don't need to import anything manually.

## Hooks

> No hooks registered

## Markers

> No markers registered

## Not Implemented Fixtures

These fixtures must be implemented by your side in order for other fixtures to work. You may override other fixtures as
well, but only these are required.

### `cats_handshake` - `Handshake` object

Must return configured object of `Handshake` subclass

```python conftest.py
from pytest import fixture
from cats.v2 import Handshake, SHA256TimeHandshake


@fixture(scope='session')
def cats_handshake() -> Handshake:
   return SHA256TimeHandshake(b'secret_key', valid_window=1)
```

### `cats_apis` - List of `Api` objects

Must return list of `Api` objects with defined `Handler`s

```python handlers.py
from cats.v2.server import Api, Handler

api = Api()

class EchoHandler(Handler, api=api, id=0x0000):
    async def handle(self):
        return self.action
```

```python conftest.py
from pytest import fixture

@fixture(scope='session')
def cats_apis() -> list[Api]:
    from .handlers import api
    return [api]
```

## Fixtures

### `cats_conn` - `client.Connection` object

```python plugin.py
@fixture
@mark.asyncio
async def cats_conn(cats_config, cats_api_version, cats_server) -> Connection:
    """
    Return TCP connection to test TCP server
    """
    conn = Connection(cats_config, cats_api_version)
    await conn.connect('127.0.0.1', cats_server.port, timeout=5)
    async with conn:
        yield conn
```

### `cats_middlware` - List of `Middleware` functions

!!!
You may want to overwrite `cats_middleware` fixture
!!!

```python plugin.py
@fixture(scope='session')
def cats_middleware() -> list[Middleware]:
    return [
        default_error_handler,
    ]
```

### `cats_api_version` - int - version of Api

!!!
You may want to overwrite `cats_api_version` fixture
!!!

```python plugin.py
@fixture(scope='function')
def cats_api_version() -> int:
    return 1
```

### `cats_config` - `Config` object

```python plugin.py
@fixture(scope='session')
def cats_config(cats_handshake) -> Config:
    return Config(
        idle_timeout=10.0,
        input_timeout=10.0,
        debug=True,
        handshake=cats_handshake,
    )
```

### `cats_server_connection` - subclass of `server.Connection` to use by `server.Server`

```python plugin.py
@fixture(scope='session')
def cats_server_connection() -> Type[ServerConnection] | None:
    return None
```

### `cats_app` - `server.Application` object

```python plugin.py
@fixture(scope='session')
def cats_app(cats_apis, cats_middleware, cats_config, cats_server_connection):
    return Application(
        apis=cats_apis,
        middleware=cats_middleware,
        config=cats_config,
        connection=cats_server_connection,
    )
```

### `cats_server` - `server.Server` object

```python plugin.py
@fixture(scope='session')
@mark.asyncio
async def cats_server(cats_app) -> Server:
    """
    Runs an TCP server for each module and return port
    :return:
    """

    server = Server(cats_app)
    server.bind_unused_port()
    server.start(1)
    yield server
    await server.shutdown()
```
