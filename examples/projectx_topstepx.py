"""ProjectX / TopstepX example.

Per the PickMyTrade docs, ProjectX caps the maximum stop-loss distance at
1000 ticks. Manual market orders directly from TradingView are not
supported; trigger them from your own Python code instead.

Per the verified capability matrix
(https://github.com/bhavishyagoyal12/pickmytrade_validation), ProjectX /
TopstepX accepts ``trail`` (the actual trailing distance is configured in
the ProjectX dashboard, not via JSON), and does NOT honour ``trail_stop``,
``trail_trigger``, ``trail_freq``, ``breakeven``, ``update_tp``,
``update_sl``, or ``advance_tp_sl``. Stick to plain SL/TP plus the
broker-side auto-trailing.
"""

import os
from pickmytrade import PickMyTradeClient, Broker


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.TOPSTEPX,
        account_id="TOPSTEP-12345",
    )

    # Long MNQ with OCO bracket: 40-tick TP, 20-tick SL.
    print(client.buy(
        symbol="MNQ",
        quantity=2,
        price=20000.00,
        dollar_tp=40,             # 40 ticks/points to target
        dollar_sl=20,             # 20 ticks/points to stop
    ))

    # Auto-trailing example - the actual trail distance is set in the
    # ProjectX dashboard; PickMyTrade only needs `trail=1` to enable it.
    print(client.buy(
        symbol="MES",
        quantity=1,
        price=5000.00,
        dollar_sl=20,
        trail=1,
    ))


if __name__ == "__main__":
    main()
