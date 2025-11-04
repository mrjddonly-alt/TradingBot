"""
Multi-Pair SMC Bot with Full Debug and FOK Orders
- M15 analysis for SMC zones: FVG, Liquidity Grab, Order Block
- Executes trades on M1 only when price touches detected zones
- Cooldown per symbol
- CSV logging for trades and detected zones
- Full debug logging
"""

import MetaTrader5 as mt5
from datetime import datetime
import time
import csv
import os

# --------------------
# CONFIG
# --------------------
ACCOUNT = 5039796656
PASSWORD = "E!B0BnPx"
SERVER = "MetaQuotes-Demo"
SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD"]  # add your pairs here
LOT_SIZE = 0.1
SL_PIPS = 15
TP_PIPS = 30
MAGIC = 123456
COOLDOWN = 60  # seconds
ANALYSIS_TF = mt5.TIMEFRAME_M15
EXECUTION_TF = mt5.TIMEFRAME_M1
BARS_ANALYSIS = 100
LOG_FILE = "smc_trades_log.csv"

# --------------------
# Logging helpers
# --------------------
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"{now()} | {msg}")

def log_to_csv(data_dict):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data_dict.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data_dict)

# --------------------
# MT5 Init
# --------------------
def init_mt5():
    log("🔹 Initializing MT5...")
    if not mt5.initialize():
        log(f"❌ MT5 init failed: {mt5.last_error()}")
        return False
    log("✅ MT5 initialized")

    log("🔹 Logging in...")
    if not mt5.login(ACCOUNT, PASSWORD, SERVER):
        log(f"❌ Login failed: {mt5.last_error()}")
        mt5.shutdown()
        return False
    log("✅ Logged in successfully")

    ai = mt5.account_info()
    if ai is None:
        log(f"❌ Failed to get account info: {mt5.last_error()}")
        mt5.shutdown()
        return False
    log(f"💰 Account={ai.login}, Balance={ai.balance}, TradeAllowed={ai.trade_allowed}")
    return True

def ensure_symbol(symbol):
    si = mt5.symbol_info(symbol)
    if si is None:
        log(f"❌ Symbol {symbol} not found")
        return False, None
    if not si.visible:
        if not mt5.symbol_select(symbol, True):
            log(f"❌ Failed to enable {symbol}")
            return False, si
    return True, si

def can_trade():
    ai = mt5.account_info()
    return ai.trade_allowed if ai else False

# --------------------
# Place order (FOK)
# --------------------
def place_order(symbol, lot, order_type, sl_pips, tp_pips):
    tick = mt5.symbol_info_tick(symbol)
    si = mt5.symbol_info(symbol)
    if not tick or not si:
        log(f"❌ Failed to get symbol info/tick for {symbol}")
        return None

    price = tick.ask if order_type == "buy" else tick.bid
    sl = price - sl_pips * si.point if order_type == "buy" else price + sl_pips * si.point
    tp = price + tp_pips * si.point if order_type == "buy" else price - tp_pips * si.point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC,
        "comment": "SMC Multi-Pair Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    log(f"📤 Sending {order_type.upper()} {symbol} price={price} sl={sl} tp={tp} volume={lot} (FOK)")
    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"✅ {order_type.upper()} order placed for {symbol} at {price}")
        log_to_csv({
            "time": now(),
            "symbol": symbol,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp
        })
        return result
    else:
        log(f"❌ Order failed {symbol} retcode={result.retcode}, comment={result.comment}, last_error={mt5.last_error()}")
        return None

# --------------------
# Detect SMC zones
# --------------------
def detect_smc_zones(symbol, bars=BARS_ANALYSIS, analysis_tf=ANALYSIS_TF):
    rates = mt5.copy_rates_from_pos(symbol, analysis_tf, 0, bars)
    if rates is None or len(rates) < 3:
        log(f"⚠️ Not enough data to detect SMC for {symbol}")
        return None

    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    closes = [r['close'] for r in rates]
    opens = [r['open'] for r in rates]

    signal = None
    fvg_zone = None
    lb_zone = None
    ob_zone = None

    # FVG detection
    for i in range(1, len(rates)-1):
        if opens[i+1] > closes[i-1]:
            fvg_zone = (closes[i-1], opens[i+1])
        elif opens[i+1] < closes[i-1]:
            fvg_zone = (opens[i+1], closes[i-1])

    # Liquidity Grab detection
    prev_high = max(highs[:-1])
    prev_low = min(lows[:-1])
    last_candle = rates[-1]
    if last_candle['high'] > prev_high:
        lb_zone = (prev_high, last_candle['high'])
        signal = "sell"
    elif last_candle['low'] < prev_low:
        lb_zone = (last_candle['low'], prev_low)
        signal = "buy"

    # Order Block detection
    for i in range(len(rates)-2, -1, -1):
        if closes[i] < opens[i] and closes[i+1] > closes[i]:
            ob_zone = (lows[i], highs[i])
            if signal is None:
                signal = "buy"
            break
        elif closes[i] > opens[i] and closes[i+1] < closes[i]:
            ob_zone = (lows[i], highs[i])
            if signal is None:
                signal = "sell"
            break

    if signal:
        return {
            'signal': signal,
            'fvg': fvg_zone,
            'liquidity_grab': lb_zone,
            'order_block': ob_zone
        }
    return None

def is_price_in_zone(price, zone):
    if zone is None:
        return False
    low, high = zone
    return low <= price <= high

# --------------------
# Main loop
# --------------------
def main():
    print("🚀 Starting Multi-Pair SMC Bot (Debug Enabled)")

    if not init_mt5():
        print("❌ MT5 init/login failed. Exiting.")
        return

    # Check symbols
    available_symbols = []
    for symbol in SYMBOLS:
        ok, _ = ensure_symbol(symbol)
        if ok:
            available_symbols.append(symbol)
        else:
            log(f"⚠️ Skipping {symbol} - not available in Market Watch")

    if not available_symbols:
        log("❌ No available symbols to trade. Exiting.")
        mt5.shutdown()
        return

    log(f"✅ Ready to trade symbols: {available_symbols}")

    last_trade_times = {sym: 0 for sym in available_symbols}

    try:
        while True:
            for symbol in available_symbols:
                smc_info = detect_smc_zones(symbol)
                current_time = time.time()

                if smc_info:
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is None:
                        log(f"⚠️ Could not get tick for {symbol}")
                        continue
                    current_price = tick.ask if smc_info['signal'] == 'buy' else tick.bid
                    inside_any = any(is_price_in_zone(current_price, z) for z in [
                        smc_info['fvg'], smc_info['order_block'], smc_info['liquidity_grab']
                    ])
                    log(f"ℹ️ {symbol}: Signal={smc_info['signal']}, Price={current_price}, InsideZone={inside_any}")

                    if inside_any and can_trade() and current_time - last_trade_times[symbol] > COOLDOWN:
                        log(f"💡 {symbol}: Placing {smc_info['signal'].upper()} order")
                        place_order(symbol, LOT_SIZE, smc_info['signal'], SL_PIPS, TP_PIPS)
                        last_trade_times[symbol] = current_time
                else:
                    log(f"📊 {symbol}: No SMC detected")

            time.sleep(5)

    except KeyboardInterrupt:
        log("🛑 Bot stopped manually.")
    finally:
        mt5.shutdown()
        log("🔒 MT5 shutdown complete.")

if __name__ == "__main__":
    main()
