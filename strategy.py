import MetaTrader5 as mt5
import pandas as pd
from trade_executor import TradeExecutor

SYMBOL = "GBPUSD"
TIMEFRAME = mt5.TIMEFRAME_M1
BARS = 500
RISK_REWARD = 2  # 1:2 RR
LOT_SIZE = 0.1

def get_data(symbol, timeframe, bars):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def find_swing_points(df, lookback=5):
    df['swing_high'] = df['high'].rolling(lookback, center=True).max()
    df['swing_low'] = df['low'].rolling(lookback, center=True).min()
    return df

def identify_zone(df):
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    # If price broke above a swing high => demand zone
    if last_row['close'] > prev_row['swing_high']:
        return 'demand', prev_row['low']
    # If price broke below a swing low => supply zone
    elif last_row['close'] < prev_row['swing_low']:
        return 'supply', prev_row['high']
    return None, None

def check_entry(df, zone_type, zone_price):
    last_price = df.iloc[-1]['close']
    if zone_type == 'demand' and last_price <= zone_price:
        return "buy"
    elif zone_type == 'supply' and last_price >= zone_price:
        return "sell"
    return None

def run_strategy():
    if not mt5.initialize():
        print("❌ MT5 init failed:", mt5.last_error())
        return

    df = get_data(SYMBOL, TIMEFRAME, BARS)
    df = find_swing_points(df)

    zone_type, zone_price = identify_zone(df)
    if not zone_type:
        print("ℹ️ No setup found.")
        mt5.shutdown()
        return

    signal = check_entry(df, zone_type, zone_price)
    if not signal:
        print("ℹ️ No entry signal.")
        mt5.shutdown()
        return

    print(f"✅ {signal.upper()} signal triggered at {zone_price}")

    # Place trade
    executor = TradeExecutor(SYMBOL, lot=LOT_SIZE, sl_points=200, tp_points=400)
    executor.place_order(order_type=signal)

    mt5.shutdown()

if __name__ == "__main__":
    run_strategy()
