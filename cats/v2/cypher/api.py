from cats.v2.cypher.base import Cypher
from cats.v2.registry import Registry

__all__ = [
    'CypherAPI',
]


class CypherAPI(Registry):
    item_type = Cypher
