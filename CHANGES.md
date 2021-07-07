# Changelog

## 0.3.1 (2021-07-07)

+ Added `BaseSerializer` _(DRF)_ and `BaseModel` _(pydantic)_ support for `JsonCodec.encode`
+ Added `djantic` _(Django models for `pydatic`)_ models support

## 0.3.0 (2021-07-07)

+ Added `pydantic` models support
+ Method `json_load` and `json_dump` now supports `plain=True` argument, which will return object of scheme, instead of
  dict
