"""Basic Tradovate buy / sell / close example.

Tradovate is the only broker that uses the ``api.pickmytrade.trade`` host;
every other broker uses ``api.pickmytrade.io``. The SDK picks the right URL
automatically when you set ``broker=Broker.TRADOVATE``.

Set your token first:

    export PICKMYTRADE_TOKEN="your-real-token"
"""

import os
from pickmytrade import PickMyTradeClient, Broker, OrderType


def main() -> None:
    client = PickMyTradeClient(
        token=os.environ["PICKMYTRADE_TOKEN"],
        broker=Broker.TRADOVATE,
        account_id="DEMO12345",          # your Tradovate account id, e.g. "DEMO12345"
        default_payload={"order_type": OrderType.MARKET.value},
    )

    # Plain market buy of 1 NQ contract.
    print(client.buy(symbol="NQ", quantity=1, price=20000.25))

    # Market sell with a 10-point stop and 20-point take profit
    # (dollar_sl / dollar_tp = distance in points/dollars from entry).
    print(client.sell(symbol="NQ", quantity=1, price=20010.00,
                      dollar_sl=10, dollar_tp=20))

    # Close the open NQ position.
    print(client.close(symbol="NQ", quantity=1, price=20005.00))


if __name__ == "__main__":
    main()
