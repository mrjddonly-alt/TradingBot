import pandas as pd
import numpy as np
from itertools import product
import os

# ==========================
# Config
# ==========================
FILE = "C:/Users/mrjdd/OneDrive/Desktop/TradingBot/USTEC_1min.csv"

# Choose which week to test: 1, 2, 3, or 4
WEEK_CHOICE = 1

# October 2025 week ranges
WEEKS = {
    1: (pd.Timestamp("2025-10-06 00:00:00"), pd.Timestamp("2025-10-10 23:59:59")),
    2: (pd.Timestamp("2025-10-13 00:00:00"), pd.Timestamp("2025-10-17 23:59:59")),
    3: (pd.Timestamp("2025-10-20 00:00:00"), pd.Timestamp("2025-10-24 23:59:59")),
    4: (pd.Timestamp("2025-10-27 00:00:00"), pd.Timestamp("2025-10-31 23:59:59")),
}

# Parameter grid
TP_mults   = [1.5, 2.0]
SL_mults   = [1.0, 1.5]
ATR_mins   = [0.2, 0.5]
VWAP_tols  = [0.0008]
T_stops    = [50, 100]
PARAM_GRID = list(product(TP_mults, SL_mults, ATR_mins, VWAP_tols, T_stops))

# A default set to inspect trades explicitly
DEFAULT_PARAMS = {'TP_mult': 1.5, 'SL_mult': 1.0, 'ATR_min': 0.2, 'VWAP_tol': 0.0008, 'T_stop': 50}

# ==========================
# Robust MT5 CSV loader
# ==========================
def load_mt5_csv(file_path: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Try encodings
    for enc in ['utf-16', 'utf-8']:
        try:
            # Peek first line to choose delimiter
            with open(file_path, 'r', encoding=enc) as f:
                first_line = f.readline()
            sep = ',' if ',' in first_line else '\t'

            # Read raw with guessed delimiter
            df = pd.read_csv(file_path, sep=sep, skiprows=1, encoding=enc, header=None)

            # Decide column layout: combined datetime vs split date/time
            cols = df.columns.tolist()
            first_col_str = df.iloc[0, 0].astype(str) if hasattr(df.iloc[0,0], 'astype') else str(df.iloc[0,0])

            # If the first field looks like "YYYY.MM.DD HH:MM[:SS]" treat it as combined datetime
            if (' ' in first_col_str) and ('.' in first_col_str):
                df.columns = ['datetime', 'open', 'high', 'low', 'close', 'tickvol', 'volume', 'spread']
                # Detect seconds vs minutes (count colons)
                colon_count = first_col_str.count(':')
                fmt = "%Y.%m.%d %H:%M:%S" if colon_count == 2 else "%Y.%m.%d %H:%M"
                df['timestamp'] = pd.to_datetime(df['datetime'].astype(str).str.strip(), format=fmt, errors='coerce')
            else:
                # Assume split date/time
                df.columns = ['date', 'time', 'open', 'high', 'low', 'close', 'tickvol', 'volume', 'spread']
                time_sample = str(df.iloc[0, 1])
                colon_count = time_sample.count(':')
                fmt = "%Y.%m.%d %H:%M:%S" if colon_count == 2 else "%Y.%m.%d %H:%M"
                df['timestamp'] = pd.to_datetime(
                    df['date'].astype(str).str.strip() + ' ' + df['time'].astype(str).str.strip(),
                    format=fmt, errors='coerce'
                )

            # Convert numerics
            for col in ['open', 'high', 'low', 'close', 'tickvol', 'volume', 'spread']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Clean and sort
            df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

            return df
        except Exception:
            continue

    raise RuntimeError("Failed to load CSV with utf-16 or utf-8 and auto-detection")

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
    vol = np.where(df['volume'] == 0, df['tickvol'], df['volume'])
    df['cum_vol'] = vol.cumsum()
    df['cum_pv']  = (df['close'] * vol).cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_vol']
    return df.drop(columns=['cum_vol', 'cum_pv'])

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

    # Ensure enough bars for EMA50 and ATR14
    start_idx = max(51, 14)

    for i in range(start_idx, len(df) - T_stop - 1):
        row  = df.iloc[i]
        prev = df.iloc[i - 1]

        # Skip low-volatility candles
        if np.isnan(row['atr']) or row['atr'] < ATR_min:
            continue

        # --- Longs ---
        if (row['close'] > row['vwap']) and (row['ema20'] > row['ema50']):
            touch       = abs(row['low'] - row['vwap']) <= (row['vwap'] * VWAP_tol)
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
                    "timestamp_entry": row['timestamp'],
                    "direction": "LONG",
                    "entry_price": entry,
                    "exit_price": entry + result,
                    "outcome": outcome,
                    "result_pips": result
                })

        # --- Shorts ---
        elif (row['close'] < row['vwap']) and (row['ema20'] < row['ema50']):
            touch       = abs(row['high'] - row['vwap']) <= (row['vwap'] * VWAP_tol)
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
                    "timestamp_entry": row['timestamp'],
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
    for combo in param_grid:
        params = dict(zip(['TP_mult','SL_mult','ATR_min','VWAP_tol','T_stop'], combo))
        trades = generate_signals(df, params)
        if len(trades) == 0:
            continue
        num_trades = len(trades)
        wins  = (trades['result_pips'] > 0).sum()
        win_rate = wins / num_trades if num_trades else 0
        expectancy = trades['result_pips'].mean()
        pf = trades[trades['result_pips']>0]['result_pips'].sum() / \
             abs(trades[trades['result_pips']<0]['result_pips'].sum() + 1e-6)
        results.append({
            **params,
            'num_trades': num_trades,
            'win_rate': round(win_rate, 3),
            'expectancy': round(expectancy, 3),
            'profit_factor': round(pf, 2)
        })
    if not results:
        return pd.DataFrame(columns=['TP_mult','SL_mult','ATR_min','VWAP_tol','T_stop','num_trades','win_rate','expectancy','profit_factor'])
    return pd.DataFrame(results).sort_values(by='expectancy', ascending=False)

# ==========================
# Main: load, filter, compute, run
# ==========================
if __name__ == "__main__":
    df = load_mt5_csv(FILE)
    print("✅ CSV loaded. Timestamp range:", df['timestamp'].min(), "→", df['timestamp'].max())

    # Week selection
    if WEEK_CHOICE not in WEEKS:
        raise ValueError(f"WEEK_CHOICE must be 1–4, got {WEEK_CHOICE}")
    START, END = WEEKS[WEEK_CHOICE]
    df_week = df[(df['timestamp'] >= START) & (df['timestamp'] <= END)].copy()

    if df_week.empty:
        print(f"❌ No data for Week {WEEK_CHOICE} ({START} → {END}). Check the CSV range above.")
        raise SystemExit(0)

    print(f"✅ Week {WEEK_CHOICE} rows: {len(df_week)}")

    # Indicators for the selected week
    df_week['ema20'] = ema(df_week['close'], 20)
    df_week['ema50'] = ema(df_week['close'], 50)
    df_week['atr']   = atr(df_week, 14)
    df_week = compute_vwap(df_week)

    # Run backtest
    all_results = backtest(df_week, PARAM_GRID)
    trades = generate_signals(df_week, DEFAULT_PARAMS)

    print(f"\n✅ Trades generated (Week {WEEK_CHOICE}, default params): {len(trades)}")
    print(trades.head(10))

    print("\n🔎 Top parameter sets (by expectancy):")
    print(all_results.head(10))

    # Save outputs
    trades.to_csv(f"USTEC_Week{WEEK_CHOICE}_trades.csv", index=False)
    df_week.to_csv(f"USTEC_Week{WEEK_CHOICE}_data.csv", index=False)
    print(f"✅ Week {WEEK_CHOICE} trades and data saved for analysis.")