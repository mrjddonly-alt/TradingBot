import MetaTrader5 as mt5
import pandas as pd

SYMBOL = "GBPUSD"
TIMEFRAME = mt5.TIMEFRAME_M1
BARS = 500

# ---------------------------
# Data helpers
# ---------------------------
def get_data(symbol, timeframe, bars):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def find_swings(df, lb=3):
    """Find swing highs and lows."""
    df['swing_high'] = df['high'].rolling(lb, center=True).max()
    df['swing_low'] = df['low'].rolling(lb, center=True).min()
    return df

# ---------------------------
# BOS + FVG detection
# ---------------------------
def detect_bos(df):
    """Detect Break of Structure (BOS)."""
    bos = []
    for i in range(2, len(df)):
        if df['close'][i] > df['swing_high'][i - 1]:  # Bullish BOS
            bos.append(('bullish', i))
        elif df['close'][i] < df['swing_low'][i - 1]:  # Bearish BOS
            bos.append(('bearish', i))
    return bos

def detect_fvg(df):
    """Detect Fair Value Gaps."""
    fvg_list = []
    for i in range(2, len(df)):
        # Bullish FVG
        if df['low'][i] > df['high'][i - 2]:
            fvg_list.append(('bullish', df['high'][i - 2], df['low'][i]))
        # Bearish FVG
        if df['high'][i] < df['low'][i - 2]:
            fvg_list.append(('bearish', df['low'][i - 2], df['high'][i]))
    return fvg_list

def choose_trade_setup(df):
    """Return trade signal and last FVG zone."""
    bos = detect_bos(df)
    fvg = detect_fvg(df)
    if not bos or not fvg:
        return None, None

    last_bos = bos[-1]
    last_fvg = fvg[-1]

    if last_bos[0] == 'bullish' and last_fvg[0] == 'bullish':
        return "buy", last_fvg
    elif last_bos[0] == 'bearish' and last_fvg[0] == 'bearish':
        return "sell", last_fvg
    return None, None

# ---------------------------
# Backtest Entry Function
# ---------------------------
def check_entry(signal, entry_data, ob_time, sl_pips, tp_pips):
    """
    Backtest entry checker:
    - Uses BOS + FVG to decide trade direction.
    - Simulates SL/TP hit.
    Always returns dict or None.
    """
    df = find_swings(entry_data.copy())
    trade_signal, zone = choose_trade_setup(df)

    if not trade_signal:
        return None

    # Simulated entry = close at ob_time
    if ob_time in entry_data.index:
        row = entry_data.loc[ob_time]
    else:
        row = entry_data.iloc[-1]
    entry_price = row['close']

    # Define SL and TP
    if trade_signal == "buy":
        sl_price = entry_price - sl_pips * 0.0001
        tp_price = entry_price + tp_pips * 0.0001
    else:  # sell
        sl_price = entry_price + sl_pips * 0.0001
        tp_price = entry_price - tp_pips * 0.0001

    pnl = 0
    exit_price = entry_price
    for _, r in entry_data.iterrows():
        if trade_signal == "buy":
            if r['low'] <= sl_price:
                exit_price, pnl = sl_price, -sl_pips
                break
            elif r['high'] >= tp_price:
                exit_price, pnl = tp_price, tp_pips
                break
        else:  # sell
            if r['high'] >= sl_price:
                exit_price, pnl = sl_price, -sl_pips
                break
            elif r['low'] <= tp_price:
                exit_price, pnl = tp_price, tp_pips
                break

    return {
        "time": ob_time,
        "type": trade_signal,
        "entry": entry_price,
        "exit": exit_price,
        "pnl": pnl
    }

# ---------------------------
# Standalone Test
# ---------------------------
if __name__ == "__main__":
    if not mt5.initialize():
        print("❌ MT5 init failed:", mt5.last_error())
    else:
        df = get_data(SYMBOL, TIMEFRAME, BARS)
        df = find_swings(df)
        sig, zone = choose_trade_setup(df)
        print("Signal:", sig, "| Zone:", zone)
        mt5.shutdown()
