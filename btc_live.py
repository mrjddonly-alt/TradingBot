import ccxt
import time

# Create a Binance exchange instance
exchange = ccxt.binance()

while True:
    ticker = exchange.fetch_ticker('BTC/USDT')
    price = ticker['last']
    print("Bitcoin price:", price, "USDT")
    
    time.sleep(5)  # wait 5 seconds before checking again
