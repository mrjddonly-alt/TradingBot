import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os

# ==========================
# Config
# ==========================
SYMBOL = "USTEC"   # change to your symbol, e.g. "XAUUSD"
WEEK_CHOICE = 2    # 1, 2, 3, or 4

# October 2025 week ranges
WEEKS = {
    1: (pd.Timestamp("2025-10-06 00:00:00"), pd.Timestamp("2025-10-10 23:59:59")),
    2: (pd.Timestamp("2025-10-13 00:00:00"), pd.Timestamp("2025-10-17 23:59:59")),
    3: (pd.Timestamp("2025-10-20 00:00:00"), pd.Timestamp("2025-10-24 23:59:59")),
    4: (pd.Timestamp("2025-10-27 00:00:00"), pd.Timestamp("2025-10-31 23:59:59")),
}

# === Default parameters (baseline) ===
DEFAULT_PARAMS = {'TP_mult': 1.5, 'SL_mult': 1.0, 'ATR_min': 0.2, 'VWAP_tol': 0.0008, 'T_stop': 50}

# === High-win-rate parameter grid ===
PARAM_GRID = [
    {'TP_mult': tp, 'SL_mult': sl, 'ATR_min': atr, 'VWAP_tol': tol, 'T_stop': tstop}
    for tp in [0.3, 0.5, 0.7]          # smaller TP multipliers
    for sl in [2.0, 2.5, 3.0]          # wider SL multipliers
    for atr in [0.5, 0.8, 1.0]         # higher ATR filter
    for tol in [0.0003, 0.0005]        # stricter VWAP tolerance
    for tstop in [50, 100]
]

# ==========================
# Indicators
# ==========================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def atr(df, period=14):
    high_low   = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close  = np.abs(df['low']  - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_vwap(df):
    vol = np.where(df['real_volume'] == 0, df['tick_volume'], df['real_volume'])
    df['cum_vol'] = vol.cumsum()
    df['cum_pv']  = (df['close'] * vol).cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_vol']
    return df.drop(columns=['cum_vol','cum_pv'])
from TradingBot.regime_classifier import classify_regime

# ==========================
# Session filter (London + US overlap)
# ==========================
def apply_session_filter(df):
    df['hour'] = df['time'].dt.hour
    return df[(df['hour'] >= 14) & (df['hour'] <= 18)]

# ==========================
# Signal generation
# ==========================
def generate_signals(df, params):
    TP_mult   = params['TP_mult']
    SL_mult   = params['SL_mult']
    ATR_min   = params['ATR_min']
    VWAP_tol  = params['VWAP_tol']
    T_stop    = params['T_stop']

    trades = []
    start_idx = max(51, 14)

    for i in range(start_idx, len(df) - T_stop - 1):
        row  = df.iloc[i]
        prev = df.iloc[i-1]

        if np.isnan(row['atr']) or row['atr'] < ATR_min:
            continue

        # Long setup
        if (row['close'] > row['vwap']) and (row['ema20'] > row['ema50']):
            touch = abs(row['low'] - row['vwap']) <= (row['vwap'] * VWAP_tol)
            momentum_ok = row['close'] > prev['close']
            distance_ok = abs(row['close'] - row['ema20']) > 0.2 * row['atr']
            if touch and momentum_ok and distance_ok:
                entry = row['close']
                TP = entry + TP_mult * row['atr']
                SL = entry - SL_mult * row['atr']
                future = df.iloc[i+1:i+T_stop]
                hit_TP = (future['high'] >= TP).any()
                hit_SL = (future['low']  <= SL).any()
                if hit_TP and not hit_SL:
                    outcome, result = "TP", TP - entry
                elif hit_SL and not hit_TP:
                    outcome, result = "SL", SL - entry
                else:
                    outcome, result = "TIMEOUT", 0
                trades.append({
                    "timestamp_entry": row['time'],
                    "direction": "LONG",
                    "entry_price": entry,
                    "exit_price": entry + result,
                    "outcome": outcome,
                    "result_pips": result
                })

        # Short setup
        elif (row['close'] < row['vwap']) and (row['ema20'] < row['ema50']):
            touch = abs(row['high'] - row['vwap']) <= (row['vwap'] * VWAP_tol)
            momentum_ok = row['close'] < prev['close']
            distance_ok = abs(row['close'] - row['ema20']) > 0.2 * row['atr']
            if touch and momentum_ok and distance_ok:
                entry = row['close']
                TP = entry - TP_mult * row['atr']
                SL = entry + SL_mult * row['atr']
                future = df.iloc[i+1:i+T_stop]
                hit_TP = (future['low']  <= TP).any()
                hit_SL = (future['high'] >= SL).any()
                if hit_TP and not hit_SL:
                    outcome, result = "TP", entry - TP
                elif hit_SL and not hit_TP:
                    outcome, result = "SL", entry - SL
                else:
                    outcome, result = "TIMEOUT", 0
                trades.append({
                    "timestamp_entry": row['time'],
                    "direction": "SHORT",
                    "entry_price": entry,
                    "exit_price": entry - result,
                    "outcome": outcome,
                    "result_pips": result
                })

    return pd.DataFrame(trades)
# ==========================
# Backtest
# ==========================
def backtest(df, param_grid):
    results = []
    for params in param_grid:
        trades = generate_signals(df, params)
        if len(trades) == 0:
            continue
        num_trades = len(trades)
        wins  = (trades['result_pips'] > 0).sum()
        win_rate = wins / num_trades * 100 if num_trades else 0
        expectancy = trades['result_pips'].mean()
        pf = trades[trades['result_pips']>0]['result_pips'].sum() / \
             abs(trades[trades['result_pips']<0]['result_pips'].sum() + 1e-6)
        results.append({**params,
                        'num_trades': num_trades,
                        'win_rate': round(win_rate,2),
                        'expectancy': round(expectancy,3),
                        'profit_factor': round(pf,2)})
    return pd.DataFrame(results).sort_values(by='win_rate', ascending=False)

# ==========================
# Main
# ==========================
def load_mt5_data(symbol, week):
    START, END = WEEKS[week]
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1,
                                 START.to_pydatetime(), END.to_pydatetime())
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print(f"❌ No data for {symbol} in Week {week}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print(f"✅ Pulled {len(df)} rows for {symbol}, Week {week}")
    return df

    # === Compute indicators ===
    df['ema20'] = ema(df['close'], 20)
    df['ema50'] = ema(df['close'], 50)
    df['atr']   = atr(df, 14)
    df = compute_vwap(df)

    # === Classify regime ===
    df = classify_regime(df)

    # === Apply session filter ===
    df = apply_session_filter(df)

    # === Strategy: Trending regime ===
    df_trending = df[df['regime'] == 'trending']
    trades_trending = generate_signals(df_trending, DEFAULT_PARAMS)
    trades_trending['regime'] = 'trending'

    # === Strategy: Choppy regime (placeholder) ===
    df_choppy = df[df['regime'] == 'choppy']
    # trades_choppy = generate_choppy_signals(df_choppy, DEFAULT_PARAMS)
    # trades_choppy['regime'] = 'choppy'

    # === Combine trades (once choppy logic is active) ===
    # all_trades = pd.concat([trades_trending, trades_choppy])
    all_trades = trades_trending  # for now

    # === Regime summary ===
    regime_counts = df['regime'].value_counts()
    print("\n📊 Regime breakdown:")
    print(regime_counts)
    print(f"\n✅ Trades in trending regime: {len(trades_trending)}")
    print(f"✅ Rows labeled as choppy regime: {len(df_choppy)}")

    # === Backtest summary ===
    all_results = backtest(df, PARAM_GRID)
    print(f"\n✅ Trades generated (Week {WEEK_CHOICE}, default params): {len(all_trades)}")
    print(all_trades.head(10))

    print("\n🔎 Parameter sets with win rate >= 65%:")
    print(all_results[all_results['win_rate'] >= 65].head(10))

    # === Save outputs ===
    all_trades.to_csv(f"{SYMBOL}_Week{WEEK_CHOICE}_trades.csv", index=False)
    df.to_csv(f"{SYMBOL}_Week{WEEK_CHOICE}_data.csv", index=False)
    print(f"✅ Week {WEEK_CHOICE} trades and data saved for analysis.")