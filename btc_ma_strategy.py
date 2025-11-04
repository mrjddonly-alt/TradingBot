import ccxt
import time
import pandas as pd

# Connect to Binance
exchange = ccxt.binance()

# Settings
symbol = 'BTC/USDT'
timeframe = '1m'  # 1-minute candles
limit = 50  # Number of candles to fetch
fast_ma = 5  # Short MA period
slow_ma = 20  # Long MA period

def fetch_data():
    """Fetch OHLCV data and return as DataFrame."""
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

def calculate_signals(df):
    """Add moving averages and signals to DataFrame."""
    df['MA_Fast'] = df['close'].rolling(fast_ma).mean()
    df['MA_Slow'] = df['close'].rolling(slow_ma).mean()
    df['Signal'] = None

    if df['MA_Fast'].iloc[-1] > df['MA_Slow'].iloc[-1]:
        df['Signal'].iloc[-1] = 'BUY'
    elif df['MA_Fast'].iloc[-1] < df['MA_Slow'].iloc[-1]:
        df['Signal'].iloc[-1] = 'SELL'
    else:
        df['Signal'].iloc[-1] = 'HOLD'

    return df

def run_bot():
    print(f"Starting Moving Average Bot for {symbol}...\n")
    while True:
        df = fetch_data()
        df = calculate_signals(df)
        latest_price = df['close'].iloc[-1]
        latest_signal = df['Signal'].iloc[-1]
        print(f"Price: {latest_price} USDT | Signal: {latest_signal}")
        time.sleep(10)  # Wait 10 seconds before checking again

if __name__ == "__main__":
    run_bot()
