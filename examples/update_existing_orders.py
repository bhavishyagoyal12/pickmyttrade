"""Modify a working stop-loss / take-profit on Tradovate.

Per the official docs (https://docs.pickmytrade.trade/docs/update-sl-tp-tradovate-pickmytrade/):

    "SL and TP will be updated with the exact values you pass in the alert."
    "We do not calculate in points, dollar_tp, or dollar_sl."
    "If you have multiple open positions ... using `update_sl: true` or
     `update_tp: true` will overwrite and apply the new SL/TP values to
     all positions for that symbol."

That makes ``update_tp`` / ``update_sl``:
    1. Tradovate-only — the SDK warns on any other broker.
    2. Driven by the EXACT PRICE you pass (not a distance in points).
    3. Symbol-wide — every open position on that symbol is modified.
"""

import os
from pickmytrade import PickMyTradeClient, Broker


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.TRADOVATE,
        account_id="DEMO12345",
    )

    # Pull the stop in to price 19990 (exact SL price, not a point distance).
    print(client.update_stop_loss(symbol="NQ", sl=19990))

    # Push the take-profit out to price 20100 (exact TP price level).
    print(client.update_take_profit(symbol="NQ", tp=20100))


if __name__ == "__main__":
    main()
