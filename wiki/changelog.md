# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project poorly adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## `2.1.0` [!badge variant="info" text="NEXT"]

Released: 2021-09-20

### Added

- [ ] Added different scheme language support: YAML, TOML

## `2.0.0` [!badge variant="info" text="LATEST"]

Released: 2021-08-31

### Added

- [x] Added [`retype`](https://retype.com) documentation
- [x] Added [`struct-model-python`](https://github.com/AdamBrianBright/struct-model-python) support
- [x] Added `CATS` client
- [x] Added `INIT Statement` support
- [x] Added separate `Config` class
- [x] Server now chooses compressors from which client support

### Changed

- [x] Updated Python version to `3.10`
- [x] Moved protocol-related things to `v2` folder
- [x] Replaced [`orjson`](https://github.com/ijl/orjson) back with [`ujson`](https://github.com/ultrajson/ultrajson)
- [x] Middlewares now apply at startup
- [x] Replaced `Server.instance -> Server` with `Server.running_server() -> list[Server]`
- [x] Moved `Action*.handle()` logic to `Connection.handle()` unified handler
- [x] Replaced `int.to_bytes`, `int.from_bytes`  with `to_uint` and `as_uint`

### Removed

- [x] Removed `cats.struct` module

### Fixed

- [x] Fixed slow sending, caused by `sleep(0.05)`, replaced with `Queue`

## `0.3.17`

Released: 2021-08-12

### Changed

- [x] Changed `sign in` / `sign out` debug messages

## `0.3.16`

Released: 2021-08-08

### Added

- [x] `Action` classes now have `__repr__`

## `0.3.15`

Released: 2021-08-08

### Fixed

- [x] Fixed `Action.handle` causing problems:
  - [x] Fixed `Message ID` duplication in `Connection.message_pool`
  - [x] Fixed `Exception` suppression

## `0.3.14`

Released: 2021-08-02

### Fixed

- [x] Fixed `'NoneType' object has no attribute 'send_time'`

## `0.3.13`

Released: 2021-07-30

### Added

- [x] Added `Server.instance` class attribute, that stores created instance of server

## `0.3.12`

Released: 2021-07-29

### Changed

- [x] We are now following `Keep a Changelog` `(╯°□°）╯︵ ┻━┻`

### Fixed

- [x] Added missing methods to connection.pyi

## `0.3.11`

Released: 2021-07-20

### Changed

- [x] Added `__slots__` for remaining classes

### Fixed

- [x] Fixed invalid missing handler

## `0.3.7`

Released: 2021-07-19

### Fixed

- [x] Fixed crash when `idle_timeout` is set to `None`
- [x] Fixed `idle_timeout` not working properly when set to `0`

## `0.3.6`

Released: 2021-07-07

### Fixed

- [x] Fix connection crash when `encoded` argument provided to `Action`

## `0.3.5`

Released: 2021-07-07

### Added

- [x] Added `encoded: int = None` argument to `Action`, `InputAction` classes

### Removed

- [x] Removed redundant prints

### Fixed

- [x] Fixed invalid typing
- [x] Fixed `Handler.json_dump` invalid encoding

## `0.3.4`

Released: 2021-07-07

### Added

- [x] Added `MISSING = Missing()` placeholder for missing values

### Changed

- [x] Function `scheme_load` now removes keys where values are `MISSING`
- [x] Type `Form` now uses `TypeVar` so every subclass objects will still be matched

## `0.3.3`

Released: 2021-07-07

### Added

- [x] Added scheme support in `JsonCodec.encode`

### Changed

- [x] Replaced `ujson` package with `orjson`
- [x] Method `Handler.json_dump` now uses scheme object instead of dict if `Dumper` provided

## `0.3.2`

Released: 2021-07-07

### Added

- [x] Added `BaseSerializer` _(DRF)_ and `BaseModel` _(pydantic)_ support for `JsonCodec.encode`
- [x] Added `djantic` _(Django models for `pydatic`)_ models support

## `0.3.1`

Released: 2021-07-07

### Fixed

- [x] skipped due to bug with pypi

## `0.3.0`

Released: 2021-07-07

### Changed

- [x] Added `pydantic` models support
- [x] Method `json_load` and `json_dump` now supports `plain=True` argument, which will return object of scheme, instead
  of dict
