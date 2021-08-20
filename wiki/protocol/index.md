---
icon: codespaces
---

# Protocol

## Common rules

+ All strings, texts, etc. is encoded in `UTF-8`
+ All numbers are `unsigned`, if not stated otherwise

## Initialisation

1. After connecting via `TCP` to the server, client must send `Protocol Version` as `uInt4`.
    1. If client [is outdated](2.0.md#client), server will send `00` byte and close the connection
    2. If client [is still valid](2.0.md#client), server will send `01` byte
2. Now client must send the **Statement**, declaring client-side info, so that server will understand how exactly to
   speak with it
3. Server will respond with its own **Statement**
4. If server has configured handshake, client must send bytes, according to specific handshake algo.
    1. If handshake failed, server will send `00` bytes and close the connection
    2. If handshake passed, server will result it `01` byte
5. Initialisation complete

### Statement

Depending on protocol version, the **Statements** may differ, but within the same version, they are the same thing.

**Statement** consists of `uInt4` prefix - length of the statement and byte payload of the statement.

[!ref Protocol v2: Statements](2.0.md#statement)

!!!
Statement is the only place, where scheme format (JSON | YAML | TOML) is being `auto` detected, and not defined.
!!!

!!!
Server statement will be encoded with requested format. If client send YAML statement, but
specifies `schemeFormat: JSON`, then server will return statement in JSON.
!!!

### Byte example

#### Protocol version validation

+ C: `00 00 00 02` - Protocol version `2.0`
+ S: `01` - client valid

#### Statement exchange

+
C: `00 00 00 51` `7B 22 61 70 69 22 3A 31 2C 22 63 6C 69 65 6E 74 54 69 6D 65 22 3A 31 36 32 39 34 33 39 35 35 30 39 34 32 2C 22 73 63 68 65 6D 65 46 6F 72 6D 61 74 22 3A 22 4A 53 4F 4E 22 2C 22 63 6F 6D 70 72 65 73 73 6F 72 73 22 3A 5B 22 7A 6C 69 62 22 5D 7D`
    + Payload length: `81`
    + Payload: `{"api":1,"clientTime":1629439550942,"schemeFormat":"JSON","compressors":["zlib"]}`
+ S: `00 00 00 1C` `7B 22 73 65 72 76 65 72 54 69 6D 65 22 3A 31 36 32 39 34 33 39 35 35 30 39 34 32 7D`
    + Payload length: `28`
    + Payload: `{"serverTime":1629439550942}`

#### Handshake (SHA256)

+
C: `4a 4f 47 45 56 61 5f 70 6e 64 4a 34 47 69 5a 41 47 53 63 72 64 37 6e 33 37 41 42 6a 35 4d 47 30 36 74 6f 73 49 38 33 36 58 34 59`
- signature
+ S: `01` - handshake valid

#### Done

Now connection is fully established, you may start exchanging actions

## Actions

Actions - are like messages. Each action type has its own structure and purpose, but they all consist of **TWO** main
parts:

[!button icon="number" variant="contrast" corners="square" text="Action ID: uInt1" margin="0 4 4 0"]
[!button icon="package" variant="contrast" corners="square" text="Action Body: bytes" margin="0 4 4 0"]

**Action Body** always contains **byte schema**, but can also contain **HEADERS** and/or **PAYLOAD**

[!ref Protocol v2: Actions](2.0.md#actions)

+ First, you send `uInt1` **Action ID**
+ Then, you send bytes, according to chosen action type scheme

If you listen for actions, read `1 byte`, match this byte with action type, then read stream with according function.