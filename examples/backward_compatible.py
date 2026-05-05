"""Backward-compatible call style preserved from the original sample.

If you started with the very first version of pickmytrade.py shipped in
this repo, your existing code keeps working unchanged.
"""

import os
from pickmytrade import buy, sell, close

TOKEN = os.environ["PICKMYTRADE_TOKEN"]

print(buy("AAPL", 3, 150.00, TOKEN, account_id=""))
print(sell("AAPL", 3, 151.00, TOKEN, account_id=""))
print(close("AAPL", 3, 150.50, TOKEN, account_id=""))
