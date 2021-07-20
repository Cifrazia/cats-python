class ProtocolError(ValueError, OSError):
    __slots__ = ()


class CodecError(ValueError):
    __slots__ = ()


class MalformedDataError(ValueError):
    __slots__ = ()


class HandshakeError(ValueError):
    __slots__ = ()
