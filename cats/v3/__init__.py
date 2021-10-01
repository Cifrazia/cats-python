"""
@dataclass
class Config:
    idle_timeout: float | int = 120.0
    input_timeout: float | int = 120.0
    input_limit: int = 5
    debug: bool = False
    max_plain_payload: int = 16 * 1024 * 1024
    stream_errors: Type[Exception] | tuple[Type[Exception]] = (
        asyncio.TimeoutError,
        asyncio.CancelledError,
        asyncio.InvalidStateError,
        StreamClosedError,
    )
    ignore_errors: Type[Exception] | tuple[Type[Exception]] = (
        *stream_errors,
        CatsError,
        KeyboardInterrupt,
    )
    handshake: Handshake | None = None

class Options:
    api_version: int = 1
    available_compressors = [GZip, zLib]
    default_compressor = none | GZip | zLib
    scheme_type: json | yaml | xml = json
    download_speed: int | None

class User:
    identity: Identity
    credentials: Credentials
    timer: Timer

class Connection:
    config: Config
    options: Options

class Codec[type_id]:
    def dispatch(data, headers, options: Options): most fit codec
    input = [data, headers]
    output = [data, headers]

class Compressor[type_id]:
    def dispatch(data, headers, options: Options): most fit compressor
    input = [data, headers]
    output = [data, headers]
"""
