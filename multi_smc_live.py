import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time

# ======================
# CONFIGURATION
# ======================
ACCOUNT = 5039796656          # your MT5 account
PASSWORD = "E!B0BnPx"    # your MT5 password
SERVER = "MetaQuotes-Demo"   # your MT5 server
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M1
MIN_MOVE = 0.5                # minimum price move to trigger signal
LOT_SIZE = 0.01               # trading lot size
DRY_RUN = False               # True = simulate orders, False = place live orders

# Hardcoded trading session: London + New York overlap (SAST)
SESSION_START = 9   # 09:00
SESSION_END = 23    # 23:00

# ======================
# HELPER FUNCTIONS
# ======================
def in_session():
    now = datetime.now()
    return SESSION_START <= now.hour < SESSION_END

def log(message):
    print(f"{datetime.now()} | {message}")

def place_order(action, price, sl, tp):
    if DRY_RUN:
        log(f"✅ (DRY_RUN) Would have placed {action} {SYMBOL} @ {price:.2f} SL={sl:.2f} TP={tp:.2f} lot={LOT_SIZE}")
        return

    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 5,
        "magic": 123456,
        "comment": "SMC Bot",
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log(f"⚠ Order failed: {result}")
    else:
        log(f"✅ Order placed: {action} {SYMBOL} @ {price:.2f} SL={sl:.2f} TP={tp:.2f}")

# ======================
# MT5 INITIALIZATION
# ======================
if not mt5.initialize():
    log("MT5 initialize() failed")
    quit()

if not mt5.login(ACCOUNT, password=PASSWORD, server=SERVER):
    log("MT5 login failed")
    mt5.shutdown()
    quit()
else:
    log(f"MT5 login successful: Account {ACCOUNT} on {SERVER}")

# ======================
# MAIN BOT LOOP
# ======================
while True:
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 10)
    if rates is None:
        log("Failed to fetch rates")
        time.sleep(1)
        continue

    df = pd.DataFrame(rates)
    df['ATR'] = df['high'] - df['low']  # simple ATR

    last_candle = df.iloc[-1]

    price = last_candle['close']
    body = abs(last_candle['close'] - last_candle['open'])
    lower_wick = last_candle['open'] - last_candle['low'] if last_candle['close'] >= last_candle['open'] else last_candle['close'] - last_candle['low']
    upper_wick = last_candle['high'] - last_candle['close'] if last_candle['close'] >= last_candle['open'] else last_candle['high'] - last_candle['open']
    trend = "up" if last_candle['close'] > last_candle['open'] else "down"
    atr = last_candle['ATR']

    log(f"{SYMBOL}: price={price:.2f} LWR={lower_wick:.2f} UWR={upper_wick:.2f} body={body:.2f} trend={trend} ATR={atr:.2f}")

    if not in_session():
        log(f"⏸ Outside trading session ({SESSION_START}:00–{SESSION_END}:00) → skipping signals")
        time.sleep(1)
        continue

    # Signal logic: body and ATR must exceed MIN_MOVE
    if trend == "up" and body >= MIN_MOVE and atr >= MIN_MOVE:
        sl = price - MIN_MOVE*2
        tp = price + MIN_MOVE*3
        place_order("BUY", price, sl, tp)
    elif trend == "down" and body >= MIN_MOVE and atr >= MIN_MOVE:
        sl = price + MIN_MOVE*2
        tp = price - MIN_MOVE*3
        place_order("SELL", price, sl, tp)
    else:
        log(f"⏳ Signal suppressed by MIN_MOVE or ATR filter (body={body:.2f}, ATR={atr:.2f} < {MIN_MOVE})")

    time.sleep(1)
