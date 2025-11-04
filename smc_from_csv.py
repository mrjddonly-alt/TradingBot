"""
smc_from_csv.py
Loads GBPUSD_M15.csv and GBPUSD_M1.csv (exported from MT5 History Center),
runs a simple Smart Money Concepts style backtest (BoS + order block + 1m confirmation),
and writes detected trades to trades_log.csv.
"""

import os
import pandas as pd
from datetime import timedelta

# --------------------
# CONFIG
# --------------------
M15_CSV = "GBPUSD_M15.csv"
M1_CSV  = "GBPUSD_M1.csv"
TRADES_LOG = "trades_log.csv"
DAYS_LOOKAHEAD_MIN = 24 * 60  # how many minutes to search after a 15m signal for 1m confirmation
ORDERBLOCK_LOOKBACK = 3       # number of 15m candles to consider as "order block" consolidation

# --------------------
# Helper: robust CSV reader for MT5 exports
# --------------------
def read_mt5_csv(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    # Try different separators commonly used in MT5 exports
    df = None
    last_exc = None
    for sep in [',', ';', '\t']:
        try:
            df_try = pd.read_csv(path, sep=sep, engine='python')
            # require at least 5 cols (time,open,high,low,close)
            if df_try.shape[1] >= 5:
                df = df_try
                break
        except Exception as e:
            last_exc = e
            continue
    if df is None:
        raise ValueError(f"Could not parse CSV: {path}. Last error: {last_exc}")

    # find time column
    cols_lower = [c.lower() for c in df.columns]
    time_col = None
    for name in ('time', 'date', 'datetime'):
        for c in df.columns:
            if c.lower().startswith(name):
                time_col = c
                break
        if time_col:
            break
    if time_col is None:
        time_col = df.columns[0]  # fallback to first column

    # parse datetimes robustly
    df[time_col] = df[time_col].astype(str).str.strip()
    df['time'] = pd.to_datetime(df[time_col], infer_datetime_format=True, errors='coerce')

    # find OHLC columns
    def find_col(prefixes):
        for p in prefixes:
            for c in df.columns:
                if c.lower().startswith(p):
                    return c
        return None

    open_col  = find_col(['open'])
    high_col  = find_col(['high'])
    low_col   = find_col(['low'])
    close_col = find_col(['close'])
    vol_col   = find_col(['tick','vol','volume'])

    # fallback: if columns are unnamed or different order, attempt positional mapping
    if any(x is None for x in (open_col, high_col, low_col, close_col)):
        # expect common order: time,open,high,low,close,vol (or similar)
        if df.shape[1] >= 6:
            # assume columns[1:6] are OHLCV
            open_col, high_col, low_col, close_col = df.columns[1], df.columns[2], df.columns[3], df.columns[4]
            if vol_col is None and df.shape[1] >= 6:
                vol_col = df.columns[5]

    # Ensure we have required columns now
    if any(x is None for x in (open_col, high_col, low_col, close_col)):
        raise ValueError(f"Could not detect OHLC columns in {path}. Columns found: {list(df.columns)}")

    # build normalized dataframe
    use_cols = {'time': 'time', open_col: 'open', high_col: 'high', low_col: 'low', close_col: 'close'}
    if vol_col:
        use_cols[vol_col] = 'volume'

    df2 = df[list(use_cols.keys())].rename(columns=use_cols)
    # coerce numeric
    for c in ['open','high','low','close','volume']:
        if c in df2.columns:
            df2[c] = pd.to_numeric(df2[c], errors='coerce')

    df2 = df2.dropna(subset=['time']).sort_values('time').reset_index(drop=True)

    return df2

# --------------------
# Load CSVs
# --------------------
print("Looking for CSV files in current folder:", os.getcwd())
for f in (M15_CSV, M1_CSV):
    print(" -", f, "→", "FOUND" if os.path.exists(f) else "MISSING")

if not os.path.exists(M15_CSV) or not os.path.exists(M1_CSV):
    raise SystemExit(
        "One or both CSV files are missing. Export GBPUSD M15 and M1 from MT5 History Center\n"
        f"and place them as '{M15_CSV}' and '{M1_CSV}' in this folder."
    )

print("Reading M15 CSV...")
df_15m = read_mt5_csv(M15_CSV)
print("Reading M1 CSV...")
df_1m  = read_mt5_csv(M1_CSV)

print(f"M15 range: {df_15m['time'].iloc[0]} → {df_15m['time'].iloc[-1]}   ({len(df_15m)} rows)")
print(f"M1  range: {df_1m['time'].iloc[0]} → {df_1m['time'].iloc[-1]}   ({len(df_1m)} rows)")

# --------------------
# SMC detection helpers
# --------------------
def break_of_structure(df, idx):
    """Bullish if close > max(high of previous 2), bearish if close < min(low of previous 2)"""
    if idx < 2:
        return None
    prev_high = df['high'].iloc[idx-2:idx].max()
    prev_low  = df['low'].iloc[idx-2:idx].min()
    if df['close'].iloc[idx] > prev_high:
        return "bullish"
    if df['close'].iloc[idx] < prev_low:
        return "bearish"
    return None

def order_block_price(df, idx, lookback=ORDERBLOCK_LOOKBACK):
    """
    Return an order block price level:
      - for bullish: the min low of the lookback candles before idx
      - for bearish: the max high of the lookback candles before idx
    """
    if idx < lookback:
        return None
    block = df.iloc[idx-lookback:idx]
    return {
        'bullish': float(block['low'].min()),
        'bearish': float(block['high'].max())
    }

def confirm_1m_entry(bos_type, ob_price, df_1m, start_time, max_minutes=DAYS_LOOKAHEAD_MIN):
    """Look forward in 1m candles from start_time up to max_minutes for price touching OB."""
    end_time = start_time + timedelta(minutes=max_minutes)
    subset = df_1m[(df_1m['time'] >= start_time) & (df_1m['time'] <= end_time)]
    if subset.empty:
        return None, None
    for _, row in subset.iterrows():
        if bos_type == 'bullish' and row['low'] <= ob_price:
            return row['time'], 'buy'
        if bos_type == 'bearish' and row['high'] >= ob_price:
            return row['time'], 'sell'
    return None, None

# --------------------
# Scan for signals on M15 and confirm on M1
# --------------------
detected_trades = []

for i in range(3, len(df_15m)):
    bos = break_of_structure(df_15m, i)
    if not bos:
        continue
    ob_dict = order_block_price(df_15m, i)
    if ob_dict is None:
        continue
    ob_price = ob_dict[bos]

    bos_time = df_15m['time'].iloc[i]
    entry_time, trade_type = confirm_1m_entry(bos, ob_price, df_1m, bos_time)
    if entry_time:
        detected_trades.append({
            'bos_time': bos_time,
            'bos_type': bos,
            'order_block_price': ob_price,
            'entry_time_1m': entry_time,
            'entry_type': trade_type
        })
        print(f"CONFIRMED: {trade_type.upper()} entry at {entry_time} (BoS {bos_time}, OB {ob_price})")

print(f"\nTotal confirmed trades found: {len(detected_trades)}")

# --------------------
# Save trades CSV
# --------------------
if detected_trades:
    df_trades = pd.DataFrame(detected_trades)
    df_trades.to_csv(TRADES_LOG, index=False)
    print(f"Wrote {len(detected_trades)} trades to {TRADES_LOG}")
else:
    print("No confirmed trades found; no CSV written.")

# --------------------
# End
# --------------------
print("Done. If you want the script to print more debugging info, edit the script's print statements.")
