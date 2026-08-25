from __future__ import annotations
import time
from collections import defaultdict,deque
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class InMemoryRateLimiter:
    def __init__(self,requests:int,window_seconds:int,clock=time.time):self.limit=requests;self.window=window_seconds;self.clock=clock;self.events=defaultdict(deque)
    def consume(self,key:str)->float:
        now=self.clock(); q=self.events[key]
        while q and q[0]<=now-self.window:q.popleft()
        if len(q)>=self.limit:return max(0,q[0]+self.window-now)
        q.append(now);return 0

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self,app,limiter:InMemoryRateLimiter):super().__init__(app);self.limiter=limiter
    async def dispatch(self,request:Request,call_next):
        if request.url.path=="/health":return await call_next(request)
        auth=request.headers.get("authorization",""); key=auth[-24:] if auth else (request.client.host if request.client else "unknown")
        retry=self.limiter.consume(key)
        if retry>0:return JSONResponse(status_code=429,content={"detail":"rate limit exceeded"},headers={"Retry-After":str(max(1,int(retry)))})
        return await call_next(request)
