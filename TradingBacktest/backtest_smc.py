"""
Backtester for two SMC bot variants
- Reads M15 and M1 CSV files (expected columns: time/datetime or any timestamp column, open, high, low, close)
- Simulates:
  - Bot A: original logic (no swing filter, places trades when zone+price conditions met)
  - Bot B: improved logic (one-trade-at-a-time + swing-high/low broken filter)
- Uses last 480 M15 bars (~5 trading days) by default
- Outputs trade logs and summary statistics to CSV and console
"""

import pandas as pd
import numpy as np
from datetime import timedelta
import os

# --------------------
# CONFIG
# --------------------
M15_CSV = "M15.csv"
M1_CSV = "M1.csv"
SYMBOL = "GBPUSD"
LOT = 0.1
SL_PIPS = 15
TP_PIPS = 30
CONTRACT_SIZE = 100000
OUTPUT_DIR = "backtest_output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------
# Helpers
# --------------------
def load_csv(filename):
    df = pd.read_csv(filename)

    # Try to automatically find a timestamp column
    time_col = None
    for c in df.columns:
        c_lower = c.lower()
        if 'time' in c_lower or 'date' in c_lower or 'datetime' in c_lower:
            time_col = c
            break

    if time_col is None:
        # If no suitable column is found, pick the first column of type object
        for c in df.columns:
            if df[c].dtype == object:
                time_col = c
                break

    if time_col is None:
        raise ValueError(f"No timestamp column found in {filename}. Please check your CSV.")

    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)
    df.rename(columns={time_col: 'time'}, inplace=True)
    return df

def pip_value(symbol):
    return 0.01 if symbol.endswith('JPY') else 0.0001

# simplified SMC detection used by both bots
def detect_smc_from_m15(m15_df_row, m15_window):
    if len(m15_window) < 3:
        return None
    highs = m15_window['high'].values
    lows = m15_window['low'].values
    last = m15_window.iloc[-1]

    lb_zone = None
    lb_signal = None
    ob_zone = None
    ob_signal = None

    prev_high = highs[:-1].max()
    prev_low = lows[:-1].min()
    if last['high'] > prev_high:
        lb_zone, lb_signal = (prev_high, last['high']), 'sell'
    elif last['low'] < prev_low:
        lb_zone, lb_signal = (last['low'], prev_low), 'buy'

    for i in range(len(m15_window)-2, -1, -1):
        c = m15_window.iloc[i]
        cnext = m15_window.iloc[i+1]
        if c['close'] < c['open'] and cnext['close'] > cnext['open']:
            ob_zone, ob_signal = (c['low'], c['high']), 'buy'
            break
        if c['close'] > c['open'] and cnext['close'] < cnext['open']:
            ob_zone, ob_signal = (c['low'], c['high']), 'sell'
            break

    signal = lb_signal or ob_signal
    return {
        'signal': signal,
        'fvg': None,
        'liquidity_grab': lb_zone,
        'order_block': ob_zone
    }

def find_last_swing_high_low(m15_window):
    highs = m15_window['high'].values
    lows = m15_window['low'].values
    pivot_high = None
    pivot_low = None
    for i in range(len(m15_window)-2, 1, -1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            pivot_high = highs[i]
            break
    for i in range(len(m15_window)-2, 1, -1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            pivot_low = lows[i]
            break
    return pivot_high, pivot_low

# --------------------
# Simulator core
# --------------------
def run_backtest(m15_df, m1_df, strategy='original'):
    m15_slice = m15_df.tail(480).reset_index(drop=True)
    m1_slice = m1_df[m1_df['time'] >= m15_slice['time'].iloc[0]].reset_index(drop=True)

    trades = []
    open_trade = None
    last_trade_time = pd.Timestamp(0)

    pv = pip_value(SYMBOL)

    for idx in range(len(m15_slice)):
        m15_bar = m15_slice.iloc[idx]
        window_start_idx = max(0, idx-50)
        m15_window = m15_slice.iloc[window_start_idx:idx+1]

        zones = detect_smc_from_m15(m15_bar, m15_window)
        signal = zones['signal']

        pivot_h, pivot_l = find_last_swing_high_low(m15_window)
        last_m15_close = m15_window['close'].iloc[-1]
        broken = None
        if pivot_h is not None and last_m15_close > pivot_h:
            broken = 'buy'
        if pivot_l is not None and last_m15_close < pivot_l:
            broken = 'sell'

        m1_start = m15_bar['time']
        m1_end = m1_start + pd.Timedelta(minutes=15)
        m1_bars = m1_slice[(m1_slice['time'] >= m1_start) & (m1_slice['time'] < m1_end)].reset_index(drop=True)

        for j in range(len(m1_bars)):
            row = m1_bars.iloc[j]
            if strategy == 'original':
                can_enter = signal is not None
            else:
                if signal is None or broken is None or signal != broken:
                    can_enter = False
                else:
                    can_enter = open_trade is None

            if can_enter and signal is not None:
                zones_list = [zones['fvg'], zones['order_block'], zones['liquidity_grab']]
                price = row['close']
                hit_zone = False
                for z in zones_list:
                    if z is None:
                        continue
                    lo, hi = min(z), max(z)
                    if row['low'] <= hi and row['high'] >= lo:
                        hit_zone = True
                        break
                if hit_zone:
                    if signal == 'buy' and row['close'] > row['open']:
                        entry_price = row['close']
                    elif signal == 'sell' and row['close'] < row['open']:
                        entry_price = row['close']
                    else:
                        continue

                    sl = entry_price - SL_PIPS * pv if signal == 'buy' else entry_price + SL_PIPS * pv
                    tp = entry_price + TP_PIPS * pv if signal == 'buy' else entry_price - TP_PIPS * pv
                    open_trade = {
                        'entry_time': row['time'],
                        'entry_price': entry_price,
                        'side': signal,
                        'sl': sl,
                        'tp': tp,
                        'm1_index': j,
                        'm15_index': idx
                    }
                    last_trade_time = row['time']

            if open_trade is not None:
                ot = open_trade
                if ot['side'] == 'buy':
                    if row['high'] >= ot['tp']:
                        exit_price = ot['tp']
                        result = 'win'
                    elif row['low'] <= ot['sl']:
                        exit_price = ot['sl']
                        result = 'loss'
                    else:
                        continue
                    profit = (exit_price - ot['entry_price']) * LOT * CONTRACT_SIZE
                else:
                    if row['low'] <= ot['tp']:
                        exit_price = ot['tp']
                        result = 'win'
                    elif row['high'] >= ot['sl']:
                        exit_price = ot['sl']
                        result = 'loss'
                    else:
                        continue
                    profit = (ot['entry_price'] - exit_price) * LOT * CONTRACT_SIZE

                trade_record = {
                    'entry_time': ot['entry_time'],
                    'exit_time': row['time'],
                    'side': ot['side'],
                    'entry': ot['entry_price'],
                    'exit': exit_price,
                    'sl': ot['sl'],
                    'tp': ot['tp'],
                    'result': result,
                    'profit': profit
                }
                trades.append(trade_record)
                open_trade = None

    trades_df = pd.DataFrame(trades)
    return trades_df

# --------------------
# Summarize results
# --------------------
def summarize(trades_df):
    if trades_df.empty:
        return {}
    total = trades_df['profit'].sum()
    wins = trades_df[trades_df['profit'] > 0]
    losses = trades_df[trades_df['profit'] <= 0]
    winrate = len(wins) / len(trades_df) if len(trades_df) else 0
    equity = trades_df['profit'].cumsum()
    peak = equity.cummax()
    dd = (equity - peak).min()
    return {
        'trades': len(trades_df),
        'net_profit': total,
        'winrate': winrate,
        'max_drawdown': dd
    }

# --------------------
# Main
# --------------------
def main():
    m15 = load_csv(M15_CSV)
    m1 = load_csv(M1_CSV)

    print("Running backtest for last 5 days (approx 480 M15 bars)...")

    trades_a = run_backtest(m15, m1, strategy='original')
    trades_b = run_backtest(m15, m1, strategy='improved')

    trades_a.to_csv(os.path.join(OUTPUT_DIR, 'trades_original.csv'), index=False)
    trades_b.to_csv(os.path.join(OUTPUT_DIR, 'trades_improved.csv'), index=False)

    sum_a = summarize(trades_a)
    sum_b = summarize(trades_b)

    print("\n=== Original Strategy ===")
    print(sum_a)
    print("\n=== Improved Strategy ===")
    print(sum_b)

    pd.DataFrame([sum_a]).to_csv(os.path.join(OUTPUT_DIR, 'summary_original.csv'), index=False)
    pd.DataFrame([sum_b]).to_csv(os.path.join(OUTPUT_DIR, 'summary_improved.csv'), index=False)

    print(f"\nResults saved to {OUTPUT_DIR}")

if __name__ == '__main__':
    main()
