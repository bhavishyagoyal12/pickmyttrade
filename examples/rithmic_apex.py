"""Rithmic example for prop-firm accounts (Apex / Bulenox / Earn2Trade).

PickMyTrade supports unlimited Rithmic accounts under a single login on
one subscription. Pass the Rithmic account id you want to trade; the
``multiple_accounts`` field can fan a single signal out to many of them.

Per the verified capability matrix
(https://github.com/bhavishyagoyal12/pickmytrade_validation), Rithmic
supports trailing via ``trail`` + ``trail_trigger`` (no ``trail_stop`` or
``trail_freq``), no break-even, no in-place SL/TP modification, and no
multi-leg ``advance_tp_sl``.

Multi-account schema (verified against the upstream validator) requires
each entry to carry ``account_id``, ``connection_name``, ``token``, and
either ``risk_percentage`` or ``quantity_multiplier`` matching the
top-level alert's sizing mode.
"""

import os
from pickmytrade import PickMyTradeClient, Broker, MultiAccountEntry


def main() -> None:
    primary_token = os.environ["PICKMYTRADE_TOKEN"]
    client = PickMyTradeClient(
        token=primary_token,
        broker=Broker.RITHMIC,
        account_id="APEX-12345",  # primary Rithmic account
    )

    # Single-account market buy with a percentage-based SL.
    print(client.buy(
        symbol="NQM5",            # Rithmic uses month-coded symbols
        quantity=2,
        price=20000.00,
        percentage_sl=0.5,        # 0.5% of price
        percentage_tp=1.0,        # 1.0% of price
    ))

    # Same signal mirrored across three Apex accounts at different sizes,
    # using the points-from-entry SL/TP form (dollar_sl / dollar_tp).
    # Top-level uses `quantity`, so every sub-account must use
    # `quantity_multiplier` (the validator enforces sizing-mode parity).
    print(client.sell(
        symbol="NQM5",
        quantity=1,
        price=20020.00,
        dollar_sl=10,             # 10-point stop
        dollar_tp=20,             # 20-point target
        multiple_accounts=[
            MultiAccountEntry(
                account_id="APEX-12345",
                connection_name="RITHMIC1",
                token=primary_token,
                quantity_multiplier=1,
            ),
            MultiAccountEntry(
                account_id="APEX-67890",
                connection_name="RITHMIC2",
                token=primary_token,
                quantity_multiplier=2,
            ),
            MultiAccountEntry(
                account_id="BULENOX-11",
                connection_name="BULENOX1",
                token=primary_token,
                quantity_multiplier=1,
            ),
        ],
    ))


if __name__ == "__main__":
    main()
