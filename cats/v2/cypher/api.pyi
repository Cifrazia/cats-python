from cats.v2 import Registry, Selector
from cats.v2.cypher.base import Cypher


class CypherAPI(Registry):
    item_type = Cypher
    registry: dict[int, Cypher]
    named_registry: dict[str, Cypher]

    def find(self, selector: Selector = None) -> Cypher | None: ...

    def find_strict(self, selector: Selector = None) -> Cypher: ...
