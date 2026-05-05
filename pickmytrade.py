"""
PickMyTrade Python SDK
======================

A community Python client for the PickMyTrade webhook API
(https://pickmytrade.io / https://pickmytrade.trade) that lets you place,
modify, and close trades from Python on every supported broker:

    Tradovate, Interactive Brokers, Rithmic, ProjectX / TopstepX,
    TradeLocker, TradeStation, Binance, Bybit, Match-Trader

The same JSON webhook that PickMyTrade builds for TradingView alerts is
exposed here as plain Python calls, so you can wire it into any indicator,
backtest replay, ML model, news scraper, cron job, or custom dashboard.

Quick start
-----------
    from pickmytrade import PickMyTradeClient, Broker

    client = PickMyTradeClient(token="YOUR_TOKEN", broker=Broker.TRADOVATE)
    client.buy(symbol="NQ", quantity=1, price=20000.25)
    client.sell(symbol="NQ", quantity=1, price=20010.00,
                dollar_sl=10, dollar_tp=20)              # 10/20 points
    client.close(symbol="NQ", quantity=1, price=20005.00)

Or, the original procedural style (kept for backward compatibility):

    from pickmytrade import buy, sell, close
    buy("NQ", 1, 20000.25, token="YOUR_TOKEN")

Authentication
--------------
You authenticate with a single string token issued by your PickMyTrade
dashboard. The token MUST be sent inside the JSON body, never in the URL or
in a header. Treat it like a password: keep it out of source control, load
it from an environment variable or a secrets manager, and rotate it if it
leaks.

TP/SL semantics (per the official PickMyTrade docs)
---------------------------------------------------
* ``tp``  / ``sl``                 - **Exact price level** (e.g. ``sl=18980``
                                    means the stop sits at price 18980).
* ``dollar_tp`` / ``dollar_sl``    - **Distance from entry, in points**
                                    (the "Point / Dollar (From Entry Price)"
                                    risk type in the PickMyTrade UI).
* ``percentage_tp`` / ``percentage_sl`` - **Percentage move** from entry.

Use exactly one TP method and one SL method per alert.

Rate limiting
-------------
PickMyTrade applies its own rate limiting and will return "Too Many
Requests" (and may temporarily block your IP / token) if you bombard the
webhook. To stay safely under the limit, this SDK ships with a built-in
sliding-window throttle of **3 requests per 5 seconds** per client. By
default it transparently sleeps when you hit the cap; pass
``rate_limit_action="raise"`` to surface a :class:`PickMyTradeRateLimitError`
instead. Disable entirely with ``rate_limit_max=0``.

This library is community-maintained and is not an official PickMyTrade
product. Always review brokerage terms, prop-firm rules, and local
regulations before automating live orders. **Test in a demo account
before pointing this at a real, funded account.**
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import logging
import os
import threading
import time
import warnings
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Union

import requests

__all__ = [
    "Broker",
    "OrderAction",
    "OrderType",
    "RiskType",
    "PickMyTradeError",
    "PickMyTradeAPIError",
    "PickMyTradeAuthError",
    "PickMyTradeRequestError",
    "PickMyTradeRateLimitError",
    "AdvancedTPSL",
    "MultiAccountEntry",
    "TradePayload",
    "PickMyTradeClient",
    # Backward-compatible procedural API
    "send_trade_request",
    "buy",
    "sell",
    "close",
    # Endpoint constants
    "DEFAULT_ENDPOINT",
    "TRADOVATE_ENDPOINT",
    "TRADOVATE_ENDPOINT_LATEST",
    "MULTIBROKER_ENDPOINT",
    "MULTIBROKER_ENDPOINT_LATEST",
    "LEGACY_ENDPOINT",
    # Broker capability lookup helpers (mirrors pickmytrade_validation)
    "BROKER_CAPABILITIES",
    "broker_supports_trailing",
    "broker_supports_trail_stop",
    "broker_supports_trail_trigger",
    "broker_supports_trail_freq",
    "broker_supports_breakeven",
    "broker_supports_update_tp_sl",
    "broker_supports_advance_tp_sl",
    "broker_supports_options",
    "get_allowed_inst_types",
]

__version__ = "1.1.0"

logger = logging.getLogger("pickmytrade")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
# Source: https://docs.pickmytrade.trade/docs/ and https://docs.pickmytrade.io/docs/
# - Tradovate-only platform uses api.pickmytrade.trade
# - Multi-broker platform (IB, Rithmic, ProjectX/TopstepX, TradeLocker,
#   TradeStation, Binance, Bybit, Match-Trader) uses api.pickmytrade.io
# - The "-latest" variant is the current preferred webhook URL.
TRADOVATE_ENDPOINT = "https://api.pickmytrade.trade/v2/add-trade-data"
TRADOVATE_ENDPOINT_LATEST = "https://api.pickmytrade.trade/v2/add-trade-data-latest"
MULTIBROKER_ENDPOINT = "https://api.pickmytrade.io/v2/add-trade-data"
MULTIBROKER_ENDPOINT_LATEST = "https://api.pickmytrade.io/v2/add-trade-data-latest"

# Default endpoint used when the caller does not specify one. Tradovate's
# v2-latest URL is the recommended starting point per the docs; users on
# other brokers should select Broker.<NAME> on the client which routes to
# MULTIBROKER_ENDPOINT_LATEST automatically.
DEFAULT_ENDPOINT = TRADOVATE_ENDPOINT_LATEST

# Legacy v1 endpoint - kept as a constant only for users who explicitly
# need to talk to the old URL. New code should use DEFAULT_ENDPOINT or
# the per-broker endpoint exposed by Broker.<NAME>.endpoint.
LEGACY_ENDPOINT = "https://pickmytrade.trade/api/add-trade-data"

DEFAULT_TIMEOUT = 15  # seconds

# PickMyTrade documents a "Too Many Requests" failure path. To stay under
# the cap and avoid IP / account blocks, the SDK throttles to this many
# requests per window by default. Override on the client if you have a
# different agreement with PickMyTrade.
DEFAULT_RATE_LIMIT_MAX = 3
DEFAULT_RATE_LIMIT_WINDOW = 5.0  # seconds


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Broker(str, Enum):
    """Brokers/platforms documented as supported by PickMyTrade.

    The ``endpoint`` property returns the canonical webhook URL that should
    be used for that broker. Tradovate is hosted on the ``.trade`` domain;
    every other broker is hosted on the multi-broker ``.io`` domain.
    """

    TRADOVATE = "tradovate"
    INTERACTIVE_BROKERS = "interactive_brokers"
    RITHMIC = "rithmic"
    PROJECTX = "projectx"          # TopstepX, TickTickTrader, etc.
    TOPSTEPX = "topstepx"          # alias of projectx (kept for clarity)
    TRADELOCKER = "tradelocker"
    TRADESTATION = "tradestation"
    TRADIER = "tradier"
    BINANCE = "binance"
    BYBIT = "bybit"
    MATCH_TRADER = "match_trader"

    @property
    def endpoint(self) -> str:
        if self is Broker.TRADOVATE:
            return TRADOVATE_ENDPOINT_LATEST
        return MULTIBROKER_ENDPOINT_LATEST

    @property
    def capability_key(self) -> str:
        """Map this enum value to the key used in BROKER_CAPABILITIES."""
        return _BROKER_CAPABILITY_KEY[self]

    @property
    def capabilities(self) -> Dict[str, Any]:
        """Return the broker capability dict, e.g. ``{"supports_trailing": True, ...}``."""
        return BROKER_CAPABILITIES.get(self.capability_key, {})


# ---------------------------------------------------------------------------
# Broker capability matrix
# ---------------------------------------------------------------------------
# Source of truth: pickmytrade_validation/broker_capabilities.py at
# https://github.com/bhavishyagoyal12/pickmytrade_validation
# Mirrored here so the SDK can warn callers when a feature isn't supported
# by the targeted broker. Keep in sync with upstream.
BROKER_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "RITHMIC": {
        "supports_trailing":      True,
        "supports_trail_stop":    False,
        "supports_trail_trigger": True,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       True,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["FUT", "FOP"],
    },
    "IB": {
        "supports_trailing":      True,
        "supports_trail_stop":    True,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     True,
        "supports_options":       True,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["STK", "FUT", "OPT", "FOP", "CASH"],
    },
    "TRADOVATE": {
        "supports_trailing":      True,
        "supports_trail_stop":    True,
        "supports_trail_trigger": True,
        "supports_trail_freq":    True,
        "supports_breakeven":     True,
        "supports_options":       True,
        "supports_update_tp_sl":  True,
        "supports_advance_tp_sl": True,
        "allowed_inst_types":     ["FUT"],
    },
    "TRADIER": {
        "supports_trailing":      False,
        "supports_trail_stop":    False,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       True,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["STK", "OPT"],
    },
    "TRADELOCKER": {
        "supports_trailing":      True,
        "supports_trail_stop":    True,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       False,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["EQUITY_CFD", "FOREX", "CRYPTO"],
    },
    "TRADESTATION": {
        "supports_trailing":      True,
        "supports_trail_stop":    True,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       True,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["STOCKS", "FUTURES", "OPTIONS"],
    },
    "PROJECTX": {
        "supports_trailing":      True,
        "supports_trail_stop":    False,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       False,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["FUT"],
        "notes": "TopstepX engine. Supports Futures only.",
    },
    "BINANCE": {
        "supports_trailing":      True,
        "supports_trail_stop":    True,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       False,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["CRYPTO", "FUTURE", "FUTURES"],
    },
    "BYBIT": {
        "supports_trailing":      True,
        "supports_trail_stop":    True,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       False,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["CRYPTO", "FUTURE", "FUTURES"],
    },
    "MATCHTRADER": {
        "supports_trailing":      True,
        "supports_trail_stop":    False,
        "supports_trail_trigger": False,
        "supports_trail_freq":    False,
        "supports_breakeven":     False,
        "supports_options":       False,
        "supports_update_tp_sl":  False,
        "supports_advance_tp_sl": False,
        "allowed_inst_types":     ["CFD", "FOREX", "FOREXCFD"],
    },
}

# Map our Broker enum members to the capability keys used above.
_BROKER_CAPABILITY_KEY: Dict["Broker", str] = {}


def _capability(broker: "Broker", flag: str) -> bool:
    return BROKER_CAPABILITIES.get(_BROKER_CAPABILITY_KEY.get(broker, ""), {}).get(flag, False)


def broker_supports_trailing(broker: Union["Broker", str]) -> bool:
    """Return True if PickMyTrade can route a trailing stop to this broker."""
    return _capability(_coerce_broker(broker), "supports_trailing")


def broker_supports_trail_stop(broker: Union["Broker", str]) -> bool:
    return _capability(_coerce_broker(broker), "supports_trail_stop")


def broker_supports_trail_trigger(broker: Union["Broker", str]) -> bool:
    return _capability(_coerce_broker(broker), "supports_trail_trigger")


def broker_supports_trail_freq(broker: Union["Broker", str]) -> bool:
    return _capability(_coerce_broker(broker), "supports_trail_freq")


def broker_supports_breakeven(broker: Union["Broker", str]) -> bool:
    return _capability(_coerce_broker(broker), "supports_breakeven")


def broker_supports_update_tp_sl(broker: Union["Broker", str]) -> bool:
    return _capability(_coerce_broker(broker), "supports_update_tp_sl")


def broker_supports_advance_tp_sl(broker: Union["Broker", str]) -> bool:
    return _capability(_coerce_broker(broker), "supports_advance_tp_sl")


def broker_supports_options(broker: Union["Broker", str]) -> bool:
    return _capability(_coerce_broker(broker), "supports_options")


def get_allowed_inst_types(broker: Union["Broker", str]) -> List[str]:
    """Return the instrument-type whitelist for the broker."""
    b = _coerce_broker(broker)
    caps = BROKER_CAPABILITIES.get(_BROKER_CAPABILITY_KEY.get(b, ""), {})
    return list(caps.get("allowed_inst_types", []))


def _coerce_broker(broker: Union["Broker", str]) -> "Broker":
    return broker if isinstance(broker, Broker) else Broker(broker)


# Populate the enum -> capability-key map now that the Broker class exists.
_BROKER_CAPABILITY_KEY.update({
    Broker.TRADOVATE:           "TRADOVATE",
    Broker.INTERACTIVE_BROKERS: "IB",
    Broker.RITHMIC:             "RITHMIC",
    Broker.PROJECTX:            "PROJECTX",
    Broker.TOPSTEPX:            "PROJECTX",   # TopstepX runs on the ProjectX engine
    Broker.TRADELOCKER:         "TRADELOCKER",
    Broker.TRADESTATION:        "TRADESTATION",
    Broker.TRADIER:             "TRADIER",
    Broker.BINANCE:             "BINANCE",
    Broker.BYBIT:               "BYBIT",
    Broker.MATCH_TRADER:        "MATCHTRADER",
})


class OrderAction(str, Enum):
    """Values accepted by the ``data`` field of the webhook payload."""

    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class OrderType(str, Enum):
    """Order types supported across PickMyTrade brokers.

    Note that PickMyTrade itself enforces some constraints, e.g. TradingView
    *strategy* alerts only emit market orders. See the PickMyTrade docs for
    broker-specific limitations.
    """

    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"


class RiskType(str, Enum):
    """How TP/SL distance is measured. Mirrors the PickMyTrade UI."""

    EXACT_PRICE = "price"      # uses tp / sl as absolute price levels
    POINTS = "points"          # uses dollar_tp / dollar_sl (Point / Dollar)
    DOLLARS = "dollars"        # uses dollar_tp / dollar_sl (alias of POINTS)
    PERCENTAGE = "percentage"  # uses percentage_tp / percentage_sl


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class PickMyTradeError(Exception):
    """Base class for every error raised by this SDK."""


class PickMyTradeAuthError(PickMyTradeError):
    """Raised when no token is provided or the token is rejected."""


class PickMyTradeRequestError(PickMyTradeError):
    """Raised on networking failures or non-2xx HTTP responses."""

    def __init__(self, message: str, *, status_code: Optional[int] = None,
                 response_body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PickMyTradeAPIError(PickMyTradeError):
    """Raised when the API returns a structured error in the JSON body."""

    def __init__(self, message: str, *, payload: Any = None) -> None:
        super().__init__(message)
        self.payload = payload


class PickMyTradeRateLimitError(PickMyTradeError):
    """Raised when the local SDK throttle would have to wait too long.

    Only raised when the client is configured with
    ``rate_limit_action="raise"``. The default behaviour is to sleep until
    the next slot opens and then proceed transparently.
    """

    def __init__(self, message: str, *, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
class _RateLimiter:
    """Sliding-window rate limiter (thread-safe).

    Tracks the timestamp of the last *N* requests; if a new request would
    push the count over the cap inside the window, ``acquire`` either
    sleeps until the oldest request falls out (default) or raises
    :class:`PickMyTradeRateLimitError` (when ``action="raise"``).

    A ``max=0`` limiter is a no-op (rate limiting disabled).
    """

    __slots__ = ("max", "window", "action", "_times", "_lock")

    def __init__(self, *, max_requests: int = DEFAULT_RATE_LIMIT_MAX,
                 window: float = DEFAULT_RATE_LIMIT_WINDOW,
                 action: str = "sleep") -> None:
        if max_requests < 0:
            raise ValueError("max_requests must be >= 0")
        if window <= 0:
            raise ValueError("window must be > 0")
        if action not in {"sleep", "raise"}:
            raise ValueError("action must be 'sleep' or 'raise'")
        self.max = int(max_requests)
        self.window = float(window)
        self.action = action
        self._times: Deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self.max == 0:
            return
        with self._lock:
            now = time.monotonic()
            # Drop any timestamps that have aged out of the window.
            while self._times and (now - self._times[0]) >= self.window:
                self._times.popleft()
            if len(self._times) >= self.max:
                wait = self.window - (now - self._times[0])
                if wait > 0:
                    if self.action == "raise":
                        raise PickMyTradeRateLimitError(
                            f"PickMyTrade SDK rate limit hit: max "
                            f"{self.max} requests / {self.window:g}s. "
                            f"Retry after {wait:.2f}s.",
                            retry_after=wait,
                        )
                    logger.warning(
                        "PickMyTrade SDK throttling for %.2fs (cap %d/%.0fs).",
                        wait, self.max, self.window,
                    )
                    time.sleep(wait)
                    now = time.monotonic()
                    while self._times and (now - self._times[0]) >= self.window:
                        self._times.popleft()
            self._times.append(now)


# Module-level limiter used by the procedural buy/sell/close helpers so the
# legacy callers also benefit from throttling.
_module_rate_limiter = _RateLimiter()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class AdvancedTPSL:
    """One leg of a multi-target exit plan (``advance_tp_sl`` array).

    Useful when scaling out: e.g. close 1 contract at +10 pts and another
    at +20 pts with the stop pulled to break-even after the first hit.

    .. note::
       Per the PickMyTrade docs, ``advance_tp_sl`` is currently supported
       on **Tradovate only**. Other brokers will ignore (or reject) the
       array.

    Each leg can express its target/stop in any of the three supported
    risk styles (``tp`` / ``dollar_tp`` / ``percentage_tp`` and the
    matching ``sl`` family).
    """

    quantity: int
    tp: float = 0
    sl: float = 0
    breakeven: float = 0
    breakeven_offset: float = 0
    dollar_tp: float = 0
    dollar_sl: float = 0
    percentage_tp: float = 0
    percentage_sl: float = 0
    trail: float = 0
    trail_stop: float = 0
    trail_trigger: float = 0
    trail_freq: float = 0


@dataclass
class MultiAccountEntry:
    """Single account override used inside the ``multiple_accounts`` array.

    Schema verified against the upstream
    `pickmytrade_validation <https://github.com/bhavishyagoyal12/pickmytrade_validation>`_
    validator:

    * ``account_id``       - required, exact account name in the broker UI.
    * ``connection_name``  - the PickMyTrade connection label (e.g.
                             ``"RITHMIC1"``) that points at this account.
                             **Required for Rithmic, IB, ProjectX/TopstepX,
                             TradeLocker, TradeStation, Tradier, Binance,
                             Bybit, Match-Trader.** **NOT required for
                             Tradovate** — Tradovate accounts are linked
                             directly to your PickMyTrade login, so leave
                             this empty.
    * ``token``            - required, the PickMyTrade token authorised for
                             this account.
    * ``risk_percentage``  - sizing in % of account; must be > 0 when the
                             top-level alert uses risk-based sizing.
    * ``quantity_multiplier`` - contract scaling factor; must be > 0 when
                             the top-level alert uses quantity-based sizing.

    The validator enforces "sizing-mode parity" — every entry must use the
    same sizing style as the parent alert (risk_percentage XOR
    quantity_multiplier). The SDK does not enforce this client-side; pass
    a consistent shape or PickMyTrade will reject the alert.
    """

    account_id: str
    connection_name: str = ""
    token: str = ""
    risk_percentage: float = 0
    quantity_multiplier: float = 0


@dataclass
class TradePayload:
    """Strongly-typed view of the JSON body POSTed to PickMyTrade.

    Field names match the keys the PickMyTrade backend expects, so the
    object can be fed directly to ``json.dumps`` after ``to_dict()``.
    Defaults match the documented "do nothing" values, so you only set
    the fields you actually need.

    See module docstring for the TP/SL semantics summary.
    """

    symbol: str
    data: str                       # "buy" | "sell" | "close"
    quantity: Union[int, float, str]
    price: Union[float, str] = 0
    token: str = ""
    account_id: str = ""

    # Timestamp - ISO8601 in UTC. PickMyTrade also accepts the
    # TradingView "{{timenow}}" placeholder when triggered from TV.
    date: str = ""

    # Order routing
    order_type: str = OrderType.MARKET.value
    stp_limit_stp_price: Union[float, str] = 0
    gtd_in_second: int = 0

    # Position sizing alternatives
    risk_percentage: float = 0

    # Take profit (use exactly one)
    # tp           = exact price level (e.g. 19100 means TP price = 19100)
    # dollar_tp    = distance in points/dollars from entry
    # percentage_tp= percentage move from entry
    tp: Union[float, str] = 0
    percentage_tp: float = 0
    dollar_tp: float = 0

    # Stop loss (use exactly one) - same semantics as the TP family above
    sl: Union[float, str] = 0
    percentage_sl: float = 0
    dollar_sl: float = 0

    # Trailing stop
    trail: float = 0
    trail_stop: float = 0
    trail_trigger: float = 0
    trail_freq: float = 0

    # Break-even
    breakeven: float = 0

    # Position management flags - defaults match the PickMyTrade docs
    update_tp: bool = False
    update_sl: bool = False
    pyramid: bool = False               # docs default: only one same-direction position
    duplicate_position_allow: bool = False  # legacy alias of pyramid
    reverse_order_close: bool = False
    same_direction_ignore: bool = False
    full_closed: bool = True
    comment: str = ""

    # Multi-leg exits (Tradovate only) and multi-account routing
    advance_tp_sl: List[AdvancedTPSL] = field(default_factory=list)
    multiple_accounts: List[MultiAccountEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return the dict that should be sent as the JSON body."""
        if not self.date:
            self.date = _utc_iso8601()
        body: Dict[str, Any] = asdict(self)
        body["advance_tp_sl"] = [asdict(leg) for leg in self.advance_tp_sl]
        body["multiple_accounts"] = [asdict(a) for a in self.multiple_accounts]
        return body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utc_iso8601() -> str:
    """Return current UTC time in the ISO8601 format the API accepts."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_token(token: Optional[str]) -> str:
    if not token or not isinstance(token, str) or not token.strip():
        raise PickMyTradeAuthError(
            "PickMyTrade token is missing. Generate one in your dashboard "
            "and pass it via the `token` argument or the PICKMYTRADE_TOKEN "
            "environment variable."
        )
    return token.strip()


def _validate_action(action: str) -> str:
    valid = {a.value for a in OrderAction}
    if action not in valid:
        raise ValueError(
            f"Invalid order action {action!r}. Expected one of {sorted(valid)}."
        )
    return action


def _validate_quantity(quantity: Union[int, float, str], *,
                       allow_zero: bool = False) -> Union[int, float, str]:
    """Validate the ``quantity`` field.

    Set ``allow_zero=True`` for SL/TP modification operations, where the
    PickMyTrade backend ignores quantity (only ``sl`` or ``tp`` is read).
    Otherwise quantity must be a positive number or a TradingView
    placeholder string.
    """
    if isinstance(quantity, str):
        if not quantity.strip():
            raise ValueError("quantity string must not be empty.")
        return quantity
    if not isinstance(quantity, (int, float)) or isinstance(quantity, bool):
        raise ValueError(f"quantity must be int|float|str, got {type(quantity).__name__}.")
    if allow_zero:
        if quantity < 0:
            raise ValueError(f"quantity must be >= 0 for updates, got {quantity}.")
    elif quantity <= 0:
        raise ValueError(f"quantity must be > 0, got {quantity}.")
    return quantity


def _check_broker_capabilities(broker: "Broker", payload: Mapping[str, Any]) -> None:
    """Warn when the payload uses a feature the broker doesn't support.

    Source: pickmytrade_validation/broker_capabilities.py. The check is
    advisory only — PickMyTrade itself remains the authoritative gatekeeper
    and may silently drop unsupported parameters.
    """
    def _truthy(key: str) -> bool:
        v = payload.get(key, 0)
        try:
            return float(v) != 0
        except (TypeError, ValueError):
            return bool(v)

    if _truthy("trail") and not broker_supports_trailing(broker):
        warnings.warn(
            f"`trail` is set but {broker.value!r} does not support trailing "
            "stops via PickMyTrade. The field will likely be ignored.",
            stacklevel=3,
        )
    if _truthy("trail_stop") and not broker_supports_trail_stop(broker):
        warnings.warn(
            f"`trail_stop` is set but {broker.value!r} does not accept it "
            "(see pickmytrade_validation broker capability matrix).",
            stacklevel=3,
        )
    if _truthy("trail_trigger") and not broker_supports_trail_trigger(broker):
        warnings.warn(
            f"`trail_trigger` is set but {broker.value!r} does not accept it.",
            stacklevel=3,
        )
    if _truthy("trail_freq") and not broker_supports_trail_freq(broker):
        warnings.warn(
            f"`trail_freq` is set but only Tradovate supports it; {broker.value!r} "
            "will ignore the value.",
            stacklevel=3,
        )
    if _truthy("breakeven") and not broker_supports_breakeven(broker):
        warnings.warn(
            f"`breakeven` is set but {broker.value!r} does not support PickMyTrade "
            "auto-breakeven; only Tradovate and IB do.",
            stacklevel=3,
        )
    if (payload.get("update_tp") or payload.get("update_sl")) and \
            not broker_supports_update_tp_sl(broker):
        warnings.warn(
            f"update_tp / update_sl is set but {broker.value!r} does not support "
            "in-place TP/SL modification; only Tradovate does.",
            stacklevel=3,
        )
    if payload.get("advance_tp_sl") and not broker_supports_advance_tp_sl(broker):
        warnings.warn(
            f"advance_tp_sl is set but {broker.value!r} does not support multi-leg "
            "scale-out; only Tradovate does.",
            stacklevel=3,
        )
    # connection_name is required on every multiple_accounts entry for
    # every broker EXCEPT Tradovate (Tradovate accounts are linked
    # directly to the PickMyTrade login).
    if broker is not Broker.TRADOVATE:
        for i, acc in enumerate(payload.get("multiple_accounts", []) or []):
            if isinstance(acc, dict) and not acc.get("connection_name"):
                warnings.warn(
                    f"multiple_accounts[{i}] is missing `connection_name` — "
                    f"this field is required for broker {broker.value!r} "
                    "(only Tradovate may omit it).",
                    stacklevel=3,
                )


def _check_single_tp_sl(payload: Mapping[str, Any]) -> None:
    """Warn (don't fail) when more than one TP or SL method is set.

    PickMyTrade documents that you should use exactly one TP method and one
    SL method per alert. Mixing them is a frequent foot-gun and PickMyTrade
    will silently pick one if you set several, so we emit a logger warning
    rather than blocking the call.
    """

    def _is_set(v: Any) -> bool:
        try:
            return float(v) != 0
        except (TypeError, ValueError):
            return bool(v) and v != "0"

    tp_count = sum(_is_set(payload.get(k, 0)) for k in ("tp", "dollar_tp", "percentage_tp"))
    sl_count = sum(_is_set(payload.get(k, 0)) for k in ("sl", "dollar_sl", "percentage_sl"))
    if tp_count > 1:
        logger.warning(
            "Multiple take-profit fields set (%d). PickMyTrade expects only one of "
            "tp / dollar_tp / percentage_tp per alert.", tp_count,
        )
    if sl_count > 1:
        logger.warning(
            "Multiple stop-loss fields set (%d). PickMyTrade expects only one of "
            "sl / dollar_sl / percentage_sl per alert.", sl_count,
        )


def _post_json(url: str, body: Dict[str, Any], *,
               session: Optional[requests.Session] = None,
               timeout: float = DEFAULT_TIMEOUT) -> Any:
    """POST ``body`` as JSON to ``url`` and return parsed JSON or raw text."""
    http = session or requests
    try:
        response = http.post(url, json=body, timeout=timeout)
    except requests.RequestException as exc:
        raise PickMyTradeRequestError(
            f"Network error calling PickMyTrade: {exc}"
        ) from exc

    try:
        parsed: Any = response.json()
    except ValueError:
        parsed = response.text

    if not response.ok:
        # 429 is the documented "Too Many Requests" path.
        if response.status_code == 429:
            raise PickMyTradeRateLimitError(
                "PickMyTrade returned HTTP 429 (Too Many Requests). "
                "Slow down or wait — repeated 429s can lead to a temporary "
                "IP / account block.",
            )
        raise PickMyTradeRequestError(
            f"PickMyTrade returned HTTP {response.status_code}",
            status_code=response.status_code,
            response_body=parsed,
        )

    # Surface API-level errors expressed in the body. The API tends to
    # return either {"status": "error", ...} or {"error": "..."}.
    if isinstance(parsed, dict):
        status = str(parsed.get("status", "")).lower()
        if status in {"error", "failed", "fail"} or "error" in parsed:
            message = parsed.get("message") or parsed.get("error") or "Unknown API error"
            raise PickMyTradeAPIError(str(message), payload=parsed)
    return parsed


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class PickMyTradeClient:
    """High-level PickMyTrade webhook client.

    Parameters
    ----------
    token:
        The API token from your PickMyTrade dashboard. If omitted, the
        ``PICKMYTRADE_TOKEN`` environment variable is read.
    broker:
        Which broker the orders should be routed to. Determines the default
        endpoint (Tradovate uses the ``.trade`` host; everything else uses
        the multi-broker ``.io`` host).
    account_id:
        Default account identifier sent with every request.
    endpoint:
        Override the webhook URL entirely. Useful for testing or for
        users who pasted a custom URL from their PickMyTrade dashboard.
    session:
        Optional ``requests.Session`` for connection pooling/retries.
    timeout:
        Per-request HTTP timeout in seconds.
    default_payload:
        Mapping merged into every request before user kwargs override it.
        Use this for site-wide defaults like ``{"order_type": "MKT"}``.
    rate_limit_max:
        Maximum requests per ``rate_limit_window`` seconds. Defaults to
        3. Set ``0`` to disable rate limiting.
    rate_limit_window:
        Sliding-window length in seconds. Defaults to 5.
    rate_limit_action:
        ``"sleep"`` (default) — block transparently when the cap is hit;
        ``"raise"`` — raise :class:`PickMyTradeRateLimitError` instead.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        broker: Union[Broker, str] = Broker.TRADOVATE,
        account_id: str = "",
        endpoint: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = DEFAULT_TIMEOUT,
        default_payload: Optional[Mapping[str, Any]] = None,
        rate_limit_max: int = DEFAULT_RATE_LIMIT_MAX,
        rate_limit_window: float = DEFAULT_RATE_LIMIT_WINDOW,
        rate_limit_action: str = "sleep",
    ) -> None:
        token = token or os.getenv("PICKMYTRADE_TOKEN")
        self.token = _validate_token(token)
        self.broker = broker if isinstance(broker, Broker) else Broker(broker)
        self.account_id = account_id
        self.endpoint = endpoint or self.broker.endpoint
        self.session = session
        self.timeout = timeout
        self.default_payload: Dict[str, Any] = dict(default_payload or {})
        self._limiter = _RateLimiter(
            max_requests=rate_limit_max,
            window=rate_limit_window,
            action=rate_limit_action,
        )

    # ---- Convenience order helpers ----
    def buy(self, symbol: str, quantity: Union[int, float, str], price: Union[float, str] = 0,
            **kwargs: Any) -> Any:
        """Submit a buy order. See :meth:`send` for all keyword arguments."""
        return self.send(symbol=symbol, action=OrderAction.BUY,
                         quantity=quantity, price=price, **kwargs)

    def sell(self, symbol: str, quantity: Union[int, float, str], price: Union[float, str] = 0,
             **kwargs: Any) -> Any:
        """Submit a sell order. See :meth:`send` for all keyword arguments."""
        return self.send(symbol=symbol, action=OrderAction.SELL,
                         quantity=quantity, price=price, **kwargs)

    def close(self, symbol: str, quantity: Union[int, float, str] = 0,
              price: Union[float, str] = 0, *, full_closed: bool = True,
              **kwargs: Any) -> Any:
        """Close an open position (or part of one).

        Set ``full_closed=False`` together with ``comment`` and a ``quantity``
        less than the open size to do a partial close.
        """
        return self.send(symbol=symbol, action=OrderAction.CLOSE,
                         quantity=quantity, price=price, _allow_zero_qty=True,
                         full_closed=full_closed, **kwargs)

    def update_take_profit(self, symbol: str, tp: float, **kwargs: Any) -> Any:
        """Modify the TP on every open position for ``symbol``.

        Per the PickMyTrade docs, when ``update_tp=true`` is sent the
        backend reads **only** the ``tp`` field as an exact price level
        (it does NOT compute from ``dollar_tp`` or ``percentage_tp``),
        and applies the new value to **every open position for that
        symbol**. Pass the exact target price, not a distance in points.
        """
        if tp is None or float(tp) <= 0:
            raise ValueError("update_take_profit requires an exact TP price > 0.")
        return self.send(symbol=symbol, action=OrderAction.BUY, quantity=0,
                         tp=tp, update_tp=True, _allow_zero_qty=True,
                         _update_only="tp", **kwargs)

    def update_stop_loss(self, symbol: str, sl: float, **kwargs: Any) -> Any:
        """Modify the SL on every open position for ``symbol``.

        Per the PickMyTrade docs, when ``update_sl=true`` is sent the
        backend reads **only** the ``sl`` field as an exact price level
        (it does NOT compute from ``dollar_sl`` or ``percentage_sl``),
        and applies the new value to **every open position for that
        symbol**. Pass the exact stop price, not a distance in points.
        """
        if sl is None or float(sl) <= 0:
            raise ValueError("update_stop_loss requires an exact SL price > 0.")
        return self.send(symbol=symbol, action=OrderAction.BUY, quantity=0,
                         sl=sl, update_sl=True, _allow_zero_qty=True,
                         _update_only="sl", **kwargs)

    # ---- Core dispatcher ----
    def send(
        self,
        *,
        symbol: str,
        action: Union[OrderAction, str],
        quantity: Union[int, float, str],
        price: Union[float, str] = 0,
        account_id: Optional[str] = None,
        # Internal flags - underscore-prefixed and stripped from the body.
        _allow_zero_qty: bool = False,
        _update_only: Optional[str] = None,
        # All TradePayload fields below are forwarded as overrides
        **kwargs: Any,
    ) -> Any:
        """Build a ``TradePayload`` and POST it to the configured endpoint."""
        if not symbol or not isinstance(symbol, str):
            raise ValueError("symbol must be a non-empty string.")
        action_value = action.value if isinstance(action, OrderAction) else _validate_action(action)
        _validate_quantity(quantity, allow_zero=_allow_zero_qty)

        payload = TradePayload(
            symbol=symbol,
            data=action_value,
            quantity=quantity,
            price=price,
            token=self.token,
            account_id=self.account_id if account_id is None else account_id,
        )

        # Apply client-wide defaults first, then per-call overrides.
        merged = payload.to_dict()
        merged.update(self.default_payload)
        for key, value in kwargs.items():
            if key not in merged and key not in {"advance_tp_sl", "multiple_accounts"}:
                # Allow new keys for forward-compatibility with PickMyTrade
                # adding fields to the schema, but log so users notice typos.
                logger.debug("Adding non-standard field to payload: %s", key)
            if key == "advance_tp_sl" and isinstance(value, Iterable):
                value = [
                    asdict(v) if isinstance(v, AdvancedTPSL) else dict(v)
                    for v in value
                ]
            elif key == "multiple_accounts" and isinstance(value, Iterable):
                value = [
                    asdict(v) if isinstance(v, MultiAccountEntry) else dict(v)
                    for v in value
                ]
            merged[key] = value

        # Mirror pyramid <-> duplicate_position_allow.
        if "duplicate_position_allow" in kwargs and "pyramid" not in kwargs:
            merged["pyramid"] = bool(kwargs["duplicate_position_allow"])
        if "pyramid" in kwargs and "duplicate_position_allow" not in kwargs:
            merged["duplicate_position_allow"] = bool(kwargs["pyramid"])

        # Update-only mode: zero out the *other* TP/SL fields and warn the
        # user about the all-positions side effect (per PickMyTrade docs).
        if _update_only == "tp":
            merged["dollar_tp"] = 0
            merged["percentage_tp"] = 0
            logger.warning(
                "update_tp affects ALL open positions for symbol %r — "
                "PickMyTrade applies the new TP to every open trade on "
                "that symbol.", symbol,
            )
        elif _update_only == "sl":
            merged["dollar_sl"] = 0
            merged["percentage_sl"] = 0
            logger.warning(
                "update_sl affects ALL open positions for symbol %r — "
                "PickMyTrade applies the new SL to every open trade on "
                "that symbol.", symbol,
            )

        # Broker capability checks - warn (don't block) when the user
        # sets a feature their broker doesn't support per the upstream
        # pickmytrade_validation matrix.
        _check_broker_capabilities(self.broker, merged)

        _check_single_tp_sl(merged)
        self._limiter.acquire()
        logger.debug("PickMyTrade POST %s: %s", self.endpoint,
                     _json.dumps({**merged, "token": "***"}))
        return _post_json(self.endpoint, merged,
                          session=self.session, timeout=self.timeout)


# ---------------------------------------------------------------------------
# Backward-compatible procedural API
# ---------------------------------------------------------------------------
# These wrappers preserve the original signature published in version 0.x of
# this sample. New code should prefer ``PickMyTradeClient`` instead.
def send_trade_request(
    symbol: str,
    data: str,
    quantity: Union[int, float],
    price: Union[float, str],
    token: str,
    account_id: str = "",
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT,
    extra: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Send a single trade request using the original sample-script schema.

    The default endpoint is :data:`DEFAULT_ENDPOINT`
    (``https://api.pickmytrade.trade/v2/add-trade-data-latest``), which is
    the recommended Tradovate URL. Pass ``endpoint=`` to target another
    URL — for non-Tradovate brokers use
    :data:`MULTIBROKER_ENDPOINT_LATEST`.

    ``extra`` is merged after the default payload so callers can opt into
    advanced fields (``trail``, ``breakeven``, etc.) without switching to the
    class-based client.
    """
    _validate_token(token)
    _validate_action(data)
    _validate_quantity(quantity, allow_zero=(data == "close"))

    body: Dict[str, Any] = {
        "symbol": symbol,
        "date": _utc_iso8601(),
        "data": data,
        "quantity": quantity,
        "risk_percentage": 0,
        "price": price,
        "tp": 0,
        "sl": 0,
        "trail": 0,
        "update_tp": False,
        "update_sl": False,
        "duplicate_position_allow": False,
        "pyramid": False,
        "reverse_order_close": False,
        "token": token,
        "account_id": account_id,
    }
    if extra:
        body.update(extra)
    _check_single_tp_sl(body)
    _module_rate_limiter.acquire()
    return _post_json(endpoint, body, timeout=timeout)


def buy(symbol: str, quantity: Union[int, float], price: Union[float, str],
        token: str, account_id: str = "", **kwargs: Any) -> Any:
    """Backward-compatible buy helper (matches the original script)."""
    return send_trade_request(symbol, "buy", quantity, price, token, account_id, **kwargs)


def sell(symbol: str, quantity: Union[int, float], price: Union[float, str],
         token: str, account_id: str = "", **kwargs: Any) -> Any:
    """Backward-compatible sell helper (matches the original script)."""
    return send_trade_request(symbol, "sell", quantity, price, token, account_id, **kwargs)


def close(symbol: str, quantity: Union[int, float], price: Union[float, str],
          token: str, account_id: str = "", **kwargs: Any) -> Any:
    """Backward-compatible close helper (matches the original script)."""
    return send_trade_request(symbol, "close", quantity, price, token, account_id, **kwargs)


# ---------------------------------------------------------------------------
# CLI sample
# ---------------------------------------------------------------------------
def _demo() -> None:
    """Print a sample payload (no network call) so the file is safe to run.

    Run ``python pickmytrade.py`` to inspect what the JSON body looks like
    for a typical buy order. To actually place an order, import the SDK
    from your own script and call :class:`PickMyTradeClient`.
    """
    sample = TradePayload(
        symbol="NQ",
        data=OrderAction.BUY.value,
        quantity=1,
        price=20000.25,
        token="<YOUR_PICKMYTRADE_TOKEN>",
        account_id="<YOUR_ACCOUNT_ID>",
        dollar_sl=10,              # 10-point stop loss (distance from entry)
        dollar_tp=20,              # 20-point take profit (distance from entry)
        breakeven=5,               # move SL to break-even after 5 pts
        order_type=OrderType.MARKET.value,
    )
    print("Example PickMyTrade webhook payload:")
    print(_json.dumps(sample.to_dict(), indent=2, default=str))
    print()
    print("Endpoints documented by PickMyTrade:")
    for name in ("DEFAULT_ENDPOINT", "TRADOVATE_ENDPOINT", "TRADOVATE_ENDPOINT_LATEST",
                 "MULTIBROKER_ENDPOINT", "MULTIBROKER_ENDPOINT_LATEST", "LEGACY_ENDPOINT"):
        print(f"  {name:30s} -> {globals()[name]}")
    print()
    print("Supported brokers:")
    for broker in Broker:
        print(f"  {broker.value:20s} -> {broker.endpoint}")
    print()
    print(f"Built-in rate limit: {DEFAULT_RATE_LIMIT_MAX} requests / "
          f"{DEFAULT_RATE_LIMIT_WINDOW:g}s (per client). "
          "Bombarding the API can get your IP/account blocked — keep this on.")


if __name__ == "__main__":
    _demo()
