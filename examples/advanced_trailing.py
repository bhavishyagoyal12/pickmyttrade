"""Advanced exits on Tradovate: trailing stop, break-even, multi-leg TPs.

Per the verified capability matrix
(https://github.com/bhavishyagoyal12/pickmytrade_validation), Tradovate is
the only broker that supports the full risk-management toolkit:
``trail`` + ``trail_stop`` + ``trail_trigger`` + ``trail_freq``,
``breakeven``, ``update_tp`` / ``update_sl``, AND ``advance_tp_sl``. The
example below uses every one of them together. Run it on any other broker
and the SDK will emit warnings for the unsupported fields.
"""

import os
from pickmytrade import PickMyTradeClient, Broker, AdvancedTPSL


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.TRADOVATE,
        account_id="DEMO12345",
    )

    # 3-contract NQ entry: take profit on 1c at +10pts, 1c at +20pts,
    # leave 1c running on a trailing stop. Move SL to break-even after
    # the first leg fills.
    print(client.buy(
        symbol="NQ",
        quantity=3,
        price=20000.0,
        dollar_sl=10,                          # initial 10-pt protective stop
        breakeven=10,                          # move to BE after +10 pts
        trail=1,
        trail_trigger=20,
        trail_stop=8,
        trail_freq=2,
        advance_tp_sl=[
            AdvancedTPSL(quantity=1, dollar_tp=10, dollar_sl=10, breakeven=0),
            AdvancedTPSL(quantity=1, dollar_tp=20, dollar_sl=10, breakeven=10),
            AdvancedTPSL(quantity=1, dollar_tp=0,  dollar_sl=10, breakeven=20),
        ],
    ))


if __name__ == "__main__":
    main()
