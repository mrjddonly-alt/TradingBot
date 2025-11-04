"""
Trading Geek SMC Bot with M15 Zones, M1 Confirmation, Confluence & Visualization
"""

import MetaTrader5 as mt5
import time
from datetime import datetime
import csv
import os

# --------------------
# CONFIG
# --------------------
ACCOUNT   = 5039796656
PASSWORD  = "E!B0BnPx"
SERVER    = "MetaQuotes-Demo"
SYMBOL    = "GBPUSD"
LOT_SIZE  = 0.1
SL_PIPS   = 15
TP_PIPS   = 30
MAGIC     = 123456
COOLDOWN  = 60  # seconds
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
    if not mt5.initialize():
        log(f"❌ MT5 init failed: {mt5.last_error()}")
        return False
    if not mt5.login(ACCOUNT, PASSWORD, SERVER):
        log(f"❌ Login failed: {mt5.last_error()}")
        mt5.shutdown()
        return False
    ai = mt5.account_info()
    if ai is None:
        log(f"❌ Failed to get account info: {mt5.last_error()}")
        mt5.shutdown()
        return False
    log(f"✅ Logged in: Account={ai.login} | Balance={ai.balance} | TradeAllowed={ai.trade_allowed}")
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
# Place order
# --------------------
def place_order(symbol, lot, order_type, sl_pips, tp_pips):
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        log(f"❌ Failed to get tick for {symbol}")
        return None

    price = tick.ask if order_type=="buy" else tick.bid
    point = mt5.symbol_info(symbol).point
    sl = price - sl_pips*point if order_type=="buy" else price + sl_pips*point
    tp = price + tp_pips*point if order_type=="buy" else price - tp_pips*point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if order_type=="buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC,
        "comment": "TradingGeek SMC Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    log(f"📤 Sending {order_type.upper()} at price {price}")
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE and result.retcode != 1:
        log(f"❌ Order failed: {result} | last_error={mt5.last_error()}")
        return None

    log_to_csv({
        "time": now(),
        "symbol": symbol,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp
    })

    log(f"✅ {order_type.upper()} order placed! Price={price} | SL={sl} | TP={tp}")
    return result

# --------------------
# SMC Zone Detection
# --------------------
def detect_smc_zones(symbol, bars=BARS_ANALYSIS, analysis_tf=ANALYSIS_TF):
    rates = mt5.copy_rates_from_pos(symbol, analysis_tf, 0, bars)
    if rates is None or len(rates) < 3:
        return None

    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    closes = [r['close'] for r in rates]
    opens = [r['open'] for r in rates]

    signal = None
    fvg_zone = None
    lb_zone = None
    ob_zone = None

    # FVG
    for i in range(1, len(rates)-1):
        if opens[i+1] > closes[i-1]:
            fvg_zone = (closes[i-1], opens[i+1])
        elif opens[i+1] < closes[i-1]:
            fvg_zone = (opens[i+1], closes[i-1])

    # Liquidity Grab
    prev_high = max(highs[:-1])
    prev_low = min(lows[:-1])
    last_candle = rates[-1]
    if last_candle['high'] > prev_high:
        lb_zone = (prev_high, last_candle['high'])
        signal = "sell"
    elif last_candle['low'] < prev_low:
        lb_zone = (last_candle['low'], prev_low)
        signal = "buy"

    # Order Block
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
        log_to_csv({
            "time": now(),
            "symbol": symbol,
            "signal": signal,
            "fvg_zone": fvg_zone,
            "liquidity_grab": lb_zone,
            "order_block": ob_zone
        })
        return {
            'signal': signal,
            'fvg': fvg_zone,
            'liquidity_grab': lb_zone,
            'order_block': ob_zone
        }
    return None

# --------------------
# Helpers
# --------------------
def is_price_in_zone(price, zone):
    if zone is None:
        return False
    low, high = zone
    return low <= price <= high

def is_confluence(price, zone_list):
    return sum(1 for z in zone_list if is_price_in_zone(price, z)) >= 2

def draw_zone(symbol, zone, name, color):
    if zone is None:
        return
    low, high = zone
    chart_id = 0
    try:
        mt5.chart_object_delete(name)
    except:
        pass
    mt5.chart_rectangle_create(chart_id, name, 0, time.time(), high, time.time()+60*60, low)
    mt5.chart_object_set_integer(name, mt5.CHART_COLOR, color)

# --------------------
# Main Loop
# --------------------
def main():
    if not init_mt5():
        return
    ok, _ = ensure_symbol(SYMBOL)
    if not ok:
        mt5.shutdown()
        return

    last_trade_time = 0
    last_m15_time = None

    try:
        log("🚀 Starting Trading Geek SMC Bot with M1 Confirmation & Visualization...")

        while True:
            smc_info = detect_smc_zones(SYMBOL)
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick:
                continue
            current_price = tick.ask if smc_info and smc_info['signal']=='buy' else tick.bid
            current_time = time.time()

            # Draw zones once per new M15 candle
            m15_candle_time = int(mt5.copy_rates_from_pos(SYMBOL, ANALYSIS_TF, 0, 1)[0]['time'])
            if last_m15_time != m15_candle_time:
                last_m15_time = m15_candle_time
                if smc_info:
                    draw_zone(SYMBOL, smc_info['fvg'], "FVG", 0xFFFF00)  # Yellow
                    draw_zone(SYMBOL, smc_info['liquidity_grab'], "LB", 0xFF0000)  # Red
                    draw_zone(SYMBOL, smc_info['order_block'], "OB", 0x00FF00)  # Green

            # Only trade if SMC detected, cooldown passed, and price in confluence zones
            if smc_info and can_trade() and current_time - last_trade_time > COOLDOWN:
                if is_confluence(current_price, [smc_info['fvg'], smc_info['order_block'], smc_info['liquidity_grab']]):
                    log(f"💡 SMC Signal inside confluence zone: {smc_info['signal'].upper()}")
                    place_order(SYMBOL, LOT_SIZE, smc_info['signal'], SL_PIPS, TP_PIPS)
                    last_trade_time = current_time
                else:
                    log("📊 Signal detected but price not in confluence zones. Waiting...")

            time.sleep(5)

    except KeyboardInterrupt:
        log("🛑 Bot stopped manually by user.")
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
    finally:
        mt5.shutdown()
        log("🔒 MT5 shutdown complete.")

if __name__ == "__main__":
    main()
