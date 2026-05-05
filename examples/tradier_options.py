"""Tradier example - stocks + stock options.

Per the verified capability matrix, Tradier supports STK and OPT
instrument types but does NOT support trailing stops, break-even,
``update_tp`` / ``update_sl``, or ``advance_tp_sl`` via PickMyTrade.
Stick to plain SL/TP and (optionally) percentage-based risk.
"""

import os
from pickmytrade import PickMyTradeClient, Broker


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.TRADIER,
        account_id="VA00000000",
    )

    # Buy 50 shares of AAPL with a percentage-based stop and target.
    print(client.buy(
        symbol="AAPL",
        quantity=50,
        price=185.50,
        percentage_sl=1.0,
        percentage_tp=2.5,
    ))

    # Sell 1 SPY put-side option position (close).
    print(client.close(symbol="SPY240621P00500000", quantity=1, price=2.50))


if __name__ == "__main__":
    main()
