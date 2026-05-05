"""Interactive Brokers (IB) example.

Per the PickMyTrade docs, IB orders are routed through the multi-broker
endpoint and require:

    * TWS or IB Gateway running locally (default port 7497 / 4001)
    * The PickMyTrade IB App connected to that TWS/Gateway
    * Your IB *username* (not account number) on file in PickMyTrade

Per the verified broker capability matrix
(https://github.com/bhavishyagoyal12/pickmytrade_validation), IB supports
trailing stops with `trail` + `trail_stop`, plus `breakeven`. It does NOT
honour `trail_trigger`, `trail_freq`, `update_tp`, `update_sl`, or
`advance_tp_sl` — the SDK warns at runtime if you set any of those.
"""

import os
from pickmytrade import PickMyTradeClient, Broker


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.INTERACTIVE_BROKERS,
        account_id="U1234567",  # your IB account id
    )

    # Long 100 shares of AAPL with $50 risk and $150 target.
    # dollar_sl / dollar_tp = distance in points/dollars from entry.
    print(client.buy(
        symbol="AAPL",
        quantity=100,
        price=185.50,
        dollar_sl=50,
        dollar_tp=150,
    ))

    # Short 1 ES futures contract with a 5-point stop and a trailing stop
    # that maintains 3 points behind price. (trail_trigger / trail_freq
    # are NOT supported by IB and are intentionally omitted.)
    print(client.sell(
        symbol="ES",
        quantity=1,
        price=5050.25,
        dollar_sl=5,
        trail=1,
        trail_stop=3,
        breakeven=2,   # IB supports auto-breakeven; SDK won't warn
    ))


if __name__ == "__main__":
    main()
