from typing import Iterable, TypeAlias

__all__ = [
    'Item',
    'Selector',
    'Registry',
]


class Item:
    @property
    def type_id(self) -> int:
        """Replace with class attribute of type: int"""
        raise NotImplementedError

    @property
    def type_name(self) -> str:
        """Replace with class attribute of type: str"""
        raise NotImplementedError

    def __int__(self):
        return self.type_id

    def __eq__(self, other):
        try:
            return int(self) == int(other)
        except (KeyError, ValueError, TypeError) as err:
            raise TypeError(f'Can not compare Item with {type(other)}') from err

    def __ne__(self, other):
        try:
            return int(self) != int(other)
        except (KeyError, ValueError, TypeError) as err:
            raise TypeError(f'Can not compare Item with {type(other)}') from err


Selector: TypeAlias = int | str | Item


class Registry:
    item_type: type = Item

    def __init__(
        self, items: Iterable[Item]
    ):
        self.registry: dict[int, Item] = {}
        self.named_registry: dict[str, Item] = {}
        for item in items:
            self.register(item)

    def register(
        self, item: Item
    ):
        if item.type_id in self.registry:
            raise ValueError(f'{self.item_type.__name__} with id {item.type_id} already registered: '
                             f'{self.__qualname__} -> {self.registry[item.type_id].__qualname__}')
        if item.type_name in self.named_registry:
            raise ValueError(f'{self.item_type.__name__} with name {item.type_name} already registered: '
                             f'{self.__qualname__} -> {self.named_registry[item.type_name].__qualname__}')
        self.registry[item.type_id] = item
        self.named_registry[item.type_name] = item

    def unregister(
        self, selector: Selector = None
    ):
        if item := self.find(selector):
            self.registry.pop(item.type_id, None)
            self.named_registry.pop(item.type_name, None)

    def find(
        self, selector: Selector = None
    ) -> Item | None:
        if isinstance(selector, int):
            return self.registry.get(selector)
        if isinstance(selector, str):
            return self.named_registry.get(selector)
        if isinstance(selector, Item):
            return self.registry.get(int(selector))
        return None

    def find_strict(
        self, selector: Selector = None
    ) -> Item:
        if found := self.find(selector):
            return found
        raise KeyError(f'{self.item_type.__name__} not found with ID {selector}')
