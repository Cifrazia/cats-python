from typing import Type, TypeVar

__all__ = [
    'IdentityObject',
    'Identity',
]

IdentityObject = TypeVar('IdentityObject', bound='Identity')


class Identity:
    __slots__ = ()
    identity_list: list[Type['Identity']] = []

    @property
    def sentry_scope(self) -> dict:
        """
        Must return dict of data that can be used by Sentry
        """
        raise NotImplementedError

    def __init_subclass__(cls):
        cls.identity_list.append(cls)
