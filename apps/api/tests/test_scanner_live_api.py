from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.main import app
from app.market.models import Candle
from app.models import User
from app.scanner import background
from app.scanner.live_scanner import LiveScanner
from app.scanner.models import ScannerStrategy

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
TC = ScannerStrategy.TREND_CONTINUATION

UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]


def setup_candles():
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[11] = (112.3, 113.8, 114.0, 112.0)
    rows[17] = (110.6, 112.4, 112.5, 110.5)
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=o, high=h, low=low, close=c, volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


@pytest.fixture
def api():
    app.dependency_overrides[get_current_user] = lambda: User(
        email="tester@drl2.dev", password_hash="x"
    )
    fresh_scanner = LiveScanner()
    background._scanner = fresh_scanner
    with TestClient(app) as client:
        yield client, fresh_scanner
    app.dependency_overrides.clear()


def live_params(**overrides):
    params = {"symbol": "BTC/USDT", "timeframe": "1h", "strategy": "trend_continuation"}
    params.update(overrides)
    return params


def test_live_state_for_an_unscanned_scope_is_404(api):
    client, _ = api
    response = client.get("/scanner/live", params=live_params())
    assert response.status_code == 404


def test_live_state_reflects_real_processed_candles(api):
    client, scanner = api
    for candle in setup_candles():
        scanner.process_candle("BTC/USDT", "1h", candle, [TC])

    response = client.get("/scanner/live", params=live_params())
    assert response.status_code == 200
    body = response.json()

    assert body["symbol"] == "BTC/USDT"
    assert body["timeframe"] == "1h"
    assert body["strategy"] == "trend_continuation"
    assert body["state"] == "valid_setup"
    assert len(body["history"]) >= 1
    assert body["history"][0]["new_state"] == "break_detected"
    assert body["history"][-1]["new_state"] == "valid_setup"
    assert set(body["history"][0]) == {"previous_state", "reason", "new_state"}


def test_live_state_only_matches_the_exact_scope(api):
    """Processing one strategy must not make a different strategy's
    scope for the same symbol appear as scanned."""
    client, scanner = api
    for candle in setup_candles():
        scanner.process_candle("BTC/USDT", "1h", candle, [TC])

    response = client.get(
        "/scanner/live",
        params=live_params(strategy="break_and_retest"),
    )
    assert response.status_code == 404


def test_login_is_required():
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.get("/scanner/live", params=live_params()).status_code == 401


def test_bad_timeframe_is_422(api):
    client, _ = api
    response = client.get("/scanner/live", params=live_params(timeframe="not-a-tf"))
    assert response.status_code == 422


def test_bad_strategy_is_422(api):
    client, _ = api
    response = client.get("/scanner/live", params=live_params(strategy="not-a-strategy"))
    assert response.status_code == 422
