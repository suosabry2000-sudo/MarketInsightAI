import time, pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from app.security.auth import TokenService, require_principal
from app.security.rate_limit import InMemoryRateLimiter


def test_token_round_trip_and_expiry():
    now=[1000]
    service=TokenService("x"*32,ttl_seconds=60,clock=lambda:now[0])
    token=service.issue("device:abc")
    assert service.verify(token)=="device:abc"
    now[0]=1061
    with pytest.raises(ValueError): service.verify(token)


def test_tampered_token_rejected():
    s=TokenService("x"*32)
    token=s.issue("device:abc")
    with pytest.raises(ValueError):s.verify(token[:-1]+("A" if token[-1]!="A" else "B"))


def test_rate_limiter_returns_retry_after():
    now=[0.0]; limiter=InMemoryRateLimiter(2,10,clock=lambda:now[0])
    assert limiter.consume("x")==0
    assert limiter.consume("x")==0
    retry=limiter.consume("x")
    assert 9 <= retry <= 10
