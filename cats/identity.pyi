from typing import Type, TypeVar


class IdentityMeta(type):
    __identity_registry__: list[Type['Identity']] = []

    def __new__(mcs, name, bases, attrs): ...

    @property
    def identity_list(cls) -> list[Type['Identity']]: ...


class Identity(metaclass=IdentityMeta):
    __slots__ = ()

    @property
    def id(self) -> int:
        raise NotImplementedError

    @property
    def model_name(self) -> str:
        raise NotImplementedError

    @property
    def sentry_scope(self) -> dict:
        """
        Must return dict of data that can be used by Sentry
        """
        raise NotImplementedError


IdentityChild = TypeVar('IdentityChild', bound=Identity)
