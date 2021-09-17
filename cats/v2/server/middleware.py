import traceback
from logging import getLogger
from typing import Protocol

from richerr import RichErr
from tornado.iostream import StreamClosedError

from cats.v2.action import Action, ActionLike
from cats.v2.server.handlers import Handler

__all__ = [
    'Forward',
    'Middleware',
    'default_error_handler',
]

logging = getLogger('CATS')


class Forward(Protocol):
    async def __call__(self, handler: Handler) -> ActionLike | None: ...


class Middleware(Protocol):
    async def __call__(self, handler: Handler, forward: Forward) -> ActionLike | None: ...


async def default_error_handler(handler: Handler, forward: Forward) -> ActionLike | None:
    try:
        return await forward(handler)
    except (KeyboardInterrupt, StreamClosedError):
        raise
    except Exception as err:
        logging.debug(traceback.format_exc())
        err = RichErr.convert(err)
        return Action(err.dict(), status=err.code)
