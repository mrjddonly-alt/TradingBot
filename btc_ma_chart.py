import ccxt
import time
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Connect to Binance
exchange = ccxt.binance()

# Settings
symbol = 'BTC/USDT'
timeframe = '1m'  # 1-minute candles
limit = 50  # Number of candles to fetch
fast_ma = 5
slow_ma = 20

def fetch_data():
    """Fetch OHLCV data and return DataFrame."""
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

def animate(i):
    """Update chart every interval."""
    df = fetch_data()
    df['MA_Fast'] = df['close'].rolling(fast_ma).mean()
    df['MA_Slow'] = df['close'].rolling(slow_ma).mean()

    plt.cla()
    plt.plot(df['time'], df['close'], label='Price', color='black')
    plt.plot(df['time'], df['MA_Fast'], label=f'{fast_ma}-MA', color='blue')
    plt.plot(df['time'], df['MA_Slow'], label=f'{slow_ma}-MA', color='red')
    plt.title(f'{symbol} Moving Averages')
    plt.xlabel('Time')
    plt.ylabel('Price (USDT)')
    plt.legend()
    plt.tight_layout()

def run_chart():
    print(f"📊 Starting live chart for {symbol}...\n")
    ani = FuncAnimation(plt.gcf(), animate, interval=10000)  # Refresh every 10s
    plt.show()

if __name__ == "__main__":
    run_chart()
