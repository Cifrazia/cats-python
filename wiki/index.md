# Welcome

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

+ Python `^3.9`
+ Tornado `^6.1`
+ Sentry SDK `^1.1.0`
+ uJSON `^4.0.2`
+ PyTZ `^2021.1`