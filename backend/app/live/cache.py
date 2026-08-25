from datetime import datetime,timezone
from app.domain.models import Quote,WeeklyScannerResponse
class LiveStateCache:
    def __init__(self,redis,*,quote_ttl_seconds=30,scanner_ttl_seconds=600,clock=lambda:datetime.now(timezone.utc)):
        self.redis=redis;self.quote_ttl_seconds=quote_ttl_seconds;self.scanner_ttl_seconds=scanner_ttl_seconds;self.clock=clock
    @staticmethod
    def quote_key(t):return f"market:v1:quote:{t.upper()}"
    @staticmethod
    def scanner_key(u):return f"market:v1:scanner:{u.lower().replace(' ','-')}"
    @staticmethod
    def _decode(v):return v.decode() if isinstance(v,bytes) else v
    async def set_quote(self,q):await self.redis.set(self.quote_key(q.ticker),q.model_dump_json(),ex=self.quote_ttl_seconds)
    async def get_quote(self,ticker):
        raw=await self.redis.get(self.quote_key(ticker))
        if raw is None:return None
        q=Quote.model_validate_json(self._decode(raw));age=(self.clock()-q.normalized_timestamp).total_seconds()
        return None if age<0 or age>self.quote_ttl_seconds else q
    async def publish_quote(self,q):await self.set_quote(q);await self.redis.publish('market:v1:quotes',q.model_dump_json())
    async def set_scanner_snapshot(self,u,s):await self.redis.set(self.scanner_key(u),s.model_dump_json(),ex=self.scanner_ttl_seconds)
    async def get_scanner_snapshot(self,u):
        raw=await self.redis.get(self.scanner_key(u));return None if raw is None else WeeklyScannerResponse.model_validate_json(self._decode(raw))
