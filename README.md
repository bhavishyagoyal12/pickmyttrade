# PickMyTrade Python SDK

> The **PickMyTrade Python SDK** is a community-maintained Python client for the [PickMyTrade](https://pickmytrade.io) webhook API. It lets you automate **Tradovate, Interactive Brokers, Rithmic, ProjectX/TopstepX, TradeLocker, TradeStation, Tradier, Binance, Bybit, and Match-Trader** from Python — no TradingView Pine script required.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen.svg)](#testing)

_Last verified against the PickMyTrade docs: **2026-05-05** · Maintainer: community contributors._

**Official PickMyTrade resources**

| Resource | URL |
|---|---|
| Multi-broker site (IB, Rithmic, ProjectX, TradeLocker, TradeStation, Tradier, Binance, Bybit, Match-Trader) | <https://pickmytrade.io> |
| Tradovate-only site | <https://pickmytrade.trade> |
| Multi-broker docs | <https://docs.pickmytrade.io/docs/> |
| Tradovate docs | <https://docs.pickmytrade.trade/docs/> |
| Multi-broker app dashboard | <https://app.pickmytrade.io> |
| Multi-broker webhook | `https://api.pickmytrade.io/v2/add-trade-data-latest` |
| Tradovate webhook | `https://api.pickmytrade.trade/v2/add-trade-data-latest` |
| Upstream validator (broker capability source-of-truth) | <https://github.com/bhavishyagoyal12/pickmytrade_validation> |

> **Entity capsule:** The PickMyTrade Python SDK (community, MIT-licensed, v1.1.0, Python 3.8+) is an unofficial Python wrapper around the PickMyTrade webhook API documented at [docs.pickmytrade.io](https://docs.pickmytrade.io/docs/) and [docs.pickmytrade.trade](https://docs.pickmytrade.trade/docs/). PickMyTrade itself is hosted at [pickmytrade.io](https://pickmytrade.io) (multi-broker) and [pickmytrade.trade](https://pickmytrade.trade) (Tradovate). This SDK is not affiliated with PickMyTrade Inc.

PickMyTrade is a hosted automation layer that turns TradingView alerts into live broker orders. This SDK wraps the same webhook the dashboard generates, so you can drive PickMyTrade from any Python runtime — backtest replays, ML inference loops, news scrapers, cron jobs, FastAPI endpoints, or Streamlit dashboards.

## Table of contents

- [Why this SDK](#why-this-sdk)
- [Supported brokers](#supported-brokers)
- [Broker capability matrix (verified)](#broker-capability-matrix-verified)
- [Install](#install)
- [Quick start](#quick-start)
- [Authentication](#authentication)
- [Webhook endpoints](#webhook-endpoints)
- [Order parameters reference](#order-parameters-reference)
- [Field deep-dive](#field-deep-dive)
- [Take-profit, stop-loss and trailing stops](#take-profit-stop-loss-and-trailing-stops)
- [Multi-account routing](#multi-account-routing)
- [Modifying open orders](#modifying-open-orders)
- [Rate limiting](#rate-limiting)
- [Backward-compatible procedural API](#backward-compatible-procedural-api)
- [Examples](#examples)
- [Error handling](#error-handling)
- [Testing](#testing)
- [Project layout](#project-layout)
- [FAQ](#faq)
- [Disclaimer](#disclaimer)
- [License](#license)

## Why this SDK

PickMyTrade ships an excellent web dashboard, but everything is driven by a TradingView webhook. The SDK lets you reach the same webhook from Python so you can:

- **Trade signals from custom indicators** that don't exist on TradingView.
- **Replay backtests through a live router** to compare paper vs. real fills.
- **Hook ML model outputs** (regression, classification, RL agents) directly into a broker.
- **Schedule and cron** entries from a server, no charts open required.
- **Test order flow in CI** — every HTTP call is mockable with `requests-mock` or `unittest.mock`, so no live token is needed.

The library is a thin, well-typed wrapper over a documented HTTPS endpoint — no extra brokerage agreement, no proprietary protocol, no scraped pages.

## Supported brokers

Every broker listed in the official PickMyTrade docs is exposed through the same `Broker` enum:

| Broker | Instrument types | Endpoint host | PickMyTrade docs |
|---|---|---|---|
| **Tradovate** (live + demo) | FUT | `api.pickmytrade.trade` | [docs.pickmytrade.trade](https://docs.pickmytrade.trade/docs/) |
| **Interactive Brokers (IB / IBKR)** | STK, FUT, OPT, FOP, CASH | `api.pickmytrade.io` | [docs.pickmytrade.io – IB](https://docs.pickmytrade.io/docs-category/interactive-brokers/) |
| **Rithmic** (Apex, Bulenox, Earn2Trade…) | FUT, FOP | `api.pickmytrade.io` | [docs.pickmytrade.io – Rithmic](https://docs.pickmytrade.io/docs-category/rithmic/) |
| **ProjectX / TopstepX** | FUT (max 1000-tick SL) | `api.pickmytrade.io` | [docs.pickmytrade.io – ProjectX](https://docs.pickmytrade.io/docs-category/projectx/) |
| **TradeLocker** | EQUITY_CFD, FOREX, CRYPTO | `api.pickmytrade.io` | [docs.pickmytrade.io – TradeLocker](https://docs.pickmytrade.io/docs-category/tradelocker/) |
| **TradeStation** | STOCKS, FUTURES, OPTIONS | `api.pickmytrade.io` | [docs.pickmytrade.io – TradeStation](https://docs.pickmytrade.io/docs/setting-up-tradingview-alerts-for-automated-trading/) |
| **Tradier** | STK, OPT | `api.pickmytrade.io` | [docs.pickmytrade.io](https://docs.pickmytrade.io/docs/) |
| **Binance** | CRYPTO, FUTURES | `api.pickmytrade.io` | [docs.pickmytrade.io](https://docs.pickmytrade.io/docs/) |
| **Bybit** | CRYPTO, FUTURES | `api.pickmytrade.io` | [docs.pickmytrade.io](https://docs.pickmytrade.io/docs/) |
| **Match-Trader** | CFD, FOREX | `api.pickmytrade.io` | [docs.pickmytrade.io](https://docs.pickmytrade.io/docs/) |

The SDK picks the right host automatically when you pass `broker=Broker.<NAME>`. Tradovate uses the `.trade` host; everything else uses the multi-broker `.io` host.

> **Quick fact:** The PickMyTrade Python SDK supports 10 brokers across futures, equities, options, forex, and crypto through a single `Broker` enum and two endpoint hosts (`api.pickmytrade.trade` for Tradovate, `api.pickmytrade.io` for every other broker). Source: [docs.pickmytrade.io](https://docs.pickmytrade.io/docs/), [docs.pickmytrade.trade](https://docs.pickmytrade.trade/docs/).

### Broker capability matrix (verified)

Not every broker accepts every PickMyTrade JSON field. The matrix below mirrors the official [`pickmytrade_validation`](https://github.com/bhavishyagoyal12/pickmytrade_validation/blob/main/src/pickmytrade_validation/broker_capabilities.py) source-of-truth used by PickMyTrade itself, and the SDK emits a `UserWarning` if you set a field your broker does not support.

| Broker | Trailing | `trail_stop` | `trail_trigger` | `trail_freq` | `breakeven` | `update_tp/sl` | `advance_tp_sl` | Options |
|---|---|---|---|---|---|---|---|---|
| **Tradovate** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Interactive Brokers** | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| **Rithmic** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **ProjectX / TopstepX** | ✅¹ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **TradeStation** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **TradeLocker** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Tradier** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Binance** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Bybit** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Match-Trader** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

¹ ProjectX/TopstepX has its own broker-side Auto-Trailing Stop Loss configured in the ProjectX dashboard; the trailing-related JSON fields are not honoured.

Look the matrix up programmatically:

```python
from pickmytrade import (
    Broker, BROKER_CAPABILITIES,
    broker_supports_trailing, broker_supports_breakeven,
    broker_supports_advance_tp_sl, broker_supports_update_tp_sl,
    get_allowed_inst_types,
)

broker_supports_trailing(Broker.TRADIER)            # False
broker_supports_breakeven(Broker.RITHMIC)           # False
broker_supports_advance_tp_sl(Broker.TRADOVATE)     # True
get_allowed_inst_types(Broker.INTERACTIVE_BROKERS)  # ['STK', 'FUT', 'OPT', 'FOP', 'CASH']
Broker.TRADOVATE.capabilities                       # full dict
```

## Install

From source (until the package is published to PyPI):

```bash
git clone https://github.com/pickmytrade/pickmytrade-python.git
cd pickmytrade-python
pip install .
```

For local development (editable install with test extras):

```bash
pip install -e ".[dev]"
```

Or vendor `pickmytrade.py` directly into your project — it's a single ~640-line module whose only runtime dependency is `requests`.

## Quick start

```python
from pickmytrade import PickMyTradeClient, Broker

client = PickMyTradeClient(
    token="YOUR_PICKMYTRADE_TOKEN",   # generated in your dashboard
    broker=Broker.TRADOVATE,
    account_id="DEMO12345",
)

# Market buy 1 NQ contract with a 10-point stop and 20-point take profit
# (dollar_sl / dollar_tp = distance in points/dollars from entry)
client.buy(symbol="NQ", quantity=1, price=20000.25, dollar_sl=10, dollar_tp=20)

# Flat the position
client.close(symbol="NQ", quantity=1, price=20005.00)
```

That's the entire happy path. Every other feature (trailing stops, OCO brackets, multi-account fan-out, partial closes, dynamic SL/TP modifications) is opt-in via keyword arguments on the same `send` / `buy` / `sell` / `close` methods.

> **Heads-up:** the SDK throttles to **3 requests per 5 seconds** by default. Bombarding the PickMyTrade webhook from Python can trigger a "Too Many Requests" response and **a temporary IP/account block**, so leave the throttle on or use a tighter limit if your account agreement says so. See [Rate limiting](#rate-limiting).

## Authentication

**Short answer:** instantiate `PickMyTradeClient(token="…", broker=Broker.TRADOVATE, account_id="…")` and call `.buy()` / `.sell()` / `.close()`. The token is read from the `PICKMYTRADE_TOKEN` environment variable if you omit it.

PickMyTrade authenticates with a single string **token** issued in your dashboard. The token must travel inside the JSON body — never in the URL, never in a header. The SDK does this for you, but you should still:

1. **Never commit your token.** Use environment variables or a secrets manager.
2. **Rotate immediately** if it leaks (a public repo, a screenshot, etc.).
3. **Use a separate token per environment** (paper, prop firm, personal) so you can revoke one without breaking the others.

```python
import os
from pickmytrade import PickMyTradeClient

# Reads PICKMYTRADE_TOKEN from the environment by default
client = PickMyTradeClient(broker="tradovate", account_id=os.environ["PMT_ACCOUNT"])
```

## Webhook endpoints

For **Tradovate** use:

```
https://api.pickmytrade.trade/v2/add-trade-data-latest
```

For **every other broker** (Interactive Brokers, Rithmic, ProjectX/TopstepX, TradeLocker, TradeStation, Binance, Bybit, Match-Trader) use:

```
https://api.pickmytrade.io/v2/add-trade-data-latest
```

The SDK picks the right URL automatically when you set `broker=Broker.<NAME>`. You can also paste a custom webhook URL from your PickMyTrade dashboard via `endpoint=`.

| Constant | URL | When to use |
|---|---|---|
| `DEFAULT_ENDPOINT` | `https://api.pickmytrade.trade/v2/add-trade-data-latest` | The Tradovate v2-latest URL — used as default when no broker-specific override is set. |
| `TRADOVATE_ENDPOINT_LATEST` | `https://api.pickmytrade.trade/v2/add-trade-data-latest` | **Recommended** Tradovate endpoint. |
| `TRADOVATE_ENDPOINT` | `https://api.pickmytrade.trade/v2/add-trade-data` | Older Tradovate v2 endpoint. |
| `MULTIBROKER_ENDPOINT_LATEST` | `https://api.pickmytrade.io/v2/add-trade-data-latest` | **Recommended** endpoint for IB, Rithmic, ProjectX/TopstepX, TradeLocker, TradeStation, Binance, Bybit, Match-Trader. |
| `MULTIBROKER_ENDPOINT` | `https://api.pickmytrade.io/v2/add-trade-data` | Older multi-broker v2 endpoint. |
| `LEGACY_ENDPOINT` | `https://pickmytrade.trade/api/add-trade-data` | Deprecated v1 URL. Kept as a constant for users who explicitly need it; new code should use `DEFAULT_ENDPOINT`. |

You can override the endpoint per client:

```python
client = PickMyTradeClient(
    token="...",
    broker=Broker.TRADOVATE,
    endpoint="https://api.pickmytrade.trade/v2/add-trade-data",  # pin to v2 base
)
```

## Order parameters reference

A PickMyTrade webhook request is a single HTTPS `POST` with a JSON body. Minimum viable payload:

```json
{
  "token": "YOUR_PICKMYTRADE_TOKEN",
  "symbol": "NQ",
  "data": "buy",
  "quantity": 1,
  "price": 20000.25,
  "order_type": "MKT",
  "account_id": "DEMO12345",
  "sl": 10,
  "tp": 20
}
```

POST it to `https://api.pickmytrade.trade/v2/add-trade-data-latest` for Tradovate, or `https://api.pickmytrade.io/v2/add-trade-data-latest` for every other broker. The token lives in the JSON body, not in a header.

Every field accepted by the PickMyTrade webhook is exposed on the `TradePayload` dataclass and on `client.send(...)` / `client.buy(...)` / `client.sell(...)` / `client.close(...)`:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `symbol` | `str` | _required_ | Ticker (e.g. `"NQ"`, `"AAPL"`, `"BTCUSDT"`, `"BTCUSD.X"`). |
| `data` | `"buy"` / `"sell"` / `"close"` | _required_ | Order action. |
| `quantity` | `int` / `float` / `str` | _required_ | Contracts/shares. Accepts a TradingView placeholder string. |
| `price` | `float` / `str` | `0` | Reference price; non-zero builds a limit order. |
| `order_type` | `"MKT"` / `"LMT"` / `"STP"` / `"STP LMT"` | `"MKT"` | Order routing type. |
| `stp_limit_stp_price` | `float` | `0` | Trigger price for stop-limit orders. |
| `gtd_in_second` | `int` | `0` | Good-til-date duration in seconds (indicator alerts only). |
| `risk_percentage` | `float` | `0` | Auto-size by % of account when non-zero. |
| `tp` | `float` / `str` | `0` | **Exact take-profit price level** (e.g. `tp=19100` puts the TP at price 19100). **Use exactly one TP method.** |
| `dollar_tp` | `float` | `0` | Take-profit **distance from entry, in points/dollars** ("Point / Dollar (From Entry Price)" in the dashboard). |
| `percentage_tp` | `float` | `0` | Take-profit as a **percentage move** from entry (e.g. `1.5` = 1.5%). |
| `sl` | `float` / `str` | `0` | **Exact stop-loss price level** (e.g. `sl=18980`). **Use exactly one SL method.** |
| `dollar_sl` | `float` | `0` | Stop-loss **distance from entry, in points/dollars**. |
| `percentage_sl` | `float` | `0` | Stop-loss as a **percentage move** from entry. |
| `trail` | `float` | `0` | `1` enables the trailing stop; `0` disables it. |
| `trail_trigger` | `float` | `0` | Profit (points) required before the trail arms. |
| `trail_stop` | `float` | `0` | Distance (points) the stop maintains behind price once armed. |
| `trail_freq` | `float` | `0` | Minimum favourable move (points) between trail adjustments. |
| `breakeven` | `float` | `0` | Move SL to break-even after this many points of profit. |
| `update_tp` | `bool` | `false` | When `true`, the backend modifies the existing TP using the exact price in `tp` (other TP fields ignored). See [Modifying open orders](#modifying-open-orders). |
| `update_sl` | `bool` | `false` | When `true`, the backend modifies the existing SL using the exact price in `sl` (other SL fields ignored). |
| `pyramid` (alias `duplicate_position_allow`) | `bool` | `false` | When `true`, multiple same-direction entries can stack into one combined position. Default per docs: `false`. |
| `reverse_order_close` | `bool` | `false` | When `true`, an entry in the opposite direction first flattens the existing position before opening the new one. |
| `same_direction_ignore` | `bool` | `false` | When `true`, a new alert in the same direction as an open position is silently dropped. |
| `full_closed` | `bool` | `true` | When `true`, a `close` action exits the entire position; set `false` for partial close together with `comment` + `quantity`. |
| `comment` | `str` | `""` | Tag the entry so a later `close` with `full_closed=false` can target that specific leg (indicator alerts only). |
| `advance_tp_sl` | `list[AdvancedTPSL]` | `[]` | Multi-leg scale-out plan. **Tradovate only.** |
| `multiple_accounts` | `list[MultiAccountEntry]` | `[]` | Fan a single signal out to multiple accounts. Each entry needs `account_id`, `token`, sizing field, and (for non-Tradovate brokers) `connection_name`. |
| `account_id` | `str` | `""` | Target broker account id (e.g. Tradovate account name, IB account number). |
| `token` | `str` | _required_ | Your PickMyTrade token (set on the client; copied into every body). |

The SDK warns (but does not block) if you set more than one TP method or more than one SL method in the same call — that's the most common foot-gun in the PickMyTrade docs.

### Field deep-dive

The fields below combine to define the actual trading behaviour. Each note links back to the official PickMyTrade article it's based on.

**`tp` vs `dollar_tp` vs `percentage_tp` (and the matching SL trio).** Three different ways to express the same target: `tp` is the literal price the order should rest at, `dollar_tp` is a distance from your fill in points/dollars, `percentage_tp` is a percentage of price. Mixing two in one alert is unsupported; the SDK logs a warning and PickMyTrade silently picks one. ([JSON alert configuration](https://docs.pickmytrade.trade/docs/tradingview-json-alert-configuration/))

**`pyramid` / `duplicate_position_allow`.** Per the [stacking-orders article](https://docs.pickmytrade.trade/docs/pickmytrade-stacking-orders-json/), defaults to `false`: a single same-direction position is held at a time. Set `true` to let "Multiple buy signals open multiple buy orders. Multiple sell signals open multiple sell orders" — useful for averaging-in/scale-in strategies. `duplicate_position_allow` is kept as a legacy alias; set either, the SDK mirrors the value to both keys.

**`reverse_order_close`.** Combine with an opposite-direction entry to close-and-reverse in one alert. Useful for systems that flip from long to short on a single signal. Per the docs, when `true` it "ignores comment and closes most recent position first" before placing the new entry. ([Advanced features](https://docs.pickmytrade.trade/docs/pickmytrade-advanced-trading-features/))

**`same_direction_ignore`.** From the [docs](https://docs.pickmytrade.trade/docs/same-direction-ignore-json-alert/): "If a position is already open in a certain direction (buy/sell), ignore any new alerts that come in the same direction." Effectively the inverse of `pyramid` — they should not be set together.

**`full_closed` + `comment`.** For partial closes from indicator alerts: tag the entry with a `comment` (e.g. `"leg-1"`), then later send a `close` with `full_closed=false`, the same `comment`, and a `quantity` smaller than the open size. Without these flags a `close` always exits the full position. ([Advanced features](https://docs.pickmytrade.trade/docs/pickmytrade-advanced-trading-features/))

**`advance_tp_sl`.** A list of legs scaling out of a single entry. Per the PickMyTrade [multi-TP/SL article](https://docs.pickmytrade.trade/docs/pickmytrade-multiple-tp-sl-strategy-workaround/), the dashboard generates this array and warns: *"Do not modify advance_tp_sl... they remain exactly as generated"* — meaning each leg is a complete `{quantity, tp, sl, breakeven, …}` object the backend executes verbatim. **This feature is documented as Tradovate-only**; the SDK emits a `UserWarning` if you supply it for any other broker.

**`multiple_accounts`.** A list of accounts that should receive the same signal. Per the [upstream PickMyTrade validator](https://github.com/bhavishyagoyal12/pickmytrade_validation/blob/main/src/pickmytrade_validation/validator.py), each entry must carry:

- `account_id` — the exact account name as displayed in your broker.
- `connection_name` — the PickMyTrade connection label (e.g. `"RITHMIC1"`). **Required for every broker except Tradovate.** For Tradovate the field can be omitted because the account is linked directly to your PickMyTrade login.
- `token` — the PickMyTrade token authorised for that account.
- Either `risk_percentage` (when the parent alert uses risk-based sizing) **or** `quantity_multiplier` (when the parent alert uses fixed-quantity sizing). Mixing the two modes is rejected by the validator.

The SDK exposes this as the `MultiAccountEntry` dataclass and emits a `UserWarning` when a non-Tradovate broker sees an entry with no `connection_name`. Trades execute simultaneously across every entry, with position size computed independently per account.

**`account_id`.** The exact account name as it appears in your trading platform (e.g. Tradovate "DEMO12345", IB "U1234567", Rithmic "APEX-12345"). When `multiple_accounts` is set, the top-level `account_id` is the primary; per-entry `account_id` overrides it for that entry.

**`token`.** A single bearer-style string from your PickMyTrade dashboard. PickMyTrade requires it inside the JSON body field `"token"`; never as a URL query string and never as an HTTP header. Each `multiple_accounts` entry can carry its own token to fan-out across user accounts.

## Take-profit, stop-loss and trailing stops

Three different ways to express the **same** target — pick one per alert:

```python
# 1. Exact price level (sl / tp = the literal price the order rests at)
#    SL at 19990, TP at 20020.50.
client.buy("NQ", 1, 20000, sl=19990, tp=20020.50)

# 2. Distance in points/dollars from entry (the "Point / Dollar" risk type)
#    10-point stop, 20-point target.
client.buy("NQ", 1, 20000, dollar_sl=10, dollar_tp=20)

# 3. Percentage of price
client.buy("BTCUSDT", 0.05, 68000, percentage_sl=1.0, percentage_tp=2.0)
```

> Setting more than one TP method (or more than one SL method) in a single call logs a warning and the backend silently picks one — keep it to one.

### Trailing stops, step-by-step

A trailing stop is wired up by four fields. They work as a system, not in isolation:

| Field | What it does |
|---|---|
| `trail` | `1` arms the trailing logic, `0` disables it. |
| `trail_trigger` | The profit (points) the trade must reach **before** the trail starts moving. |
| `trail_stop` | The distance the stop maintains **behind** the highest favourable price once armed. |
| `trail_freq` | The minimum favourable move (points) needed before the stop is re-pulled. Higher = fewer adjustments. |

Concrete walk-through — long NQ at 20000 with `trail_trigger=20, trail_stop=8, trail_freq=2`:

1. Price moves from 20000 → 20019. Profit is +19 pts. **No change** — the trigger (20) is not yet hit, the protective `dollar_sl=10` is still in effect at 19990.
2. Price ticks 20020. Profit hits +20 pts. **Trail arms.** New stop = 20020 − 8 = **20012**.
3. Price runs to 20025 (+25 pts). The favourable move from the last adjustment is 5 pts (≥ `trail_freq=2`), so the stop pulls up to 20025 − 8 = **20017**.
4. Price wiggles to 20026 (+1 pt move, < `trail_freq=2`). **No adjustment**.
5. Price drops back to 20017. The trailing stop fills, locking in +17 pts.

Combined with break-even:

```python
client.buy(
    symbol="NQ",
    quantity=1,
    price=20000,
    dollar_sl=10,         # initial protective stop, 10 pts under entry
    breakeven=10,         # move SL to entry once +10 pts are realised
    trail=1,              # arm the trailing stop
    trail_trigger=20,     # …after +20 pts of profit
    trail_stop=8,         # trail 8 pts behind the high-water mark
    trail_freq=2,         # only re-pull when price advances ≥ 2 pts
)
```

### Trailing support varies by broker

The four-knob trailing recipe above is the **Tradovate** sweet spot. Per the [verified capability matrix](#broker-capability-matrix-verified), other brokers accept a subset:

- **IB / TradeStation / TradeLocker / Binance / Bybit** — accept `trail` + `trail_stop` only. `trail_trigger` and `trail_freq` are ignored.
- **Rithmic** — accepts `trail` + `trail_trigger` only. `trail_stop` and `trail_freq` are ignored.
- **ProjectX / TopstepX** — `trail` is acknowledged but the actual trailing distance is configured in the ProjectX dashboard, not via JSON.
- **Match-Trader** — accepts `trail` only.
- **Tradier** — does **not** support trailing stops at all; the SDK warns and the field is dropped.

The SDK inspects your `Broker.<NAME>` and emits a `UserWarning` on every unsupported field so the bug is loud, not silent.

### Multi-leg scale-out (Tradovate only)

`advance_tp_sl` is supported on **Tradovate only** per the upstream validation matrix. Each leg is a self-contained `{quantity, tp, sl, breakeven, …}` object that the backend executes verbatim. Example: 3-contract NQ entry, scale 1c out at +10, 1c at +20, and let the last contract run on the trailing stop with SL pulled to break-even:

```python
from pickmytrade import AdvancedTPSL

client.buy(   # client.broker must be Broker.TRADOVATE
    symbol="NQ",
    quantity=3,
    price=20000,
    advance_tp_sl=[
        AdvancedTPSL(quantity=1, dollar_tp=10, dollar_sl=10),
        AdvancedTPSL(quantity=1, dollar_tp=20, dollar_sl=10, breakeven=10),
        AdvancedTPSL(quantity=1, dollar_tp=0,  dollar_sl=10, breakeven=20),
    ],
    trail=1, trail_trigger=20, trail_stop=8, trail_freq=2,
)
```

If the client's `broker` is anything other than `Broker.TRADOVATE`, the SDK emits a `UserWarning` because PickMyTrade does not document support for `advance_tp_sl` on the multi-broker hosts.

## Multi-account routing

Mirror one signal across many accounts on the same broker. Each entry needs the broker `account_id`, the PickMyTrade `connection_name` it lives under (omit for Tradovate), the `token` authorised for that account, and either `quantity_multiplier` or `risk_percentage` depending on the parent alert's sizing mode.

**Rithmic / IB / TradeStation / TradeLocker / Tradier / Binance / Bybit / Match-Trader / ProjectX:** `connection_name` required.

```python
from pickmytrade import MultiAccountEntry

client.sell(   # broker=Broker.RITHMIC, top-level uses fixed quantity
    symbol="NQM5", quantity=1, price=20020,
    dollar_sl=10, dollar_tp=20,
    multiple_accounts=[
        MultiAccountEntry(account_id="APEX-12345", connection_name="RITHMIC1",
                          token="tok_a", quantity_multiplier=1),
        MultiAccountEntry(account_id="APEX-67890", connection_name="RITHMIC2",
                          token="tok_a", quantity_multiplier=2),
        MultiAccountEntry(account_id="BULENOX-11", connection_name="BULENOX1",
                          token="tok_b", quantity_multiplier=1),
    ],
)
```

**Tradovate:** `connection_name` may be omitted (Tradovate accounts are linked directly to your PickMyTrade login):

```python
client.buy(    # broker=Broker.TRADOVATE
    symbol="NQ", quantity=1, price=20000,
    dollar_sl=10, dollar_tp=20,
    multiple_accounts=[
        MultiAccountEntry(account_id="DEMO12345", token="tok",
                          quantity_multiplier=1),
        MultiAccountEntry(account_id="DEMO67890", token="tok",
                          quantity_multiplier=2),
    ],
)
```

The SDK warns at runtime if you forget `connection_name` on a non-Tradovate broker. Sizing-mode parity (every entry must use the same `quantity_multiplier` vs `risk_percentage` style as the parent alert) is enforced server-side by PickMyTrade — pass a consistent shape or the alert will be rejected.

## Modifying open orders

```python
# IMPORTANT: pass the EXACT PRICE for the new SL/TP, not a distance in points.
client.update_stop_loss(symbol="NQ", sl=18980)        # move SL to price 18980
client.update_take_profit(symbol="NQ", tp=19100)      # move TP to price 19100
```

Per the [official update SL/TP article](https://docs.pickmytrade.trade/docs/update-sl-tp-tradovate-pickmytrade/):

> *"SL and TP will be updated with the **exact values** you pass in the alert"* and *"We do not calculate in points, dollar_tp, or dollar_sl"*.

Critical caveats from the same docs page:

1. **Exact price only** — the helper raises a `ValueError` if you pass `0` or a negative number, since PickMyTrade interprets the value as the literal price level the order should rest at. `dollar_sl`, `dollar_tp`, `percentage_sl`, `percentage_tp` are not read in this mode (the SDK zeroes them out before sending).
2. **Affects every open position for the symbol** — *"using `update_sl: true` or `update_tp: true` will overwrite and apply the new SL/TP values to all positions for that symbol"*. The SDK logs a warning to remind you.
3. **Tradovate only** — `update_tp` / `update_sl` is documented as supported only on Tradovate. The SDK emits a `UserWarning` if your client targets any other broker.

Internally `update_take_profit` and `update_stop_loss` send `update_tp=true` / `update_sl=true` with `quantity=0`, the action set to `buy` (the action field is ignored in update mode), and only the relevant `tp` or `sl` price populated.

## Rate limiting

PickMyTrade returns **HTTP 429 ("Too Many Requests")** if you flood the webhook, and repeated 429s can lead to a **temporary IP or account block** — exactly the situation you do not want when an automated strategy is running. To stay safe by default, the SDK ships with a built-in **sliding-window throttle of 3 requests every 5 seconds** per `PickMyTradeClient` instance. The procedural `buy` / `sell` / `close` helpers share a module-wide limiter with the same defaults.

```python
from pickmytrade import PickMyTradeClient, PickMyTradeRateLimitError

# Default behaviour: transparently sleep until the next slot opens.
c = PickMyTradeClient(token="…", broker="tradovate")

# Tighter (or looser) throttle — measured in requests per window.
c = PickMyTradeClient(token="…", rate_limit_max=2, rate_limit_window=10)

# Surface the cap as an exception instead of sleeping.
c = PickMyTradeClient(token="…", rate_limit_action="raise")
try:
    c.buy("NQ", 1, 20000)
except PickMyTradeRateLimitError as exc:
    print(f"Backed off — retry after {exc.retry_after:.1f}s")

# Disable entirely (only do this if your account agreement explicitly allows it).
c = PickMyTradeClient(token="…", rate_limit_max=0)
```

If the server itself returns HTTP 429, the SDK raises `PickMyTradeRateLimitError` (a subclass of `PickMyTradeError`) so you can catch and back off without confusing it with a generic network failure.

> **Operational guidance:** never wrap the SDK in a tight retry loop. A 429 is the network telling you to slow down — respect it, or you risk losing the ability to send orders at the worst possible moment.

## Backward-compatible procedural API

The original sample-script style still works. Existing scripts that import `buy`, `sell`, `close` from `pickmytrade` continue to function with no changes:

```python
from pickmytrade import buy, sell, close

buy("AAPL", 3, 150.00, "YOUR_TOKEN", account_id="")
sell("AAPL", 3, 151.00, "YOUR_TOKEN", account_id="")
close("AAPL", 3, 150.50, "YOUR_TOKEN", account_id="")
```

Pass advanced fields through the `extra` keyword:

```python
from pickmytrade import send_trade_request

send_trade_request("NQ", "buy", 1, 20000, "YOUR_TOKEN",
                   extra={"trail": 1, "trail_trigger": 5, "trail_stop": 3})
```

## Examples

The [`examples/`](examples/) folder is broker-by-broker:

| File | Demonstrates |
|---|---|
| [`tradovate_basic.py`](examples/tradovate_basic.py) | Bread-and-butter buy / sell / close on Tradovate. |
| [`interactive_brokers.py`](examples/interactive_brokers.py) | IB stocks + IB futures with dollar-based risk, `trail` + `trail_stop`, and break-even (the IB-supported subset). |
| [`rithmic_apex.py`](examples/rithmic_apex.py) | Rithmic + Apex / Bulenox / Earn2Trade prop accounts with multi-account fan-out. |
| [`projectx_topstepx.py`](examples/projectx_topstepx.py) | TopstepX bracket order with broker-side auto-trailing. |
| [`tradelocker_crypto.py`](examples/tradelocker_crypto.py) | Crypto and forex symbol notation (`BTCUSD.X`, `EURUSD.X`) plus `trail` + `trail_stop`. |
| [`tradestation.py`](examples/tradestation.py) | TradeStation stocks + futures with $-based risk and trailing. |
| [`tradier_options.py`](examples/tradier_options.py) | Tradier stocks and stock options (no trailing / break-even per the capability matrix). |
| [`binance_bybit.py`](examples/binance_bybit.py) | Spot crypto on Binance and Bybit. |
| [`advanced_trailing.py`](examples/advanced_trailing.py) | Tradovate-only: full trailing + break-even + multi-leg `advance_tp_sl`. |
| [`update_existing_orders.py`](examples/update_existing_orders.py) | Modify SL/TP at an exact price (Tradovate only). |
| [`backward_compatible.py`](examples/backward_compatible.py) | Original procedural style for legacy scripts. |

Each script reads `PICKMYTRADE_TOKEN` from the environment. None of them ship with real tokens, accounts, or symbols you don't recognise.

## Error handling

The SDK raises four typed exceptions so you can react surgically:

```python
from pickmytrade import (
    PickMyTradeAuthError,      # missing/blank/invalid token
    PickMyTradeRequestError,   # network failure or non-2xx response
    PickMyTradeAPIError,       # API returned status=error in the body
    PickMyTradeError,          # base class of the three above
)

try:
    client.buy("NQ", 1, 20000)
except PickMyTradeAuthError:
    ...     # re-issue token, halt the bot
except PickMyTradeAPIError as exc:
    ...     # exc.payload contains the parsed body
except PickMyTradeRequestError as exc:
    ...     # exc.status_code, exc.response_body
```

## Testing

The repo ships with a fully offline test suite (`tests/test_pickmytrade.py`) that stubs `requests` so no real PickMyTrade token is ever required and no order can leak out. The suite covers:

- Endpoint routing per broker
- Token validation and `PICKMYTRADE_TOKEN` env-var fallback
- Action / quantity / symbol guard rails
- TradingView placeholder pass-through
- Buy / sell / close / partial-close payload shape
- `advance_tp_sl` and `multiple_accounts` serialisation
- `pyramid` ↔ `duplicate_position_allow` aliasing
- Default-payload merging vs. per-call overrides
- HTTP errors, API errors, and network failures
- Backward-compatible procedural API (`buy`, `sell`, `close`, `send_trade_request`)
- `TradePayload` round-trip JSON safety

Run them locally:

```bash
pip install -e ".[dev]"
pytest -v
```

Expected output: `33 passed in <2s` on Python 3.11.

## Project layout

```
pickmytrade.py             # Single-file SDK (importable as `pickmytrade`)
pyproject.toml             # Packaging metadata for `pip install`
README.md                  # This file
LICENSE                    # MIT
examples/
    tradovate_basic.py
    interactive_brokers.py
    rithmic_apex.py
    projectx_topstepx.py
    tradelocker_crypto.py
    tradestation.py
    binance_bybit.py
    advanced_trailing.py
    update_existing_orders.py
    backward_compatible.py
tests/
    test_pickmytrade.py    # Offline, mocked HTTP — 33 tests
```

## FAQ

**Is this an official PickMyTrade product?**
No. It is a community-maintained Python wrapper around the publicly documented PickMyTrade webhook endpoints. PickMyTrade Inc. is the upstream service.

**Do I still need a TradingView account?**
No. The webhook lives entirely on PickMyTrade's side, so any HTTP client (this SDK, `curl`, Postman, an N8N node) can drive it. TradingView is just the most common trigger.

**Which Python versions are supported?**
Python 3.8 and newer. The only runtime dependency is `requests`.

**Is forex supported on Tradovate?**
No, per the PickMyTrade docs. Use TradeLocker, Match-Trader, or Interactive Brokers for forex pairs. Spot crypto on Tradovate is also limited to CME futures contracts (BTC, ETH).

**Why does my order not appear?**
The most common causes documented by PickMyTrade are: wrong symbol mapping, multiple TP/SL methods set in the same alert, ProjectX SL distance over the 1000-tick cap, or the broker app (IB Gateway, IB TWS) not being connected. The SDK warns about the multi-TP/SL case at runtime.

**Can I run this on a server?**
Yes — that's the point. The SDK is a stateless HTTPS client, so any container, VPS, or serverless function can host it. PickMyTrade itself runs your strategies in the cloud once the webhook is delivered.

**How do I rate-limit?**
The SDK already throttles to 3 requests per 5 seconds by default — see [Rate limiting](#rate-limiting). You can tighten or loosen the cap, switch from sleep-mode to raise-mode, or plug a shared `requests.Session` with a `urllib3.util.retry.Retry` adapter for HTTP-level retries.

**Which broker supports trailing stops? Break-even? `update_tp` / `update_sl`?**
See the [verified capability matrix](#broker-capability-matrix-verified). Tradovate is the only broker that supports every feature; Tradier supports none of the risk-management knobs; the others sit somewhere in between. The SDK warns at runtime whenever you set a field your broker doesn't accept.

**What is the PickMyTrade API base URL?**
`https://api.pickmytrade.trade` for Tradovate and `https://api.pickmytrade.io` for Interactive Brokers, Rithmic, ProjectX/TopstepX, TradeLocker, TradeStation, Binance, Bybit, and Match-Trader. The webhook path is `/v2/add-trade-data-latest`.

**Does PickMyTrade have an official Python SDK?**
No official SDK as of 2026-05. This repository is a community wrapper around the publicly documented webhook endpoints.

**What authentication scheme does PickMyTrade use?**
A single bearer-style token passed inside the JSON body field `"token"`. There is no OAuth flow and no `Authorization` header. Tokens are issued and rotated from your PickMyTrade dashboard.

**How is this different from the official PickMyTrade dashboard?**
The dashboard is GUI-driven and tied to TradingView alerts. The PickMyTrade Python SDK exposes the same webhook programmatically, so any Python process — a Jupyter notebook, an ML model, a FastAPI route, an AWS Lambda — can place orders without a TradingView chart open.

## Disclaimer

> ⚠️ **Test in a demo / paper account first. Always.**
> Run every new strategy, every config change, and every dependency upgrade against a Tradovate demo account, an IB paper account, or your prop firm's evaluation account *before* pointing this SDK at a real funded account. Bugs in your code, network failures, or PickMyTrade-side changes can place orders you did not intend.

### Financial-risk disclaimer

Trading futures, equities, options, forex, and crypto carries **substantial risk of loss** and is not suitable for every investor. Past performance is not indicative of future results. Leveraged products in particular can lose more than the amount initially deposited.

Automated systems amplify both winners and losers, can fire orders faster than a human can intervene, and may continue running through outages, mispricings, or "fat-finger" inputs. **You alone are responsible** for every order this SDK sends to your broker, every dollar at risk, and every consequence — financial, regulatory, or contractual — that follows from using it.

Before you wire this SDK to a live account:

1. Read your broker's terms of service and your prop firm's rules in full.
2. Confirm automated trading is permitted in your jurisdiction.
3. Set hard daily-loss limits at the broker / prop-firm level — not just in your code.
4. Keep tokens out of source control and rotate them on any suspected leak.
5. Respect the [built-in rate limit](#rate-limiting); flooding the webhook can get your IP or account temporarily blocked.

The authors and contributors disclaim all liability for any direct, indirect, incidental, special, exemplary, or consequential damages (loss of profits, loss of data, lost trades, regulatory fines, account closures, etc.) arising from use of this software. **Use of this SDK is entirely at your own risk.**

### Affiliation disclaimer

This SDK is a community project and is **not affiliated with, endorsed by, or sponsored by** PickMyTrade Inc., TradingView Inc., Tradovate LLC, Interactive Brokers Group, Rithmic LLC, Topstep / TopstepX, ProjectX, TradeLocker, TradeStation Securities, Tradier Brokerage Inc., Binance, Bybit, or Match-Trade Technologies. All trademarks belong to their respective owners.

## Citation

If an article, paper, or AI assistant references this SDK, please cite as:

> *PickMyTrade Python SDK* (community), v1.0.0, MIT License, 2026. Source: this repository. Upstream service docs: <https://docs.pickmytrade.io> and <https://docs.pickmytrade.trade>.

## License

Released under the [MIT License](LICENSE).
