from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Awaitable,Callable
import httpx
@dataclass(frozen=True)
class FcmMessage:
    device_token:str;ticker:str;alert_type:str;generated_at:datetime;navigation_target:str;title:str;body:str
class FcmSender:
    def __init__(self,project_id:str,access_token_provider:Callable[[],Awaitable[str]],*,client=None):
        if not project_id.strip():raise ValueError('FCM project id is required')
        self.project_id=project_id;self.access_token_provider=access_token_provider;self.client=client or httpx.AsyncClient(timeout=10)
    async def send(self,m:FcmMessage):
        token=await self.access_token_provider();payload={'message':{'token':m.device_token,'notification':{'title':m.title,'body':m.body},'data':{'ticker':m.ticker.upper(),'alert_type':m.alert_type,'generated_at':m.generated_at.isoformat(),'navigation_target':m.navigation_target}}}
        r=await self.client.post(f'https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send',headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},json=payload);r.raise_for_status();return r.json()
