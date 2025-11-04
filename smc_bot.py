"""
Smart Money Concepts (SMC) Backtest Bot
Backtests GBPUSD with M15 analysis and M1 confirmation
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta


# --- SETTINGS ---
SYMBOL = "GBPUSD"
DAYS_BACK = 5                     # Always backtest last 5 days
MAX_TRADES = 5                    # Max concurrent trades
RR = 2                            # Risk:Reward ratio


# --- CONNECT TO MT5 ---
if not mt5.initialize():
    print("Failed to connect to MT5")
    quit()
print(f"Connected to MT5, version: {mt5.version()}")


# --- HELPER: GET LAST X DAYS OF DATA (up to broker's last candle) ---
def get_data(symbol, timeframe, days_back):
    # Ensure symbol is loaded
    mt5.symbol_select(symbol, True)

    # Get broker's last tick to know latest candle time
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Could not get tick data for {symbol}")
        return pd.DataFrame()

    end = datetime.fromtimestamp(tick.time)   # broker's last candle time
    start = end - timedelta(days=days_back)

    # Fetch candles between start and end
    rates = mt5.copy_rates_range(symbol, timeframe, start, end)
    if rates is None or len(rates) == 0:
        print(f"No data for {symbol} {timeframe}, fallback to bars...")
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 5000)

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


# --- LOAD DATA ---
df_15m = get_data(SYMBOL, mt5.TIMEFRAME_M15, DAYS_BACK)
df_1m = get_data(SYMBOL, mt5.TIMEFRAME_M1, DAYS_BACK)

print(f"Downloaded {len(df_15m)} candles for {SYMBOL} (15M)")
print(f"Downloaded {len(df_1m)} candles for {SYMBOL} (1M)")
if not df_15m.empty:
    print(f"15M Data range: {df_15m['time'].iloc[0]} → {df_15m['time'].iloc[-1]}")
if not df_1m.empty:
    print(f"1M Data range: {df_1m['time'].iloc[0]} → {df_1m['time'].iloc[-1]}")


# --- SIMPLE BOS DETECTION (PLACEHOLDER) ---
def detect_bos(df):
    signals = []
    for i in range(2, len(df)):
        if df['close'].iloc[i] > df['high'].iloc[i - 2]:  # Break of structure (bullish)
            signals.append((df['time'].iloc[i], "BUY"))
        elif df['close'].iloc[i] < df['low'].iloc[i - 2]:  # Break of structure (bearish)
            signals.append((df['time'].iloc[i], "SELL"))
    return signals


# --- DETECT SIGNALS ON 15M ---
signals_15m = detect_bos(df_15m)


# --- CONFIRM ON 1M ---
trades = []
for signal_time, direction in signals_15m:
    confirm = df_1m[df_1m['time'] >= signal_time]

    if not confirm.empty:
        entry_time = confirm.iloc[0]['time']
        trades.append({
            "time": entry_time,
            "direction": direction
        })
        print(f"Trade detected! {direction} at {entry_time} "
              f"(from 15M BoS at {signal_time})")

    if len(trades) >= MAX_TRADES:
        print("Max concurrent trades reached, stopping entries.")
        break


# --- RESULTS ---
print(f"\nTotal confirmed trades: {len(trades)}")


# --- SHUTDOWN MT5 ---
mt5.shutdown()
