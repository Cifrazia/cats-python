from cats.v2.scheme import JSON, MsgPack
from cats.v2.statement import *

CLIENT_LEN = b'\x00\x00\x00U'
CLIENT_STMT = b'\x85\xa3api\x01\xabclient_time\xce\x00\x0fB@\xad' \
              b'scheme_format\xa4json\xabcompressors\x91\xa4zlib\xb3default_compression\xa4zlib'

SERVER_LEN = b'\x00\x00\x00\x17'
SERVER_STMT = b'{"server_time":1000000}'


def test_client_statement():
    assert ClientStatement(1, 1000_000).pack(MsgPack) == CLIENT_LEN + CLIENT_STMT
    assert ClientStatement.unpack(CLIENT_STMT) == ClientStatement(api=1, client_time=1000000, scheme_format='json',
                                                                  compressors=['zlib'], default_compression='zlib')


def test_server_statement():
    assert ServerStatement(1000_000).pack() == SERVER_LEN + SERVER_STMT
    assert ServerStatement.unpack(SERVER_STMT, JSON) == ServerStatement(server_time=1000000)
