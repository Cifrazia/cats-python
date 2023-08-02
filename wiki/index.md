!!!WARNING
This package is deprecated and should not be used. It will continue to exist until fully migrated and will be archived.

THIS PACKAGE MAY BE DELETED. DO NOT USE IT.
!!!

# Welcome

[![PyPI version](https://badge.fury.io/py/cats-python.svg)](https://badge.fury.io/py/cats-python) [![codecov](https://codecov.io/gh/Cifrazia/cats-python/branch/master/graph/badge.svg?token=MMDPS40REC)](https://codecov.io/gh/Cifrazia/cats-python) [![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FCifrazia%2Fcats-python.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2FCifrazia%2Fcats-python?ref=badge_shield)

## Cifrazia Action Transport System

CATS - is a TCP based byte protocol for persistence package exchanging. This so-called protocol is designed specifically
for internal use in [Cifrazia](https://cifrazia.com).

[Learn more about protocol](./protocol)

## Features

+ One action at a time
+ Up-to 4GB payload in single [plain Action](protocol/2.0.md#0x00-action)
+ Unlimited and delayed payload in [Streaming Actions](protocol/2.0.md#0x01-streamaction)
+ Chained [inputs](protocol/2.0.md#inputs)
+ [Broadcasts](protocol/2.0.md#broadcast)
+ Multiple [data formats](protocol/2.0.md#data-types)
+ Custom [handshakes](protocol/2.0.md#handshake)
+ ~~Local and global encryption~~

[!ref](get-started.md)

## Requirements

+ Python `3.10`
+ Tornado `^6.1`
+ uJSON `^5.1`
+ PyTZ `^2023.3`
