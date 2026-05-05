"""TradeLocker example covering crypto and forex symbol notation.

TradeLocker reads available symbols from the connected account. Crypto is
suffixed ``.X`` (e.g. ``BTCUSD.X``); spot forex uses the same suffix
(e.g. ``EURUSD.X``).

Per the verified capability matrix, TradeLocker supports
``trail`` + ``trail_stop`` (no trail_trigger / trail_freq), no break-even,
no in-place SL/TP modification, and no multi-leg ``advance_tp_sl``.
"""

import os
from pickmytrade import PickMyTradeClient, Broker


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.TRADELOCKER,
        account_id="TL-1001",
    )

    # Long 0.05 BTC at market with a 1% / 2% percentage SL/TP.
    print(client.buy(
        symbol="BTCUSD.X",
        quantity=0.05,
        price=68000.0,
        percentage_sl=1.0,
        percentage_tp=2.0,
    ))

    # Sell 1 mini lot of EUR/USD with a points-based SL/TP.
    print(client.sell(
        symbol="EURUSD.X",
        quantity=10000,
        price=1.0850,
        dollar_sl=20,             # 20 points/pips of risk
        dollar_tp=40,             # 40 points/pips target
        trail=1,                  # arm trailing stop
        trail_stop=15,            # trail 15 points behind price
    ))


if __name__ == "__main__":
    main()
