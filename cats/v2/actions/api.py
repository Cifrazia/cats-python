from cats.v2.actions.base import BaseAction
from cats.v2.registry import Registry, Selector

__all__ = [
    'ActionAPI',
]


class ActionAPI(Registry):
    item_type = type[BaseAction]

    def get_action_name(self, action_id: Selector, default: str = 'unknown') -> str:
        """
        Returns Type Name by it's id (w/ fallback to default)
        :param action_id:
        :param default:
        :return:
        """
        if action := self.find(action_id):
            return action.type_name
        return default
