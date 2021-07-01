# CATS Python

## Cifrazia Action Transport System

### Requirements

+ Python `^3.9`
+ Tornado `^6.1`
+ Sentry SDK `^1.1.0`
+ uJSON `^4.0.2`
+ PyTZ `^2021.1`

**Extras**

+ `django`
  + Django `^2.2` (optional)
  + Django Rest Framework `^3.12.4` (optional)

### Installation

**Install via Poetry**

```shell
poetry add cats-python
```

With `Django` support:

```shell
poetry add cats-python[django]
```

# [WIP] Protocol declaration

## Compression

### Compression algorithms

`0x00` **No compression**

All payload in not compressed (unless the payload itself is a compressed data)

`0x01` **GZip**

Payload compressed with GZip at level 6

`0x02` **ZLib**

Payload compressed with ZLib DEFLATE method at level 6

Additional header with **Adler32** checksum provided `{"Adler32": 1235323}` 