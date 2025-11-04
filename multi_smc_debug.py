import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

# ======================
# CONFIGURATION
# ======================
ACCOUNT = 5039796656
PASSWORD = "E!B0BnPx"
SERVER = "MetaQuotes-Demos"
SYMBOLS = ["XAUUSD"]
LOT_SIZE = 0.1
RR = 1.5  # Risk-Reward ratio
COOLDOWN = 5  # seconds between trades
LWR_THRESHOLD = 0.25
UWR_THRESHOLD = 0.25
MIN_ATR = 0.5
ATR_MULTIPLIER_SL = 1

# ======================
# LOGIN
# ======================
if not mt5.initialize(login=ACCOUNT, password=PASSWORD, server=SERVER):
    print(f"❌ MT5 init failed, error code={mt5.last_error()}")
    quit()
print(f"{datetime.now()} | ✅ Logged in successfully | Account={ACCOUNT}")

# ======================
# HELPER FUNCTIONS
# ======================
def get_ticks(symbol, n=50):
    """Get last n ticks as DataFrame"""
    ticks = mt5.copy_ticks_from(symbol, datetime.now(), n, mt5.COPY_TICKS_ALL)
    df = pd.DataFrame(ticks)
    return df

def calculate_atr(df):
    """ATR calculation using last n ticks"""
    df['high'] = df['ask']
    df['low'] = df['bid']
    df['close'] = (df['ask'] + df['bid']) / 2
    df['tr'] = df[['high','low','close']].apply(
        lambda row: max(row['high'] - row['low'], abs(row['high'] - row['close']), abs(row['low'] - row['close'])), axis=1
    )
    atr = df['tr'].rolling(14).mean().iloc[-1]
    return atr

def get_m15_trend(symbol):
    """Determine trend from last 5 M15 candles"""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 5)
    closes = [r['close'] for r in rates]
    if all(x < y for x, y in zip(closes, closes[1:])):
        return 'up'
    elif all(x > y for x, y in zip(closes, closes[1:])):
        return 'down'
    else:
        return 'neutral'

# ======================
# MAIN LOOP
# ======================
last_order_time = 0
while True:
    for symbol in SYMBOLS:
        ticks = get_ticks(symbol, n=50)
        atr = calculate_atr(ticks)

        # Calculate LWR/UWR (simplified)
        lwr = min(ticks['ask']) / max(ticks['ask'])
        uwr = max(ticks['ask']) / min(ticks['ask'])

        trend = get_m15_trend(symbol)
        cooldown_remaining = max(0, COOLDOWN - (time.time() - last_order_time))

        # Debug logs
        print(f"{datetime.now()} | DEBUG {symbol}: LWR={lwr:.2f} UWR={uwr:.2f} Trend={trend} ATR={atr:.3f}")

        # Signal logic
        signal = None
        if atr >= MIN_ATR:
            if lwr < LWR_THRESHOLD and trend in ['up','neutral']:
                signal = 'buy'
            elif uwr < UWR_THRESHOLD and trend in ['down','neutral']:
                signal = 'sell'

        # Order execution
        if signal and cooldown_remaining <= 0:
            price = ticks['ask'].iloc[-1] if signal=='buy' else ticks['bid'].iloc[-1]
            sl = price - ATR_MULTIPLIER_SL * atr if signal=='buy' else price + ATR_MULTIPLIER_SL * atr
            tp = price + RR*(price-sl) if signal=='buy' else price - RR*(sl-price)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": LOT_SIZE,
                "type": mt5.ORDER_TYPE_BUY if signal=='buy' else mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 2,
                "magic": 123456,
                "comment": "SMC scalper",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"{datetime.now()} | ✅ Order placed {symbol} {signal.upper()} at {price:.2f} | SL={sl:.2f} TP={tp:.2f}")
                last_order_time = time.time()
            else:
                print(f"{datetime.now()} | ❌ Order failed: {result.retcode}")

    time.sleep(1)  # loop delay
