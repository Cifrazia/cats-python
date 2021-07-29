import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Iterable, Optional, Type, TypeVar

from sentry_sdk import Scope
from tornado.iostream import IOStream, StreamClosedError

from cats.errors import HandshakeError, ProtocolError
from cats.identity import Identity
from cats.server.action import BaseAction, Input
from cats.server.app import Application
from cats.server.handlers import Handler
from cats.types import BytesAnyGen, T_Headers

ConnType = TypeVar('ConnType', bound='Connection')


class Connection:
    MAX_PLAIN_DATA_SIZE: int
    STREAM_ERRORS = (asyncio.TimeoutError, asyncio.CancelledError, asyncio.InvalidStateError, StreamClosedError)
    IGNORE_ERRORS = (*STREAM_ERRORS, HandshakeError, ProtocolError, KeyboardInterrupt)

    __slots__ = (
        '_closed', 'stream', 'address', 'api_version', '_app', 'scope', 'download_speed',
        '_identity', '_credentials', 'loop', 'input_deq', '_idle_timer', 'message_pool', 'is_sending',
        'debug', 'recv_fut',
    )

    def __init__(self, stream: IOStream, address: tuple[str, int], api_version: int, app: Application,
                 debug: bool = False):
        self._closed: bool = False
        self.stream: IOStream = stream
        self.address: tuple[str, int] = address
        self.api_version: int = api_version
        self._app: Application = app
        self.scope: Scope = Scope()
        self._identity: Optional[Identity] = None
        self._credentials: Any = None
        self.loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self.input_deq: dict[int, Input] = {}
        self._idle_timer: Optional[asyncio.Future] = None
        self.message_pool: list[int] = []
        self.is_sending: bool = False
        self.download_speed: int = 0
        self.debug = debug
        self.recv_fut: Optional[asyncio.Future] = None

    @property
    def host(self) -> str: ...

    @property
    def port(self) -> int: ...

    @property
    def is_open(self) -> bool: ...

    @property
    def app(self) -> Application: ...

    async def init(self) -> None: ...

    async def start(self, ping: bool = True) -> None: ...

    @contextmanager
    def preserve_message_id(self, message_id: int): ...

    async def recv(self) -> BaseAction: ...

    async def tick(self) -> None: ...

    def on_tick_done(self, task: asyncio.Task) -> None: ...

    def dispatch(self, handler_id: int) -> Type[Handler]: ...

    async def ping(self) -> None: ...

    async def set_download_speed(self, speed: int = 0): ...

    async def send(self, handler_id: int, data: Any, message_id: int = None, compression: int = None, *,
                   headers: T_Headers = None, status: int = 200) -> None: ...

    async def send_stream(self, handler_id: int, data: BytesAnyGen, data_type: int,
                          message_id: int = None, compression: int = None, *,
                          headers: T_Headers = None, status: int = 200) -> None: ...

    def attach_to_channel(self, channel: str): ...

    def detach_from_channel(self, channel: str): ...

    @property
    def conns_with_same_identity(self) -> Iterable['Connection']: ...

    @property
    def conns_with_same_model(self) -> Iterable['Connection']: ...

    @property
    def identity(self) -> Optional[Identity]: ...

    @property
    def credentials(self) -> Optional[Any]: ...

    @property
    def identity_scope_user(self): ...

    def signed_in(self) -> bool: ...

    def sign_in(self, identity: Identity, credentials: Any = None): ...

    def sign_out(self): ...

    def _sign_out_and_remove_from_channels(self): ...

    def close(self, exc: BaseException = None) -> None: ...

    def __str__(self) -> str: ...

    class ProtocolError(ValueError, IOError):
        pass

    def reset_idle_timer(self) -> None: ...

    def _get_free_message_id(self) -> int: ...

    @asynccontextmanager
    async def lock_write(self): ...
