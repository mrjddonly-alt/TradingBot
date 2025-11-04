"""
Multi-SMC Bot with Fibonacci + ATR Risk Management (DRY_RUN Testing Version)
- DRY_RUN safe
- FOK order filling
- ATR-based SL/TP
- Looser Wick Rejection for more signals
- Fib filter temporarily disabled for testing
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import datetime as dt

# ======================
# CONFIGURATION
# ======================
ACCOUNT = 5039796656
PASSWORD = "E!B0BnPx"
SERVER = "MetaQuotes-Demo"

SYMBOLS = ["XAUUSD"]
ENTRY_TF = mt5.TIMEFRAME_M1
ANALYSIS_TF = mt5.TIMEFRAME_M15

LOT_SIZE = 0.1
RR = 2
ATR_PERIOD = 14
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618]
COOLDOWN = 60
DRY_RUN = False   # ✅ Safe mode

# ======================
# LOGGING
# ======================
def log(msg):
    print(f"{dt.datetime.now()} | {msg}")

# ======================
# ATR CALCULATION
# ======================
def calc_atr(symbol, timeframe, period=14):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period+50)
    if rates is None or len(rates) < period+1:
        log(f"⚠️ ATR: Not enough data for {symbol}")
        return None
    df = pd.DataFrame(rates)
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = np.abs(df["high"] - df["close"].shift())
    df["low_close"] = np.abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)
    atr = df["tr"].rolling(period).mean().iloc[-1]
    return atr

# ======================
# FIBONACCI CHECK
# ======================
def check_fib_confluence(symbol, price):
    rates = mt5.copy_rates_from_pos(symbol, ANALYSIS_TF, 0, 100)
    if rates is None or len(rates) < 2:
        return None
    df = pd.DataFrame(rates)
    high = df["high"].max()
    low = df["low"].min()
    for lvl in FIB_LEVELS:
        fib_price = high - (high - low) * lvl
        if abs(price - fib_price) <= (0.001 * price):
            return round(lvl*100, 1)
    return None

# ======================
# ORDER BLOCK / WICK REJECTION DETECTION
# ======================
def detect_order_block(symbol):
    rates = mt5.copy_rates_from_pos(symbol, ENTRY_TF, 0, 20)
    if rates is None or len(rates) < 5:
        return None
    df = pd.DataFrame(rates)
    last_candle = df.iloc[-1]

    lower_wick_ratio = (last_candle['open'] - last_candle['low']) / last_candle['close']
    upper_wick_ratio = (last_candle['high'] - last_candle['open']) / last_candle['close']

    # Looser wick detection for testing
    if last_candle['close'] > last_candle['open'] and lower_wick_ratio > 0.25:
        return "buy"
    elif last_candle['close'] < last_candle['open'] and upper_wick_ratio > 0.25:
        return "sell"
    return None

# ======================
# SMC SIGNAL GENERATION
# ======================
def get_smc_signal(symbol):
    rates = mt5.copy_rates_from_pos(symbol, ANALYSIS_TF, 0, 50)
    if rates is None or len(rates) < 5:
        return None
    df = pd.DataFrame(rates)
    highs = df['high']
    lows = df['low']

    # Trend determination
    if highs.iloc[-1] > highs.iloc[-2] and lows.iloc[-1] > lows.iloc[-2]:
        trend = "up"
    elif highs.iloc[-1] < highs.iloc[-2] and lows.iloc[-1] < lows.iloc[-2]:
        trend = "down"
    else:
        trend = "range"

    # Wick/OB detection
    ob_signal = detect_order_block(symbol)
    tick = mt5.symbol_info_tick(symbol)
    price = tick.bid if tick else None
    if price is None or ob_signal is None:
        return None

    # Trend + OB alignment
    if trend == "up" and ob_signal == "buy":
        return "buy"
    elif trend == "down" and ob_signal == "sell":
        return "sell"
    else:
        return None

# ======================
# PLACE ORDER
# ======================
def place_order(symbol, signal, lot, price, atr):
    if atr is None:
        log(f"⚠️ No ATR for {symbol}, skipping order.")
        return False
    point = mt5.symbol_info(symbol).point
    sl = price + (atr * 2 if signal == "sell" else -atr * 2)
    tp = price - (atr * RR if signal == "sell" else -atr * RR)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_SELL if signal == "sell" else mt5.ORDER_TYPE_BUY,
        "price": price,
        "sl": round(sl, 5) if symbol != "XAUUSD" else round(sl, 2),
        "tp": round(tp, 5) if symbol != "XAUUSD" else round(tp, 2),
        "deviation": 20,
        "type_filling": mt5.ORDER_FILLING_FOK,
        "type_time": mt5.ORDER_TIME_GTC,
    }

    if DRY_RUN:
        log(f"📝 DRY_RUN: {signal.upper()} {symbol} at {price} SL={sl} TP={tp}")
        return True

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log(f"❌ Order failed {symbol} retcode={result.retcode} comment={result.comment}")
        return False
    else:
        log(f"✅ Order placed {symbol} {signal.upper()} at {price}")
        return True

# ======================
# MAIN LOOP
# ======================
def should_place_order(fib):
    # For DRY_RUN testing, ignore Fib filter
    return True

def main():
    log("Initializing MT5...")
    if not mt5.initialize():
        log("❌ MT5 initialization failed")
        return
    authorized = mt5.login(ACCOUNT, PASSWORD, SERVER)
    if not authorized:
        log("❌ Login failed")
        return

    acc = mt5.account_info()
    log(f"✅ Logged in successfully | Account={acc.login} | Balance={acc.balance} | TradeAllowed={acc.trade_allowed}")

    for s in SYMBOLS:
        info = mt5.symbol_info(s)
        if info is None:
            log(f"❌ Symbol not found: {s}")
        else:
            log(f"✅ Symbol OK: {s} | Point={info.point} | Digits={info.digits}")

    log(f"Starting main loop...")
    cooldowns = {}

    while True:
        for s in SYMBOLS:
            tick = mt5.symbol_info_tick(s)
            if tick is None:
                continue
            price = tick.bid
            atr = calc_atr(s, ENTRY_TF, ATR_PERIOD)
            fib = check_fib_confluence(s, price)
            signal = get_smc_signal(s)

            if signal is None:
                continue

            log(f"ℹ️ {s}: Signal={signal}, Price={price}, ATR={atr}, Fib={fib}")

            # Cooldown check
            if s in cooldowns and (time.time() - cooldowns[s]) < COOLDOWN:
                log(f"📊 {s}: Cooldown active ({int(COOLDOWN-(time.time()-cooldowns[s]))}s left)")
                continue

            if should_place_order(fib):
                placed = place_order(s, signal, LOT_SIZE, price, atr)
                if placed:
                    cooldowns[s] = time.time()

        time.sleep(5)

    mt5.shutdown()

# ======================
# RUN
# ======================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("🔒 Bot stopped manually")
        mt5.shutdown()
