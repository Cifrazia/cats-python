class CatsError(Exception):
    __slots__ = ()


class InputCancelled(CatsError):
    __slots__ = ()


class ProtocolViolation(CatsError, ValueError, OSError):
    __slots__ = ('conn',)

    def __init__(self, *args: object, conn) -> None:
        self.conn = conn
        super().__init__(*args)


class UnsupportedAction(CatsError, RuntimeError):
    """Raised if was issued action, that is not supported"""
    __slots__ = ()


class HandlerRulesViolation(CatsError, RuntimeError):
    """Raised if client`s request violated handler rules"""
    __slots__ = ('action',)

    def __init__(self, *args: object, action) -> None:
        self.action = action
        super().__init__(*args)


class InterfaceViolation(CatsError, RuntimeError):
    __slots__ = ()


class UnsupportedForm(CatsError, TypeError):
    __slots__ = ('form',)

    def __init__(self, *args: object, form) -> None:
        self.form = form
        super().__init__(*args)


class InvalidData(CatsError, ValueError):
    __slots__ = ('data',)

    def __init__(self, *args: object, data) -> None:
        self.data = data
        super().__init__(*args)


class CodecError(CatsError, ValueError):
    __slots__ = ('data', 'headers', 'options')

    def __init__(self, *args: object, data, headers: dict, options) -> None:
        self.data = data
        self.headers = headers
        self.options = options
        super().__init__(*args)


class InvalidCodec(CatsError, TypeError):
    __slots__ = ('data', 'headers', 'options')

    def __init__(self, *args: object, data, headers: dict, options) -> None:
        self.data = data
        self.headers = headers
        self.options = options
        super().__init__(*args)


class CompressorError(CatsError, ValueError):
    __slots__ = ('data', 'headers')

    def __init__(self, *args: object, data, headers: dict) -> None:
        self.data = data
        self.headers = headers
        super().__init__(*args)


class InvalidCompressor(CatsError, TypeError):
    __slots__ = ('data', 'headers', 'options')

    def __init__(self, *args: object, data, headers: dict, options) -> None:
        self.data = data
        self.headers = headers
        self.options = options
        super().__init__(*args)


class CypherError(CatsError, ValueError):
    __slots__ = ('data', 'headers', 'options')

    def __init__(self, *args: object, data, headers: dict, options) -> None:
        self.data = data
        self.headers = headers
        self.options = options
        super().__init__(*args)


class InvalidCypher(CatsError, TypeError):
    __slots__ = ('data', 'headers', 'options')

    def __init__(self, *args: object, data, headers: dict, options) -> None:
        self.data = data
        self.headers = headers
        self.options = options
        super().__init__(*args)


class MalformedData(CatsError, ValueError):
    __slots__ = ('data',)

    def __init__(self, *args: object, data) -> None:
        self.data = data
        super().__init__(*args)


class MalformedHeaders(CatsError, ValueError):
    __slots__ = ('headers',)

    def __init__(self, *args: object, headers: dict) -> None:
        self.headers = headers
        super().__init__(*args)


class HandshakeFailure(CatsError, ValueError):
    __slots__ = ('conn', 'handshake')

    def __init__(self, *args: object, conn, handshake) -> None:
        self.conn = conn
        self.handshake = handshake
        super().__init__(*args)
