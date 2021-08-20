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

```python main.py
from cats.server import Api, Application, Handler, Server
from tornado.ioloop import IOLoop

api = Api()

class EchoHandler(Handler, api=api, id=0xFFFF):
    async def handle(self):
        return self.action

def main():
    app = Application([api])
    server = Server(app)
    server.bind(9095, '0.0.0.0')
    server.start(1)
    IOLoop.current().start()

if __name__ == '__main__':
    main()
```