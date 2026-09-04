"""
Phase 6: one-time logging setup.

`loguru` ships with a default handler already writing to stderr (handler
id `0`) - `logger.remove()` drops that before adding this project's own
single stdout sink, so output isn't duplicated.

`enqueue=False` (the default) is a deliberate choice, not an oversight:
`enqueue=True` was tried first for the non-blocking benefit reasoned
through in the Phase 6 learning journal's "waiter"/"enqueue" entries, but
loguru's own source shows it backs that with real `multiprocessing`
primitives (`SimpleQueue`, `Event`, `Lock`) - OS-level semaphores that
this app never explicitly tears down before exit. Confirmed directly:
running with `uvicorn --reload` and stopping it reliably produced
"leaked semaphore objects" warnings with `enqueue=True`, and reliably
didn't with it off. This project has no real concurrent-traffic scenario
yet to justify paying that cost - see BACKLOG.md for the concrete trigger
to revisit it (Phase 7's async routes, or Phase 8D's multi-worker setup).

`logger` itself (imported as `from loguru import logger` everywhere else
in this app) is a global singleton - there's nothing to import from this
module except `configure_logging`, called once at startup in main.py.
"""

import sys

from loguru import logger

from app.config import settings


def configure_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level=settings.log_level)
