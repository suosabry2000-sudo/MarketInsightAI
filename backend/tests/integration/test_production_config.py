from pathlib import Path
import pytest

from app.settings import Settings

ROOT = Path(__file__).resolve().parents[3]


def test_production_settings_require_private_services_and_market_credentials():
    with pytest.raises(ValueError) as exc:
        Settings(APP_ENV="production", MARKET_PROVIDER="alpaca").validate_production()
    message = str(exc.value)
    for name in ("DATABASE_URL", "REDIS_URL", "TOKEN_SECRET", "APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
        assert name in message


def test_production_example_names_required_secrets_without_values():
    text = (ROOT / "infra" / ".env.production.example").read_text()
    for name in ("DATABASE_URL", "REDIS_URL", "TOKEN_SECRET", "APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
        assert f"{name}=" in text
    assert "changeme" not in text.lower()
    assert "supersecret" not in text.lower()


def test_proxy_only_exposes_public_ports_and_supports_websockets():
    compose = (ROOT / "infra" / "docker-compose.prod.yml").read_text()
    nginx = (ROOT / "infra" / "nginx.conf").read_text()
    assert "ports:" in compose
    assert "backend:" in compose and "postgres:" in compose and "redis:" in compose and "worker:" in compose
    assert "proxy:" in compose
    # Backend/private services must not publish host ports.
    for marker in ("backend:", "postgres:", "redis:", "worker:"):
        block = compose.split(marker, 1)[1].split("\n  ", 1)[0]
        assert "ports:" not in block
    assert "proxy_set_header Upgrade $http_upgrade" in nginx
    assert "return 301 https://$host$request_uri" in nginx

def test_production_app_wires_redis_cache_and_stream_manager(monkeypatch):
    import sys, types
    fake_redis = object()
    redis_async = types.ModuleType("redis.asyncio")
    redis_async.from_url = lambda *a, **k: fake_redis
    redis_pkg = types.ModuleType("redis")
    redis_pkg.asyncio = redis_async
    monkeypatch.setitem(sys.modules, "redis", redis_pkg)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_async)
    from app.main import create_app_from_settings
    settings = Settings(
        APP_ENV="production", MARKET_PROVIDER="alpaca", DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://redis:6379/0", TOKEN_SECRET="x"*32,
        APCA_API_KEY_ID="key", APCA_API_SECRET_KEY="secret", ALPACA_DATA_FEED="iex"
    )
    app = create_app_from_settings(settings)
    assert app.state.scanner_cache.redis is fake_redis
    assert app.state.stream_manager.cache is app.state.scanner_cache

def test_backend_dockerfile_copies_package_before_installing_it():
    text = (ROOT / "backend" / "Dockerfile").read_text()
    copy_app = text.index("COPY app ./app")
    install = text.index("RUN pip install --no-cache-dir .")
    assert copy_app < install

def test_production_app_lifecycle_registration_survives_fastapi_without_app_event_helper(monkeypatch):
    import sys, types
    import fastapi

    fake_redis = object()
    redis_async = types.ModuleType("redis.asyncio")
    redis_async.from_url = lambda *a, **k: fake_redis
    redis_pkg = types.ModuleType("redis")
    redis_pkg.asyncio = redis_async
    monkeypatch.setitem(sys.modules, "redis", redis_pkg)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_async)
    monkeypatch.setattr(fastapi.FastAPI, "add_event_handler", None, raising=False)

    from app.main import create_app_from_settings
    settings = Settings(
        APP_ENV="production", MARKET_PROVIDER="alpaca", DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://redis:6379/0", TOKEN_SECRET="x"*32,
        APCA_API_KEY_ID="key", APCA_API_SECRET_KEY="secret", ALPACA_DATA_FEED="iex"
    )
    app = create_app_from_settings(settings)
    assert app.state.stream_manager.cache is app.state.scanner_cache
