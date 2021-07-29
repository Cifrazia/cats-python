# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project poorly adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.12] 2021-07-29

### Changed

+ We are now following `Keep a Changelog` `(╯°□°）╯︵ ┻━┻`

### Fixed

+ Added missing methods to connection.pyi

## [0.3.11] 2021-07-20

### Changed

+ Added `__slots__` for remaining classes

### Fixed

+ Fixed invalid missing handler

## [0.3.7] 2021-07-19

### Fixed

+ Fixed crash when `idle_timeout` is set to `None`
+ Fixed `idle_timeout` not working properly when set to `0`

## [0.3.6] 2021-07-07

### Fixed

+ Fix connection crash when `encoded` argument provided to `Action`

## [0.3.5] 2021-07-07

### Added

+ Added `encoded: int = None` argument to `Action`, `InputAction` classes

### Removed

+ Removed redundant prints

### Fixed

+ Fixed invalid typing
+ Fixed `Handler.json_dump` invalid encoding

## [0.3.4] 2021-07-07

### Added

+ Added `MISSING = Missing()` placeholder for missing values

### Changed

+ Function `scheme_load` now removes keys where values are `MISSING`
+ Type `Form` now uses `TypeVar` so every subclass objects will still be matched

## [0.3.3] 2021-07-07

### Added

+ Added scheme support in `JsonCodec.encode`

### Changed

+ Replaced `ujson` package with `orjson`
+ Method `Handler.json_dump` now uses scheme object instead of dict if `Dumper` provided

## [0.3.2] 2021-07-07

### Added

+ Added `BaseSerializer` _(DRF)_ and `BaseModel` _(pydantic)_ support for `JsonCodec.encode`
+ Added `djantic` _(Django models for `pydatic`)_ models support

## [0.3.1] 2021-07-07

### Fixed

+ skipped due to bug with pypi

## [0.3.0] 2021-07-07

### Changed

+ Added `pydantic` models support
+ Method `json_load` and `json_dump` now supports `plain=True` argument, which will return object of scheme, instead of
  dict
