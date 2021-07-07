# Changelog

## 0.3.4 (2021-07-07)

+ Added `MISSING = Missing()` placeholder for missing values
+ Function `scheme_load` now removes keys where values are `MISSING`
+ Type `Form` now uses `TypeVar` so every subclass objects will still be matched

## 0.3.3 (2021-07-07)

+ Replaced `ujson` package with `orjson`
+ Added scheme support in `JsonCodec.encode`
+ Method `Handler.json_dump` now uses scheme object instead of dict if `Dumper` provided

## 0.3.2 (2021-07-07)

+ Added `BaseSerializer` _(DRF)_ and `BaseModel` _(pydantic)_ support for `JsonCodec.encode`
+ Added `djantic` _(Django models for `pydatic`)_ models support

## 0.3.1 (2021-07-07)

+ skipped due to bug with pypi

## 0.3.0 (2021-07-07)

+ Added `pydantic` models support
+ Method `json_load` and `json_dump` now supports `plain=True` argument, which will return object of scheme, instead of
  dict
