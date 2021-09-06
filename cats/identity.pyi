from typing import Type, TypeVar

IdentityObject = TypeVar('IdentityObject', bound='Identity')


class Identity:
    __slots__ = ()
    identity_list: list[Type['Identity']] = []

    @property
    def id(self) -> int:
        raise NotImplementedError

    @property
    def model_name(self) -> int:
        raise NotImplementedError

    @property
    def sentry_scope(self) -> dict:
        raise NotImplementedError
