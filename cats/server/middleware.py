import asyncio
import traceback
from logging import getLogger
from typing import Any, Callable, Optional

from tornado.iostream import StreamClosedError

from cats.server.action import Action
from cats.server.handlers import Handler

__all__ = [
    'Middleware',
    'default_error_handler',
]

logging = getLogger('CATS')

Middleware = Callable[[Handler], Optional[Any]]


async def default_error_handler(handler: Handler):
    try:
        return await handler()
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
