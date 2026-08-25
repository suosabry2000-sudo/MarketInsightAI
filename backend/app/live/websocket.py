from __future__ import annotations
import asyncio
from fastapi import APIRouter,WebSocket,WebSocketDisconnect
from app.domain.models import Quote
class QuoteHub:
    def __init__(self):self.subs={}
    def register(self):q=asyncio.Queue(maxsize=100);self.subs[q]=set();return q
    def unregister(self,q):self.subs.pop(q,None)
    def subscribe(self,q,tickers):self.subs[q]={str(x).upper() for x in tickers[:100]}
    def active_tickers(self):return set().union(*self.subs.values()) if self.subs else set()
    async def publish(self,quote:Quote):
        for q,tickers in list(self.subs.items()):
            if quote.ticker not in tickers:continue
            if q.full():
                try:q.get_nowait()
                except asyncio.QueueEmpty:pass
            await q.put(quote)
router=APIRouter()
@router.websocket('/ws/quotes')
async def ws_quotes(ws:WebSocket):
    await ws.accept();hub=ws.app.state.quote_hub;q=hub.register()
    try:
        while True:
            # Receive control message with short timeout, otherwise push latest quote.
            try:
                msg=await asyncio.wait_for(ws.receive_json(),timeout=.05)
                if msg.get('type')=='subscribe':hub.subscribe(q,list(msg.get('tickers',[])))
            except asyncio.TimeoutError:pass
            try:quote=q.get_nowait();await ws.send_json(quote.model_dump(mode='json'))
            except asyncio.QueueEmpty:await asyncio.sleep(.02)
    except WebSocketDisconnect:pass
    finally:hub.unregister(q)
