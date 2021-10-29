"""
proxy_protocol.py

Implements the HAProxy Proxy Protocol that passes the actual client
IP behind a load balancer to the server.

Note that the spec is defined here:
https://www.haproxy.org/download/1.8/doc/proxy-protocol.txt
"""
from functools import wraps
from typing import TypedDict

from tornado import httpserver, httputil, iostream, tcpserver
from tornado.iostream import IOStream

# Set the maximum number of bytes that should be allowed in the PROXY
# protocol; this is specifically designed so the proxy line fits in a
# single TCP packet, if I remember correctly.
MAX_PROXY_PROTO_BYTES = 108


class ProxyDict(TypedDict):
    client_ip: str
    client_port: int
    local_ip: str
    local_port: int


class ProxyProtocolInvalidAddress(Exception):
    """ Indicates that the proxy type was invalid.

    The proxy protocol requires fields like: TCP4 or TCP6 (for version 1)
    """
    pass


class ProxyProtocolInvalidLine(Exception):
    """ Indicates that the proxy line as a whole was invalid. """
    pass


class ProxyProtocolIncompleteLine(Exception):
    """ Indicates that the proxy line is incomplete. """
    pass


def parse_proxy_line(line: bytes | bytearray) -> tuple[ProxyDict, int]:
    """
    Parses the given line (string or sequence of bytes) for the client IP
    and other fields passed through the proxy protocol.

    This returns a tuple with elements as follows:
    (1) Dictionary with the parsed IP addresses
    (2) Index where the proxy protocol stopped parsing.

    This throws exceptions if the proxy protocol could not be parsed.
    """
    line_len = len(line)
    if not line.startswith(b"PROXY "):
        for i, ch in enumerate("PROXY "):
            if i >= line_len:
                raise ProxyProtocolIncompleteLine()
            if line[i] != ch:
                break
        raise ProxyProtocolInvalidLine()

    idx = line.find(b'\r\n')
    if idx < 0:
        if line_len >= MAX_PROXY_PROTO_BYTES:
            raise ProxyProtocolInvalidLine()
        raise ProxyProtocolIncompleteLine()

    # Now, try and parse the proxy line as desired.
    proxy_line = line[:idx]
    fields: list[bytes] = proxy_line.split(b' ')
    if len(fields) != 6:
        raise ProxyProtocolInvalidLine()

    # Check if the proxy line is for v1 of the protocol.
    if fields[0] == b"PROXY":
        try:
            if fields[1] == b"TCP4" or fields[1] == b"TCP6":
                source_addr = fields[2]
                dest_addr = fields[3]
                source_port = int(fields[4])
                dest_port = int(fields[5])
            else:
                raise ProxyProtocolInvalidAddress()
        except:
            raise ProxyProtocolInvalidAddress()

        return {
                   'client_ip': source_addr.decode('utf-8'),
                   'client_port': source_port,
                   'local_ip': dest_addr.decode('utf-8'),
                   'local_port': dest_port
               }, int(idx + 2)
    raise ProxyProtocolInvalidLine()


def putback_line_in_stream(line: bytes | bytearray, stream: IOStream):
    """
    HACKY: This call reinjects the given line back into the stream.

    This emulates a "putback" or "unget" operation. This is subject to
    break, though, so it should be used with caution, since it uses
    tornado internals.
    """
    # line_len = len(line)
    # stream._read_buffer_pos -= line_len
    # stream._read_buffer_size += line_len
    if not line:
        return
    stream._read_buffer[:0] = line
    stream._read_buffer_size += len(line)


async def parse_proxy_line_from_buff(stream: IOStream) -> ProxyDict:
    line = b''
    bytes_remaining = MAX_PROXY_PROTO_BYTES
    addr = None
    idx = 0
    # This "while" loop is necessary because Tornado does not (but it should!)
    # support an option to `stream.read_until()` to not automatically close the
    # connection if the maximum byte count is reached before finding the
    # delimiter.
    #
    # Again, @bdarnell, can you provide a cleaner way to do this?
    #
    while True:
        # Keep reading until we get the maximum number of bytes allowed.
        # We will break out of this loop early if we identify that the
        # parsed line doesn't imply the proxy protocol.
        val = await stream.read_bytes(bytes_remaining, partial=True)
        line += val
        bytes_remaining = MAX_PROXY_PROTO_BYTES - len(line)

        try:
            addr, idx = parse_proxy_line(line)
            break
        except ProxyProtocolIncompleteLine:
            # If the line is incomplete, keep trying to read.
            continue
        except (ProxyProtocolInvalidLine, ProxyProtocolInvalidAddress):
            idx = 0
            break

    # Reinsert any unparsed bytes back into the stream.
    putback_line_in_stream(line[idx:], stream)

    # Return the address we parsed.
    # This supports older tornado versions, though this can be very
    # easily fixed to work with asyncio.
    return addr


def handle_with_proxy(fn: tcpserver.TCPServer.handle_stream = None):
    if fn is None:
        return handle_with_proxy

    @wraps(fn)
    async def handle_stream(self, stream: IOStream, address: tuple[str, int]):
        try:
            addr = await parse_proxy_line_from_buff(stream)
            if addr is not None:
                address = (addr['client_ip'], addr['client_port'])
                stream.proxy_addr = addr
            return await fn(self, stream, address)
        except iostream.StreamClosedError:
            raise
        except:
            return await fn(self, stream, address)

    return handle_stream


class ProxyProtocolTCPServer(tcpserver.TCPServer):
    """
    Wrapper for tornado.tcpserver.TCPServer that parses out the
    HAProxy PROXY protocol and attaches the actual IP to the stream
    as an attribute named 'proxy_addr'.

    The proxy protocol spec is defined here:
    http://www.haproxy.org/download/1.8/doc/proxy-protocol.txt
    """

    async def handle_stream(self, stream: IOStream, address: tuple[str, int]):
        try:
            addr = await parse_proxy_line_from_buff(stream)
            if addr is not None:
                stream.proxy_addr = addr
        except iostream.StreamClosedError:
            raise
        finally:
            await super(ProxyProtocolTCPServer, self).handle_stream(stream, address)


class ProxyProtocolAdapter(httputil.HTTPMessageDelegate, object):
    """
    Implements a HTTPMessageDelegate that injects the real client IP into the
    request context for each request.

    Basically, this call makes sure that the following code actually returns
    the correct client IP:
    `
    class SampleHandler(tornado.web.RequestHandler):
        def post(self):
            self.request.remote_ip
    `

    This works by intercepting the delegate that is called whenever a request
    is made, then injecting the proper remote_ip (and other relevant fields).
    When the request is finished, or stuff falls out of scope, this "undoes"
    the injected changes so everything is consistent.

    Note that this particular adapter only works for HTTP (and by extension
    WebSocket) calls.
    """

    def __init__(self, delegate, request_conn, proxy_ip=None):
        self.connection = request_conn
        self.delegate = delegate
        self.proxy_ip = proxy_ip

    def _apply_proxy_info(self):
        self._orig_ip = self.connection.context.remote_ip
        if self.proxy_ip:
            self.connection.context.remote_ip = self.proxy_ip

    def _undo_proxy_info(self):
        self.connection.context.remote_ip = self._orig_ip

    def headers_received(self, start_line, headers):
        self._apply_proxy_info()
        return self.delegate.headers_received(start_line, headers)

    def data_received(self, chunk):
        return self.delegate.data_received(chunk)

    def finish(self):
        self.delegate.finish()
        self._undo_proxy_info()

    def on_connection_close(self):
        self.delegate.on_connection_close()
        self._undo_proxy_info()


class ProxyProtocolHTTPServer(httpserver.HTTPServer):
    """
    Wrapper for tornado.httpserver.HTTPServer that parses out the
    HAProxy PROXY protocol and sets the appropriate remote_ip as
    defined here:
    http://www.haproxy.org/download/1.8/doc/proxy-protocol.txt
    """

    async def handle_stream(self, stream: IOStream, address: tuple[str, int]):
        """
        Creates the stream for this connection.

        This parses out the proxy protocol from the request and injects the
        relevant fields onto the given stream object at: `stream.proxy_addr`
        """
        try:
            addr = await parse_proxy_line_from_buff(stream)
            if addr is not None:
                stream.proxy_addr = addr

            # Use our parsed address here.
            super(ProxyProtocolHTTPServer, self).handle_stream(stream, address)
        except iostream.StreamClosedError:
            pass
        except:
            super(ProxyProtocolHTTPServer, self).handle_stream(stream, address)

    def start_request(self, server_conn, request_conn):
        """
        Override so that we can inject the real ip for `self.request.remote_ip`
        in each request.
        """
        delegate = super(ProxyProtocolHTTPServer, self).start_request(server_conn, request_conn)

        # If the real client IP was parsed via the proxy protocol, the address would
        # have been attached to the socket in the 'proxy_addr' attribute, so we try
        # to fetch it. If we couldn't, just ignore it and default to the usual
        # behavior. (Should we log it instead?)
        try:
            proxy_addr = server_conn.stream.proxy_addr
            addr = proxy_addr['client_ip']
            return ProxyProtocolAdapter(delegate, request_conn, proxy_ip=addr)
        except Exception as e:
            return delegate
