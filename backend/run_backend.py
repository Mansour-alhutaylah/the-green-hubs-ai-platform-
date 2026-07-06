"""Development entrypoint.

Deliberately runs with ``reload=False``. Hemaya's reference project hit a
real bug on Python 3.14 + Windows where ``uvicorn --reload`` spawns a
subprocess and ``asyncio.run()`` hangs inside it -- this project targets the
same Python/OS combination locally, so the same workaround is carried
forward. ``--reload`` is safe inside the Linux-based Docker container; it is
simply not used for local Windows development.
"""

import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
