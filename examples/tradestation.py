"""TradeStation example covering stocks, futures, and stock options.

Per the verified capability matrix, TradeStation supports
``trail`` + ``trail_stop`` (no trail_trigger / trail_freq) and options
(STOCKS, FUTURES, OPTIONS instrument types). It does NOT support
``breakeven``, ``update_tp`` / ``update_sl``, or ``advance_tp_sl``.
"""

import os
from pickmytrade import PickMyTradeClient, Broker


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.TRADESTATION,
        account_id="TS-12345678",
    )

    # Buy 10 shares of MSFT at market with $25 stop and $75 target.
    print(client.buy(
        symbol="MSFT",
        quantity=10,
        price=420.0,
        dollar_sl=25,
        dollar_tp=75,
    ))

    # Sell 1 ES futures contract with a 5-pt stop and a trail.
    print(client.sell(
        symbol="ES",
        quantity=1,
        price=5050.0,
        dollar_sl=5,
        trail=1,
        trail_stop=3,
    ))


if __name__ == "__main__":
    main()
