from __future__ import annotations
import asyncio
import contextlib
import logging

log = logging.getLogger("marketinsight.live")


class StreamManager:
    def __init__(self, provider, cache, hub, *, poll_interval: float = 1.0):
        self.provider = provider
        self.cache = cache
        self.hub = hub
        self.poll_interval = max(0.01, poll_interval)
        self._stopped = asyncio.Event()

    async def run_once(self, tickers: list[str]):
        streamer = getattr(self.provider, "stream_quotes", None)
        if not callable(streamer):
            raise RuntimeError("market provider does not support quote streaming")
        async for quote in streamer(tickers):
            await self.cache.publish_quote(quote)
            await self.hub.publish(quote)
            if self._stopped.is_set():
                return

    async def run_forever(self):
        active: tuple[str, ...] = ()
        stream_task: asyncio.Task | None = None
        try:
            while not self._stopped.is_set():
                wanted = tuple(sorted(self.hub.active_tickers()))
                if wanted != active:
                    if stream_task is not None:
                        stream_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await stream_task
                    active = wanted
                    stream_task = asyncio.create_task(self.run_once(list(active))) if active else None
                if stream_task is not None and stream_task.done():
                    exc = stream_task.exception()
                    if exc is not None:
                        log.warning("quote stream ended: %s", exc)
                    stream_task = asyncio.create_task(self.run_once(list(active))) if active else None
                await asyncio.sleep(self.poll_interval)
        finally:
            if stream_task is not None:
                stream_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await stream_task

    def stop(self):
        self._stopped.set()
