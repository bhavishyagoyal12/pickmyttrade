import requests
import datetime

# Tradovate Automation for Prop firm Trading
# Tradovate Automation for Apex Automation
# Tradovate Demo account Trading
# Tradovate Live Trading
# Tradovate Algo Trading


# Function to send trade data
def send_trade_request(symbol, data, quantity, price, token, account_id=""):
    url = "https://pickmytrade.trade/api/add-trade-data"
    timenow = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "symbol": symbol,
        "date": timenow,
        "data": data,
        "quantity": quantity,
        "risk_percentage": 0,
        "price": price,  # Pass the actual close price here
        "tp": 0,
        "sl": 0,
        "trail": 0,
        "update_tp": False,
        "update_sl": False,
        "duplicate_position_allow": True,
        "reverse_order_close": True,
        "token": token,
        "account_id": account_id
    }

    response = requests.post(url, json=payload)
    return response.json()

# Method to execute a buy order
def buy(symbol, quantity, price, token, account_id=""):
    return send_trade_request(symbol, "buy", quantity, price, token, account_id)

# Method to execute a sell order
def sell(symbol, quantity, price, token, account_id=""):
    return send_trade_request(symbol, "sell", quantity, price, token, account_id)

# Method to close a position
def close(symbol, quantity, price, token, account_id=""):
    return send_trade_request(symbol, "close", quantity, price, token, account_id)

# Example usage of the methods
if __name__ == "__main__":
    # These are example values, replace them with actual values
    symbol = "AAPL"
    quantity = 3
    price = 150.00  # Example close price, replace with actual price
    token = "fkjf" ## Pass your Pickmytrade Token 
    account_id = ""  # Optional, add if available

    # Tradovate Automation: Buy order
    buy_response = buy(symbol, quantity, price, token, account_id)
    print("Buy Response:", buy_response)

    # Tradovate Automation: Sell order
    sell_response = sell(symbol, quantity, price, token, account_id)
    print("Sell Response:", sell_response)

    # Tradovate Automation: Close position
    close_response = close(symbol, quantity, price, token, account_id)
    print("Close Response:", close_response)

