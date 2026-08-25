from __future__ import annotations
import base64, hashlib, hmac, json, time
from fastapi import Header, HTTPException, Request, status

class TokenService:
    def __init__(self,secret:str,ttl_seconds:int=900,clock=time.time):
        if len(secret)<16: raise ValueError("token secret must be at least 16 characters")
        self.secret=secret.encode(); self.ttl=ttl_seconds; self.clock=clock
    @staticmethod
    def _b64(b:bytes)->str:return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    @staticmethod
    def _unb64(s:str)->bytes:return base64.urlsafe_b64decode(s+"="*((4-len(s)%4)%4))
    def issue(self,principal:str)->str:
        payload={"sub":principal,"exp":int(self.clock())+self.ttl,"iat":int(self.clock())}
        body=self._b64(json.dumps(payload,separators=(",",":")).encode()); sig=self._b64(hmac.new(self.secret,body.encode(),hashlib.sha256).digest())
        return f"{body}.{sig}"
    def verify(self,token:str)->str:
        try:body,sig=token.split(".",1); expected=self._b64(hmac.new(self.secret,body.encode(),hashlib.sha256).digest())
        except Exception as e:raise ValueError("invalid token") from e
        if not hmac.compare_digest(sig,expected):raise ValueError("invalid token signature")
        try:p=json.loads(self._unb64(body)); exp=int(p["exp"]); sub=str(p["sub"])
        except Exception as e:raise ValueError("invalid token payload") from e
        if self.clock()>exp:raise ValueError("token expired")
        return sub

def require_principal(request:Request,authorization:str|None=Header(default=None))->str:
    if not getattr(request.app.state,"auth_required",False):
        if authorization and authorization.startswith("Bearer "):
            try:return request.app.state.token_service.verify(authorization[7:])
            except ValueError:pass
        return "anonymous"
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Bearer token required")
    try:return request.app.state.token_service.verify(authorization[7:])
    except ValueError as e:raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail=str(e)) from e
