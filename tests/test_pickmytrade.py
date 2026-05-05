"""Unit tests for the PickMyTrade SDK.

These tests run fully offline by stubbing :mod:`requests`, so no real
PickMyTrade token is required and no order ever leaves the machine.
"""

from __future__ import annotations

import json
import warnings
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

import pickmytrade
from pickmytrade import (
    DEFAULT_ENDPOINT,
    AdvancedTPSL,
    Broker,
    MultiAccountEntry,
    OrderAction,
    OrderType,
    PickMyTradeAPIError,
    PickMyTradeAuthError,
    PickMyTradeClient,
    PickMyTradeRateLimitError,
    PickMyTradeRequestError,
    TradePayload,
    buy,
    close,
    sell,
    send_trade_request,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, *, status_code: int = 200, json_body: Any = None,
                 text: str = "") -> None:
        self.status_code = status_code
        self._json = json_body
        self.text = text or json.dumps(json_body) if json_body is not None else ""
        self.ok = 200 <= status_code < 300

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json body")
        return self._json


def _capture_post(monkeypatch, response: _FakeResponse) -> List[Dict[str, Any]]:
    """Replace requests.post and capture every call body."""
    calls: List[Dict[str, Any]] = []

    def _fake(url: str, json: Dict[str, Any] = None, timeout: float = None,
              **_: Any) -> _FakeResponse:
        calls.append({"url": url, "json": json, "timeout": timeout})
        return response

    monkeypatch.setattr(pickmytrade.requests, "post", _fake)
    return calls


# ---------------------------------------------------------------------------
# Enum / endpoint tests
# ---------------------------------------------------------------------------
def test_tradovate_uses_trade_endpoint() -> None:
    assert Broker.TRADOVATE.endpoint.startswith("https://api.pickmytrade.trade/")


@pytest.mark.parametrize("broker", [
    Broker.INTERACTIVE_BROKERS, Broker.RITHMIC, Broker.PROJECTX,
    Broker.TOPSTEPX, Broker.TRADELOCKER, Broker.TRADESTATION,
    Broker.BINANCE, Broker.BYBIT, Broker.MATCH_TRADER,
])
def test_non_tradovate_uses_io_endpoint(broker: Broker) -> None:
    assert broker.endpoint.startswith("https://api.pickmytrade.io/")


def test_endpoint_constants_match_docs() -> None:
    assert pickmytrade.LEGACY_ENDPOINT == "https://pickmytrade.trade/api/add-trade-data"
    assert pickmytrade.TRADOVATE_ENDPOINT_LATEST.endswith("/v2/add-trade-data-latest")
    assert pickmytrade.MULTIBROKER_ENDPOINT_LATEST.endswith("/v2/add-trade-data-latest")


# ---------------------------------------------------------------------------
# Auth / validation
# ---------------------------------------------------------------------------
def test_client_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.delenv("PICKMYTRADE_TOKEN", raising=False)
    with pytest.raises(PickMyTradeAuthError):
        PickMyTradeClient(token=None)


def test_client_reads_token_from_env(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "env-token")
    c = PickMyTradeClient()
    assert c.token == "env-token"


def test_client_rejects_blank_token() -> None:
    with pytest.raises(PickMyTradeAuthError):
        PickMyTradeClient(token="   ")


def test_send_rejects_invalid_action(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "x")
    c = PickMyTradeClient()
    with pytest.raises(ValueError):
        c.send(symbol="NQ", action="hold", quantity=1)


def test_send_rejects_zero_quantity(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "x")
    c = PickMyTradeClient()
    with pytest.raises(ValueError):
        c.buy(symbol="NQ", quantity=0)


def test_send_rejects_empty_symbol(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "x")
    c = PickMyTradeClient()
    with pytest.raises(ValueError):
        c.send(symbol="", action=OrderAction.BUY, quantity=1)


def test_quantity_accepts_string_placeholder(monkeypatch) -> None:
    """TradingView placeholders pass through as strings."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "x")
    c = PickMyTradeClient()
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    c.buy(symbol="NQ", quantity="{{strategy.order.contracts}}", price=20000)
    assert captured[0]["json"]["quantity"] == "{{strategy.order.contracts}}"


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------
def test_buy_payload_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.TRADOVATE, account_id="ACC1")
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    c.buy(symbol="NQ", quantity=2, price=20000.5, sl=10, tp=20, breakeven=5)

    body = captured[0]["json"]
    assert captured[0]["url"] == Broker.TRADOVATE.endpoint
    assert body["symbol"] == "NQ"
    assert body["data"] == "buy"
    assert body["quantity"] == 2
    assert body["price"] == 20000.5
    assert body["sl"] == 10
    assert body["tp"] == 20
    assert body["breakeven"] == 5
    assert body["token"] == "tok-1"
    assert body["account_id"] == "ACC1"
    # Date should be ISO8601 UTC with Z suffix.
    assert body["date"].endswith("Z")
    assert "T" in body["date"]


def test_sell_close_payloads(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.RITHMIC, account_id="APX")
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    c.sell(symbol="NQM5", quantity=1, price=20020)
    c.close(symbol="NQM5", quantity=1, price=20015, full_closed=False, comment="leg-1")

    assert captured[0]["json"]["data"] == "sell"
    assert captured[1]["json"]["data"] == "close"
    assert captured[1]["json"]["full_closed"] is False
    assert captured[1]["json"]["comment"] == "leg-1"


def test_advance_tp_sl_serialised(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.TRADOVATE)
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    c.buy(symbol="NQ", quantity=2, price=20000, advance_tp_sl=[
        AdvancedTPSL(quantity=1, tp=10, sl=10),
        AdvancedTPSL(quantity=1, tp=20, sl=10, breakeven=10),
    ])
    legs = captured[0]["json"]["advance_tp_sl"]
    # The AdvancedTPSL dataclass carries every field PickMyTrade documents
    # for an exit leg (extended in v1.1) - assert the user-set fields and
    # that defaults are zero / empty.
    assert legs[0]["quantity"] == 1
    assert legs[0]["tp"] == 10
    assert legs[0]["sl"] == 10
    assert legs[0]["breakeven"] == 0
    assert legs[0]["dollar_tp"] == 0 and legs[0]["percentage_sl"] == 0
    assert legs[1]["breakeven"] == 10


def test_advance_tp_sl_warns_on_non_tradovate(monkeypatch) -> None:
    """Per pickmytrade_validation, advance_tp_sl is Tradovate-only."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.RITHMIC)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with pytest.warns(UserWarning, match="advance_tp_sl"):
        c.buy(symbol="NQ", quantity=1, price=20000,
              advance_tp_sl=[AdvancedTPSL(quantity=1, tp=10)])


# ---------------------------------------------------------------------------
# Broker capability matrix (sourced from pickmytrade_validation)
# ---------------------------------------------------------------------------
def test_capability_helpers_match_upstream_matrix() -> None:
    from pickmytrade import (
        broker_supports_trailing, broker_supports_breakeven,
        broker_supports_update_tp_sl, broker_supports_advance_tp_sl,
        broker_supports_trail_freq, broker_supports_options,
        get_allowed_inst_types,
    )
    # Tradier: zero PickMyTrade-side risk features
    assert broker_supports_trailing(Broker.TRADIER) is False
    assert broker_supports_options(Broker.TRADIER) is True
    assert get_allowed_inst_types(Broker.TRADIER) == ["STK", "OPT"]
    # Tradovate: every supported feature
    for fn in (broker_supports_trailing, broker_supports_breakeven,
               broker_supports_update_tp_sl, broker_supports_advance_tp_sl,
               broker_supports_trail_freq):
        assert fn(Broker.TRADOVATE) is True, fn.__name__
    # IB: trailing yes, but no trail_trigger / no advance_tp_sl
    assert broker_supports_trailing(Broker.INTERACTIVE_BROKERS) is True
    assert broker_supports_advance_tp_sl(Broker.INTERACTIVE_BROKERS) is False
    # TopstepX maps to PROJECTX
    assert Broker.TOPSTEPX.capability_key == "PROJECTX"


def test_trail_warns_on_tradier(monkeypatch) -> None:
    """Tradier doesn't support trailing per the upstream matrix."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.TRADIER)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with pytest.warns(UserWarning, match=r"trail.*tradier"):
        c.buy(symbol="AAPL", quantity=1, price=180,
              trail=1, trail_stop=1)


def test_breakeven_warns_on_rithmic(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.RITHMIC)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with pytest.warns(UserWarning, match="breakeven"):
        c.buy(symbol="NQ", quantity=1, price=20000, dollar_sl=10, breakeven=5)


def test_breakeven_no_warning_on_ib(monkeypatch) -> None:
    """IB supports breakeven per the matrix - no warning expected."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.INTERACTIVE_BROKERS)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        c.buy(symbol="ES", quantity=1, price=5050, dollar_sl=10, breakeven=5)


def test_update_tp_warns_on_non_tradovate(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.INTERACTIVE_BROKERS)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with pytest.warns(UserWarning, match="update_tp"):
        c.update_take_profit(symbol="ES", tp=5100)


def test_missing_connection_name_warns_on_non_tradovate(monkeypatch) -> None:
    """connection_name is required on every multiple_accounts entry for
    every broker except Tradovate (verified against the upstream
    pickmytrade_validation/validator.py)."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.RITHMIC)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with pytest.warns(UserWarning, match="connection_name"):
        c.buy(
            symbol="NQM5", quantity=1, price=20000,
            multiple_accounts=[
                MultiAccountEntry(account_id="A", token="t",
                                  quantity_multiplier=1),  # missing connection_name
            ],
        )


def test_missing_connection_name_quiet_on_tradovate(monkeypatch) -> None:
    """Tradovate accounts are linked directly to the PickMyTrade login,
    so connection_name may be omitted without warnings."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.TRADOVATE)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        c.buy(
            symbol="NQ", quantity=1, price=20000,
            multiple_accounts=[
                MultiAccountEntry(account_id="A", token="t",
                                  quantity_multiplier=1),  # no connection_name OK
            ],
        )


def test_trail_no_warning_on_tradovate(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(broker=Broker.TRADOVATE)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        c.buy(symbol="NQ", quantity=1, price=20000,
              trail=1, trail_stop=8, trail_trigger=20, trail_freq=2,
              breakeven=10)


def test_multiple_accounts_serialised(monkeypatch) -> None:
    """Schema verified against pickmytrade_validation/validator.py:
    each entry requires account_id, connection_name, token; sizing is
    either risk_percentage or quantity_multiplier."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    c.buy(symbol="NQ", quantity=1, price=20000, multiple_accounts=[
        MultiAccountEntry(account_id="A", connection_name="RITHMIC1",
                          token="tok-A", quantity_multiplier=1),
        MultiAccountEntry(account_id="B", connection_name="RITHMIC2",
                          token="tok-B", quantity_multiplier=2),
    ])
    accs = captured[0]["json"]["multiple_accounts"]
    assert accs[0] == {
        "account_id": "A", "connection_name": "RITHMIC1",
        "token": "tok-A", "risk_percentage": 0, "quantity_multiplier": 1.0,
    }
    assert accs[1] == {
        "account_id": "B", "connection_name": "RITHMIC2",
        "token": "tok-B", "risk_percentage": 0, "quantity_multiplier": 2.0,
    }
    # Importantly, no reverse_action key — that field is not in the
    # upstream PickMyTrade validator schema.
    assert "reverse_action" not in accs[0]
    assert "reverse_action" not in accs[1]


def test_pyramid_and_duplicate_position_allow_aliased(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    c.buy(symbol="NQ", quantity=1, price=20000, pyramid=False)
    body = captured[0]["json"]
    assert body["pyramid"] is False
    assert body["duplicate_position_allow"] is False


def test_default_payload_merged(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(default_payload={"order_type": "LMT"})
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    c.buy(symbol="NQ", quantity=1, price=20000)
    assert captured[0]["json"]["order_type"] == "LMT"


def test_per_call_kwargs_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(default_payload={"order_type": "LMT"})
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    c.buy(symbol="NQ", quantity=1, price=20000, order_type="MKT")
    assert captured[0]["json"]["order_type"] == "MKT"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
def test_http_error_raises(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    _capture_post(monkeypatch, _FakeResponse(status_code=500,
                                             json_body={"message": "boom"}))
    with pytest.raises(PickMyTradeRequestError) as excinfo:
        c.buy(symbol="NQ", quantity=1, price=20000)
    assert excinfo.value.status_code == 500


def test_api_error_raises(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    _capture_post(monkeypatch, _FakeResponse(
        status_code=200, json_body={"status": "error", "message": "bad symbol"}))
    with pytest.raises(PickMyTradeAPIError) as excinfo:
        c.buy(symbol="ZZZ", quantity=1, price=1)
    assert "bad symbol" in str(excinfo.value)


def test_network_failure_raises(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise pickmytrade.requests.ConnectionError("dns")

    monkeypatch.setattr(pickmytrade.requests, "post", _boom)
    with pytest.raises(PickMyTradeRequestError):
        c.buy(symbol="NQ", quantity=1, price=20000)


# ---------------------------------------------------------------------------
# Backward-compatible procedural API
# ---------------------------------------------------------------------------
def test_legacy_buy_defaults_to_v2_tradovate_endpoint(monkeypatch) -> None:
    """Procedural API now defaults to the recommended v2-latest URL."""
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    buy("AAPL", 1, 150.0, "tok-1", account_id="ACC")
    assert captured[0]["url"] == DEFAULT_ENDPOINT
    assert captured[0]["url"] == "https://api.pickmytrade.trade/v2/add-trade-data-latest"
    body = captured[0]["json"]
    assert body["symbol"] == "AAPL"
    assert body["data"] == "buy"
    assert body["token"] == "tok-1"
    assert body["account_id"] == "ACC"


def test_legacy_endpoint_constant_still_available() -> None:
    """LEGACY_ENDPOINT remains exported for users who explicitly need it."""
    assert pickmytrade.LEGACY_ENDPOINT == "https://pickmytrade.trade/api/add-trade-data"


def test_legacy_buy_can_target_legacy_endpoint(monkeypatch) -> None:
    """Users can still hit the legacy v1 URL by passing endpoint= explicitly."""
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    send_trade_request("AAPL", "buy", 1, 150.0, "tok-1",
                       endpoint=pickmytrade.LEGACY_ENDPOINT)
    assert captured[0]["url"] == pickmytrade.LEGACY_ENDPOINT


def test_legacy_helpers_match_actions(monkeypatch) -> None:
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    buy("AAPL", 1, 150, "t")
    sell("AAPL", 1, 150, "t")
    close("AAPL", 1, 150, "t")
    assert [c["json"]["data"] for c in captured] == ["buy", "sell", "close"]


def test_legacy_send_trade_request_extra(monkeypatch) -> None:
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    send_trade_request("NQ", "buy", 1, 20000, "tok",
                       extra={"trail": 1, "trail_trigger": 5, "trail_stop": 3})
    body = captured[0]["json"]
    assert body["trail"] == 1
    assert body["trail_trigger"] == 5
    assert body["trail_stop"] == 3


# ---------------------------------------------------------------------------
# TradePayload model
# ---------------------------------------------------------------------------
def test_trade_payload_to_dict_fills_date() -> None:
    p = TradePayload(symbol="NQ", data="buy", quantity=1, token="t")
    body = p.to_dict()
    assert body["date"].endswith("Z")
    assert body["symbol"] == "NQ"
    assert "advance_tp_sl" in body
    assert "multiple_accounts" in body


def test_trade_payload_round_trip_safe_to_json() -> None:
    p = TradePayload(symbol="NQ", data="buy", quantity=1, token="t",
                     advance_tp_sl=[AdvancedTPSL(quantity=1, tp=10, sl=10)],
                     multiple_accounts=[MultiAccountEntry(account_id="A")])
    body = p.to_dict()
    json.dumps(body)  # would raise if non-serialisable


# ---------------------------------------------------------------------------
# Docs-verified defaults
# ---------------------------------------------------------------------------
def test_pyramid_defaults_to_false() -> None:
    """Per docs.pickmytrade.trade pyramid defaults to false."""
    p = TradePayload(symbol="NQ", data="buy", quantity=1, token="t").to_dict()
    assert p["pyramid"] is False
    assert p["duplicate_position_allow"] is False


def test_full_closed_defaults_to_true() -> None:
    p = TradePayload(symbol="NQ", data="buy", quantity=1, token="t").to_dict()
    assert p["full_closed"] is True


def test_close_accepts_zero_quantity(monkeypatch) -> None:
    """close() must allow quantity=0 for full-position close calls."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    c.close(symbol="NQ", quantity=0, price=20000)
    assert captured[0]["json"]["data"] == "close"


# ---------------------------------------------------------------------------
# update_take_profit / update_stop_loss
# ---------------------------------------------------------------------------
def test_update_take_profit_only_sets_tp(monkeypatch) -> None:
    """Per docs: when update_tp=true the backend reads ONLY tp (exact price)."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    c.update_take_profit(symbol="NQ", tp=19100)
    body = captured[0]["json"]
    assert body["update_tp"] is True
    assert body["tp"] == 19100
    assert body["dollar_tp"] == 0
    assert body["percentage_tp"] == 0
    assert body["quantity"] == 0


def test_update_stop_loss_only_sets_sl(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    c.update_stop_loss(symbol="NQ", sl=18980)
    body = captured[0]["json"]
    assert body["update_sl"] is True
    assert body["sl"] == 18980
    assert body["dollar_sl"] == 0
    assert body["percentage_sl"] == 0
    assert body["quantity"] == 0


def test_update_take_profit_rejects_zero_or_negative_price(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient()
    with pytest.raises(ValueError):
        c.update_take_profit(symbol="NQ", tp=0)
    with pytest.raises(ValueError):
        c.update_stop_loss(symbol="NQ", sl=-5)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
def test_rate_limiter_sleeps_when_cap_hit(monkeypatch) -> None:
    """Default behaviour: sleep until next slot opens."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(rate_limit_max=2, rate_limit_window=0.2)
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))

    sleeps: list = []
    monkeypatch.setattr(pickmytrade.time, "sleep", lambda s: sleeps.append(s))

    for _ in range(4):
        c.buy(symbol="NQ", quantity=1, price=20000)

    # Cap is 2 per 0.2s, so 4 calls should produce at least one sleep.
    assert len(sleeps) >= 1
    assert all(s > 0 for s in sleeps)


def test_rate_limiter_can_raise_instead_of_sleep(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(rate_limit_max=2, rate_limit_window=0.5,
                          rate_limit_action="raise")
    _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    c.buy(symbol="NQ", quantity=1, price=20000)
    c.buy(symbol="NQ", quantity=1, price=20000)
    with pytest.raises(PickMyTradeRateLimitError) as excinfo:
        c.buy(symbol="NQ", quantity=1, price=20000)
    assert excinfo.value.retry_after > 0


def test_rate_limiter_disabled_with_max_zero(monkeypatch) -> None:
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(rate_limit_max=0)
    captured = _capture_post(monkeypatch, _FakeResponse(json_body={"status": "ok"}))
    sleeps: list = []
    monkeypatch.setattr(pickmytrade.time, "sleep", lambda s: sleeps.append(s))
    for _ in range(10):
        c.buy(symbol="NQ", quantity=1, price=20000)
    assert sleeps == []
    assert len(captured) == 10


def test_http_429_raises_rate_limit_error(monkeypatch) -> None:
    """A 429 from the server surfaces as PickMyTradeRateLimitError."""
    monkeypatch.setenv("PICKMYTRADE_TOKEN", "tok-1")
    c = PickMyTradeClient(rate_limit_max=0)  # don't trip the local limiter
    _capture_post(monkeypatch, _FakeResponse(status_code=429,
                                             json_body={"message": "slow down"}))
    with pytest.raises(PickMyTradeRateLimitError):
        c.buy(symbol="NQ", quantity=1, price=20000)
