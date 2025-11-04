import ccxt
import time

# Create a Binance exchange instance
exchange = ccxt.binance()

# Set the percentage change for alerts
ALERT_CHANGE = 2  # alert if price changes by 2%

# Get the starting price
last_price = exchange.fetch_ticker('BTC/USDT')['last']
print(f"Starting price: {last_price} USDT")

while True:
    ticker = exchange.fetch_ticker('BTC/USDT')
    price = ticker['last']
    change = ((price - last_price) / last_price) * 100
    
    print(f"Bitcoin price: {price} USDT | Change: {change:.2f}%")
    
    # Check if price moved more than ALERT_CHANGE%
    if abs(change) >= ALERT_CHANGE:
        print("🚨 ALERT: Bitcoin price moved more than 2%! 🚨")
        last_price = price  # reset baseline price
    
    time.sleep(5)  # wait 5 seconds
