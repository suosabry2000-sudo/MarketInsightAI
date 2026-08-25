from __future__ import annotations

import asyncio
import logging
from app.settings import Settings

log = logging.getLogger("marketinsight.worker")


async def main() -> None:
    settings = Settings().validate_production()
    interval = max(30, settings.SCANNER_REFRESH_SECONDS)
    log.info("worker started")
    # The specialized scanner/outcome/news workers are safe to invoke from one process.
    # Keeping the heartbeat here prevents a production container from exiting while
    # deployments wire provider/cache/database adapters through environment settings.
    while True:
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
