# Test Docker server

## Install

1. Clone [this](https://github.com/cifrazia/cats-python) repo
2. Build image with `docker build -t cats-test:latest .`
3. Run image with `docker run --rm --name cats-test -p 9095:9095 cats-test`

## Config

### Bindings

#### Port

Server runs on 9095 port. To change external port, use `-p <your-server-port>:9095` instead of `-p 9095:9095`

### Environment variables

#### `SERVER_CORE`

How many forks to run. `0` to max CPU threads. Default: `1`.

#### `HANDSHAKE_SECRET`

What secret to use with timed handshake. Default: `t0ps3cr3t`.

## Use and test your client

### Configuration

- Idle timeout is set to `2 minutes`.
- Handshake is set to `SHA256TimeHandshake`
- Protocol version is set to `2`

### Handlers

#### `VoidHandler`: `0x0000`

Return nothing.

#### `EchoPlainHandler`: `0x0001`

Return received data without compression

#### `EchoZlibHandler`: `0x0002`

Return received data with ZLib compression.

#### `VersionedHandler`: `0x0010`

Return json payload for different API versions, specified on client connection:

- on API version before `1` fails
- on API version `1` to `2` returns `{"version":1}`
- on API version `3` to `4` returns `{"version":2}`
- on API version `5` fails
- on API version `6` and up returns `{"version":3}`

#### `DelayedHandler`: `0x0020`

Returns `StreamAction` with `0.01` sec delay between following `byte` chunks:

- `hello`
- ` world`
- `!`

#### `InputHandler`: `0x0030`

- Returns `InputAction` with byte payload `Are you ok?`
- Awaits for `InputAction` response
  - If response payload is `yes`, will return `Nice!`
  - Otherwise, will return `Sad!`

#### `InputJsonHandler`: `0x0031`

- Returns `InputAction` with JSON payload (string) `"Are you ok?"`
- Awaits for `InputAction` JSON response
  - If response payload is `"yes"`, will return `"Nice!"`
  - Otherwise, will return `"Sad!"`

#### `JsonFormHandler`: `0x0040`

Accepts and validates JSON payload. If valid, will return JSON payload.

**Request**

```json5
{
  // >= 0, <=10
  "id": 0,
  // length >= 3, length <= 16
  "name": "User",
}
```

**Response**

```json5
{
  // 6 characters long random string
  "code": "ABCDEF",
  // 64 characters long random string
  "token": "ABCDEF1234567890",
}
```

### Broadcast

Every `5 seconds` clients will receive broadcast `Action` with payload `ping!` on Handler ID `0x0050`