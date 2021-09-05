import asyncio
import inspect

from cats.v2 import Config
from cats.v2.action import Action
from cats.v2.client import Connection as BaseConn

__all__ = [
    'Connection',
]


class Connection(BaseConn):
    __slots__ = ('broadcast_inbox', 'store_handled_broadcast', 'broadcast_inbox_size')

    def __init__(self, conf: Config, api_version: int):
        super().__init__(conf, api_version)
        self.broadcast_inbox: list[Action] = []
        self.store_handled_broadcast: bool = False
        self.broadcast_inbox_size: int = 5

    async def handle_broadcast(self, action: Action):
        if action.handler_id in self.subscriptions:
            for fn in self.subscriptions[action.handler_id].values():
                res = fn(action)
                if inspect.isawaitable(res):
                    await res
            if not self.store_handled_broadcast:
                return
        self.broadcast_inbox.append(action)
        self.broadcast_inbox = self.broadcast_inbox[-self.broadcast_inbox_size:]

    def clear_broadcast_inbox(self):
        self.broadcast_inbox.clear()

    def get_received_broadcast(self, handler_id: int) -> (int | None, Action | None):
        for i, action in enumerate(self.broadcast_inbox):
            if action.handler_id == handler_id:
                return i, action
        return None, None

    async def recv_broadcast(self, handler_id: int) -> Action | None:
        i, action = self.get_received_broadcast(handler_id)
        if action is not None:
            if not self.store_handled_broadcast:
                self.broadcast_inbox.pop(i)
            return action
        fut = asyncio.Future()
        sub_id = self.subscribe(handler_id, lambda res: fut.set_result(res))
        response = await asyncio.wait_for(fut, 5.0)
        self.unsubscribe(handler_id, sub_id)
        return response
