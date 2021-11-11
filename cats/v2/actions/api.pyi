from typing import Iterable

from cats.v2 import Registry, Selector
from cats.v2.actions.base import BaseAction


class ActionAPI(Registry):
    item_type = type[BaseAction]
    registry: dict[int, BaseAction]
    named_registry: dict[str, BaseAction]

    def __init__(self, items: Iterable[type[BaseAction]]): ...

    def get_action_name(self, action_id: Selector, default: str = 'unknown') -> str: ...

    def find(self, selector: Selector = None) -> type[BaseAction] | None: ...

    def find_strict(self, selector: Selector = None) -> type[BaseAction]: ...
