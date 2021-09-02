import asyncio
import traceback
from logging import getLogger
from typing import Protocol

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
    except asyncio.CancelledError:
        return Action({
            'error': 'CancelledError',
            'message': 'Request was cancelled',
        }, status=500)
    except asyncio.TimeoutError:
        return Action({
            'error': 'TimeoutError',
            'message': 'Request timeout',
        }, status=503)
    except Exception as err:
        logging.debug(traceback.format_exc())
        return Action({
            'error': err.__class__.__name__,
            'message': str(err),
        }, status=500)
