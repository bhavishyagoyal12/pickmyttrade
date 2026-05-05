"""Crypto exchange example for Binance and Bybit.

Per the verified capability matrix, Binance and Bybit accept ``trail`` +
``trail_stop`` (no trail_trigger / trail_freq), no break-even, no
``update_tp`` / ``update_sl``, no ``advance_tp_sl``. Allowed instrument
types are CRYPTO and FUTURE / FUTURES.
"""

import os
from pickmytrade import PickMyTradeClient, Broker


def main() -> None:
    binance = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.BINANCE,
        account_id="BIN-MAIN",
    )
    bybit = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.BYBIT,
        account_id="BB-MAIN",
    )

    # Long 0.01 BTC on Binance with a 1% stop.
    print(binance.buy(
        symbol="BTCUSDT",
        quantity=0.01,
        price=68000.0,
        percentage_sl=1.0,
        percentage_tp=2.0,
    ))

    # Short 0.1 ETH on Bybit perp with a fixed-dollar stop and trail.
    print(bybit.sell(
        symbol="ETHUSDT",
        quantity=0.1,
        price=3500.0,
        dollar_sl=10,
        dollar_tp=30,
        trail=1,
        trail_stop=5,
    ))


if __name__ == "__main__":
    main()
