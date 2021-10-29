from abc import ABC

from cats.v2.identity import Identity


def test_identity_registry():
    class User(Identity, ABC):
        ...

    assert len(Identity.identity_list) == 1
    assert User in Identity.identity_list
    Identity.identity_list.remove(User)
