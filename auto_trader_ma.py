import os, time
import ccxt
import pandas as pd

# === USER SETTINGS ===
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1m'          # 1-minute candles
LIMIT = 150               # candles fetched each loop
FAST_MA = 5
SLOW_MA = 20
RISK_FRACTION = 0.10      # use 10% of USDT balance per trade
POLL_SECONDS = 10         # refresh rate

# === AUTH + EXCHANGE (TESTNET) ===
api_key = os.getenv('BINANCE_API_KEY', '')
secret  = os.getenv('BINANCE_SECRET', '')

if not api_key or not secret:
    raise SystemExit("❌ Set BINANCE_API_KEY and BINANCE_SECRET environment variables first.")

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True,
})
# IMPORTANT: stay in sandbox while testing
exchange.set_sandbox_mode(True)

# Preload markets (gives precision/limits)
markets = exchange.load_markets()
if SYMBOL not in markets:
    raise SystemExit(f"❌ {SYMBOL} not found on exchange.")

def fetch_df():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

def last_cross_signal(df):
    """
    Returns 'BUY' if fast MA crossed above slow MA on the last candle,
            'SELL' if fast crossed below slow,
            None otherwise.
    """
    df['MA_Fast'] = df['close'].rolling(FAST_MA).mean()
    df['MA_Slow'] = df['close'].rolling(SLOW_MA).mean()
    if len(df) < max(FAST_MA, SLOW_MA) + 2:
        return None

    fast_prev, fast_now = df['MA_Fast'].iloc[-2], df['MA_Fast'].iloc[-1]
    slow_prev, slow_now = df['MA_Slow'].iloc[-2], df['MA_Slow'].iloc[-1]

    if pd.notna(fast_prev) and pd.notna(slow_prev):
        if fast_prev <= slow_prev and fast_now > slow_now:
            return 'BUY'
        if fast_prev >= slow_prev and fast_now < slow_now:
            return 'SELL'
    return None

def get_free_usdt():
    bal = exchange.fetch_balance()
    return bal.get('free', {}).get('USDT', 0)

def get_free_base():
    base = SYMBOL.split('/')[0]
    bal = exchange.fetch_balance()
    return bal.get('free', {}).get(base, 0)

def size_for_buy(quote_to_use, last_price):
    # Convert USDT to base amount, then precision-round
    raw_amount = quote_to_use / last_price if last_price > 0 else 0
    return float(exchange.amount_to_precision(SYMBOL, raw_amount))

def size_for_sell(available_base):
    return float(exchange.amount_to_precision(SYMBOL, max(0, available_base)))

def place_market_buy(amount_base):
    if amount_base <= 0:
        print("⚠️ Skipping buy: computed amount <= 0")
        return None
    print(f"🟢 Placing MARKET BUY {amount_base} {SYMBOL.split('/')[0]}")
    return exchange.create_market_buy_order(SYMBOL, amount_base)

def place_market_sell(amount_base):
    if amount_base <= 0:
        print("⚠️ Skipping sell: computed amount <= 0")
        return None
    print(f"🔴 Placing MARKET SELL {amount_base} {SYMBOL.split('/')[0]}")
    return exchange.create_market_sell_order(SYMBOL, amount_base)

def run():
    print(f"🚀 Auto Trader (MA {FAST_MA}/{SLOW_MA}) on {SYMBOL} — TESTNET MODE")
    print("⏱  Polling every", POLL_SECONDS, "seconds\n")

    in_position = False  # simple position flag (spot: long or flat)
    while True:
        try:
            df = fetch_df()
            ticker = exchange.fetch_ticker(SYMBOL)
            last_price = float(ticker['last'])
            signal = last_cross_signal(df)

            print(f"[{pd.to_datetime('now'):%H:%M:%S}] Price={last_price} | Signal={signal}")

            if signal == 'BUY' and not in_position:
                usdt_free = get_free_usdt()
                to_spend = usdt_free * RISK_FRACTION
                qty = size_for_buy(to_spend, last_price)
                order = place_market_buy(qty)
                if order:
                    in_position = True
                    print("✅ BUY filled:", order.get('id', '(no id)'))

            elif signal == 'SELL' and in_position:
                base_free = get_free_base()
                qty = size_for_sell(base_free)
                order = place_market_sell(qty)
                if order:
                    in_position = False
                    print("✅ SELL filled:", order.get('id', '(no id)'))

        except ccxt.NetworkError as e:
            print("🌐 Network error:", e)
        except ccxt.ExchangeError as e:
            print("🏦 Exchange error:", e)
        except Exception as e:
            print("❗ Unexpected error:", type(e).__name__, e)

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    run()
