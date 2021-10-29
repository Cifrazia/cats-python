from cats.v2 import Registry, Selector
from cats.v2.actions.base import Action


class ActionAPI(Registry):
    item_type = Action
    registry: dict[int, Action]
    named_registry: dict[str, Action]

    def get_action_name(self, action_id: Selector, default: str = 'unknown') -> str: ...

    def find(self, selector: Selector = None) -> Action | None: ...

    def find_strict(self, selector: Selector = None) -> Action: ...
