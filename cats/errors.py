class CatsError(Exception):
    """Base class for CATS errors"""
    __slots__ = ()


class InputCancelled(CatsError):
    """Raise if received CANCEL action"""
    __slots__ = ()


class ProtocolError(CatsError, ValueError, OSError):
    """Raise if protocol was violated"""
    __slots__ = ('conn',)

    def __init__(self, *args: object, conn) -> None:
        self.conn = conn
        super().__init__(*args)


class ClientSupportError(CatsError, RuntimeError):
    """Raised if server issued action, that client does not support"""
    __slots__ = ()


class ActionError(CatsError, RuntimeError):
    """Raised if client`s request violated handler rules"""
    __slots__ = ('action',)

    def __init__(self, *args: object, action) -> None:
        self.action = action
        super().__init__(*args)


class CatsUsageError(CatsError, RuntimeError):
    """Raise if cats API was violated"""
    __slots__ = ()


class UnsupportedSchemeError(CatsError, TypeError):
    """Raise if scheme is unsupported"""
    __slots__ = ('scheme',)

    def __init__(self, *args: object, scheme) -> None:
        self.scheme = scheme
        super().__init__(*args)


class ValidationError(CatsError, ValueError):
    """Raise if data does not fulfil requirements"""
    __slots__ = ('data',)

    def __init__(self, *args: object, data) -> None:
        self.data = data
        super().__init__(*args)


class CodecError(CatsError, ValueError):
    """Raise if codec failed to handle data"""
    __slots__ = ('data', 'headers')

    def __init__(self, *args: object, data, headers: dict) -> None:
        self.data = data
        self.headers = headers
        super().__init__(*args)


class InvalidCodecError(CatsError, TypeError):
    """Raise if codec failed to handle data"""
    __slots__ = ('data', 'headers')

    def __init__(self, *args: object, data, headers: dict) -> None:
        self.data = data
        self.headers = headers
        super().__init__(*args)


class CompressorError(CatsError, ValueError):
    """Raise if compressor failed to handle data"""
    __slots__ = ('data', 'headers')

    def __init__(self, *args: object, data, headers: dict) -> None:
        self.data = data
        self.headers = headers
        super().__init__(*args)


class InvalidCompressorError(CatsError, TypeError):
    """Raise if compressor failed to handle data"""
    __slots__ = ('data', 'headers')

    def __init__(self, *args: object, data, headers: dict) -> None:
        self.data = data
        self.headers = headers
        super().__init__(*args)


class MalformedDataError(CatsError, ValueError):
    """Raise if data is corrupted, but it is not Codec error"""
    __slots__ = ('data', 'headers')

    def __init__(self, *args: object, data, headers: dict) -> None:
        self.data = data
        self.headers = headers
        super().__init__(*args)


class MalformedHeadersError(CatsError, ValueError):
    """Raise if headers are corrupted"""
    __slots__ = ('headers',)

    def __init__(self, *args: object, headers: dict) -> None:
        self.headers = headers
        super().__init__(*args)


class HandshakeError(CatsError, ValueError):
    """Raise if handshake failed"""
    __slots__ = ('conn', 'handshake')

    def __init__(self, *args: object, conn, handshake) -> None:
        self.conn = conn
        self.handshake = handshake
        super().__init__(*args)
