"""
Phase 6: one-time logging setup.

`loguru` ships with a default handler already writing to stderr (handler
id `0`) - `logger.remove()` drops that before adding this project's own
single stdout sink, so output isn't duplicated. `enqueue=True` is the
actual point: the request-handling code only pays for dropping a log
record on a queue, not for the write itself, which happens on a separate
thread - see the Phase 6 learning journal's "waiter" and "enqueue" entries
for why that matters once requests are actually concurrent.

`logger` itself (imported as `from loguru import logger` everywhere else
in this app) is a global singleton - there's nothing to import from this
module except `configure_logging`, called once at startup in main.py.
"""

import sys

from loguru import logger

from app.config import settings


def configure_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level=settings.log_level, enqueue=True)
