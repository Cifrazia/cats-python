class ProtocolError(ValueError, OSError):
    pass


class CodecError(ValueError):
    pass


class MalformedDataError(ValueError):
    pass


class HandshakeError(ValueError):
    pass
