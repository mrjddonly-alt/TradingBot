import pandas as pd
import matplotlib.pyplot as plt
import ccxt
import datetime

# Parameters
SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"  # 1-hour candles
LIMIT = 500  # number of candles
SHORT_MA = 9
LONG_MA = 21

# Connect to Binance (no API key needed for historical data)
exchange = ccxt.binance()

def fetch_data(symbol, timeframe, limit):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

def backtest(df):
    # Calculate moving averages
    df['SMA_Short'] = df['close'].rolling(SHORT_MA).mean()
    df['SMA_Long'] = df['close'].rolling(LONG_MA).mean()

    # Generate signals
    df['Signal'] = 0
    df.loc[df['SMA_Short'] > df['SMA_Long'], 'Signal'] = 1
    df.loc[df['SMA_Short'] < df['SMA_Long'], 'Signal'] = -1

    # Calculate returns
    df['Return'] = df['close'].pct_change()
    df['Strategy'] = df['Signal'].shift(1) * df['Return']
    df['Cumulative'] = (1 + df['Strategy']).cumprod()

    return df

def plot_backtest(df):
    plt.figure(figsize=(14, 7))
    plt.plot(df['time'], df['close'], label='Price', alpha=0.5)
    plt.plot(df['time'], df['SMA_Short'], label=f'SMA {SHORT_MA}')
    plt.plot(df['time'], df['SMA_Long'], label=f'SMA {LONG_MA}')
    plt.plot(df['time'], df['Cumulative'] * df['close'].iloc[0], label='Strategy Equity', color='green')
    plt.legend()
    plt.title(f'{SYMBOL} Backtest (MA {SHORT_MA}/{LONG_MA})')
    plt.show()

if __name__ == "__main__":
    print("Fetching data...")
    data = fetch_data(SYMBOL, TIMEFRAME, LIMIT)
    print("Running backtest...")
    result = backtest(data)
    print(f"Final Strategy Return: {(result['Cumulative'].iloc[-1]-1)*100:.2f}%")
    plot_backtest(result)
