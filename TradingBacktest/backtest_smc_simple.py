import pandas as pd
import numpy as np
import datetime as dt

# ======================
# CONFIGURATION
# ======================
SYMBOL = "XAUUSD"
ENTRY_TF = "M1"       # Your saved CSV for M1
ANALYSIS_TF = "M15"   # Your saved CSV for M15
LOT_SIZE = 0.1
RR = 2
ATR_PERIOD = 14
ATR_SL_FACTOR = 1.5
MIN_ATR = 5
COOLDOWN = 600  # seconds
RISK_PER_TRADE = 0.01
ACCOUNT_BALANCE = 10000
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618]

# ======================
# UTILITY FUNCTIONS
# ======================
def log(msg):
    print(f"{dt.datetime.now()} | {msg}")

def calc_atr(df, period=ATR_PERIOD):
    df = df.copy()
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = np.abs(df["high"] - df["close"].shift())
    df["low_close"] = np.abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low","high_close","low_close"]].max(axis=1)
    df["atr"] = df["tr"].rolling(period).mean()
    return df

def get_trend(df, lookback=50):
    df = df.copy()
    df['trend'] = np.where(df['close'] > df['close'].rolling(lookback).mean(), 'UP', 'DOWN')
    return df

def detect_order_block(df):
    last_candle = df.iloc[-1]
    body = abs(last_candle['close'] - last_candle['open'])
    candle_range = last_candle['high'] - last_candle['low']
    if candle_range == 0:
        return None
    upper_wick = last_candle['high'] - max(last_candle['close'], last_candle['open'])
    lower_wick = min(last_candle['close'], last_candle['open']) - last_candle['low']

    if body < 0.2 * candle_range or upper_wick > 0.95 * candle_range or lower_wick > 0.95 * candle_range:
        pass  # lenient, consider signal anyway

    if last_candle['close'] > last_candle['open']:
        return "buy"
    elif last_candle['close'] < last_candle['open']:
        return "sell"
    return None

def check_fib_confluence(df, price):
    high = df['high'].max()
    low = df['low'].min()
    for lvl in FIB_LEVELS:
        fib_price = high - (high - low) * lvl
        if abs(price - fib_price) <= (0.002 * price):
            return round(lvl*100,1)
    return None

def get_smc_signal(entry_df, analysis_df, i):
    trend = analysis_df['trend'].iloc[-1]
    ob_signal = detect_order_block(entry_df)
    price = entry_df['close'].iloc[-1]

    if trend == "UP" and ob_signal == "buy":
        return "buy"
    elif trend == "DOWN" and ob_signal == "sell":
        return "sell"
    elif ob_signal is None and trend in ["UP","DOWN"]:
        return "buy" if trend=="UP" else "sell"
    return None

# ======================
# BACKTEST
# ======================
def run_backtest(entry_file, analysis_file):
    df_low = pd.read_csv(entry_file, parse_dates=['time'])
    df_high = pd.read_csv(analysis_file, parse_dates=['time'])

    df_high = calc_atr(df_high)
    df_high = get_trend(df_high)
    df_low = calc_atr(df_low)

    df_low = pd.merge_asof(df_low.sort_values('time'),
                           df_high[['time','trend','atr']].sort_values('time'),
                           on='time', direction='backward')

    trades = []
    open_trade = None
    cooldown = -COOLDOWN  # initialize

    for i, row in df_low.iterrows():
        price = row['close']
        atr = row['atr']
        if atr is None or atr < MIN_ATR:
            continue

        signal = get_smc_signal(df_low.iloc[max(i-20,0):i+1], df_high.iloc[max(i-50,0):i+1], i)
        fib = check_fib_confluence(df_high.iloc[max(i-100,0):i+1], price)

        if signal is None:
            continue

        # Cooldown check
        if trades and (price - trades[-1]['entry_time']).total_seconds() < COOLDOWN:
            continue

        # Close previous
        if open_trade:
            open_trade['exit_price'] = price
            open_trade['pnl'] = (open_trade['exit_price'] - open_trade['entry_price']) * (1 if open_trade['signal']=='buy' else -1)
            trades.append(open_trade)

        sl = atr * ATR_SL_FACTOR
        tp = sl * RR
        risk_amount = ACCOUNT_BALANCE * RISK_PER_TRADE
        position_size = risk_amount / sl if sl>0 else 0

        open_trade = {
            'signal': signal,
            'entry_price': price,
            'entry_time': row['time'],
            'sl': price - sl if signal=='buy' else price + sl,
            'tp': price + tp if signal=='buy' else price - tp,
            'position_size': position_size,
            'fib': fib
        }

    # close last trade
    if open_trade:
        open_trade['exit_price'] = df_low.iloc[-1]['close']
        open_trade['pnl'] = (open_trade['exit_price'] - open_trade['entry_price']) * (1 if open_trade['signal']=='buy' else -1)
        trades.append(open_trade)

    trades_df = pd.DataFrame(trades)

    # Performance metrics
    total_trades = len(trades_df)
    wins = trades_df[trades_df['pnl']>0].shape[0] if total_trades>0 else 0
    win_rate = wins/total_trades*100 if total_trades>0 else 0
    avg_pnl = trades_df['pnl'].mean() if total_trades>0 else 0
    cum_pnl = trades_df['pnl'].cumsum() if total_trades>0 else pd.Series([0])
    max_dd = cum_pnl.cummax() - cum_pnl if total_trades>0 else pd.Series([0])

    print(f"Total trades: {total_trades}")
    print(f"Winning trades: {wins} ({win_rate:.2f}%)")
    print(f"Average PnL per trade: {avg_pnl:.2f}")
    print(f"Cumulative PnL: {cum_pnl.iloc[-1]:.2f}")
    print(f"Max drawdown: {max_dd.max():.2f}")

    return trades_df

# ======================
# RUN
# ======================
if __name__=="__main__":
    trades_df = run_backtest("XAUUSD_M1.csv","XAUUSD_M15.csv")
