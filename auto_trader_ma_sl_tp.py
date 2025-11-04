import os, time
import ccxt
import pandas as pd

# === USER SETTINGS ===
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1m'
LIMIT = 150
FAST_MA = 5
SLOW_MA = 20
RISK_FRACTION = 0.10  # Use 10% of balance per trade
STOP_LOSS_PCT = 0.01  # 1% stop-loss
TAKE_PROFIT_PCT = 0.02  # 2% take-profit
POLL_SECONDS = 10

# === AUTH + EXCHANGE (TESTNET) ===
api_key = os.getenv('BINANCE_API_KEY', '')
secret = os.getenv('BINANCE_SECRET', '')

if not api_key or not secret:
    raise SystemExit("❌ Set BINANCE_API_KEY and BINANCE_SECRET environment variables first.")

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)
markets = exchange.load_markets()

def fetch_df():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

def last_cross_signal(df):
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
    return exchange.fetch_balance().get('free', {}).get('USDT', 0)

def get_free_base():
    base = SYMBOL.split('/')[0]
    return exchange.fetch_balance().get('free', {}).get(base, 0)

def size_for_buy(to_spend, price):
    return float(exchange.amount_to_precision(SYMBOL, to_spend / price if price > 0 else 0))

def size_for_sell(amount):
    return float(exchange.amount_to_precision(SYMBOL, amount))

def place_market_buy(amount):
    if amount <= 0: return None
    print(f"🟢 MARKET BUY {amount}")
    return exchange.create_market_buy_order(SYMBOL, amount)

def place_market_sell(amount):
    if amount <= 0: return None
    print(f"🔴 MARKET SELL {amount}")
    return exchange.create_market_sell_order(SYMBOL, amount)

def place_sl_tp(amount, entry_price):
    """Place SL & TP limit orders after a BUY"""
    stop_loss = entry_price * (1 - STOP_LOSS_PCT)
    take_profit = entry_price * (1 + TAKE_PROFIT_PCT)
    stop_loss = float(exchange.price_to_precision(SYMBOL, stop_loss))
    take_profit = float(exchange.price_to_precision(SYMBOL, take_profit))
    amount = float(exchange.amount_to_precision(SYMBOL, amount))
    print(f"📉 Placing STOP LOSS at {stop_loss} | 📈 TAKE PROFIT at {take_profit}")

    try:
        # Stop-Loss Sell (Stop-Market)
        exchange.create_order(
            symbol=SYMBOL,
            type='STOP_MARKET',
            side='sell',
            amount=amount,
            params={'stopPrice': stop_loss}
        )
        # Take-Profit Sell (Limit)
        exchange.create_limit_sell_order(SYMBOL, amount, take_profit)
    except Exception as e:
        print("⚠️ Failed to place SL/TP:", e)

def run():
    print(f"🚀 Auto Trader with SL/TP (MA {FAST_MA}/{SLOW_MA}) — TESTNET MODE\n")
    in_position = False

    while True:
        try:
            df = fetch_df()
            ticker = exchange.fetch_ticker(SYMBOL)
            last_price = float(ticker['last'])
            signal = last_cross_signal(df)
            print(f"[{pd.to_datetime('now'):%H:%M:%S}] Price={last_price} | Signal={signal}")

            if signal == 'BUY' and not in_position:
                usdt = get_free_usdt()
                qty = size_for_buy(usdt * RISK_FRACTION, last_price)
                order = place_market_buy(qty)
                if order:
                    in_position = True
                    entry_price = last_price
                    place_sl_tp(qty, entry_price)
                    print(f"✅ BUY filled at {entry_price}, SL/TP placed")

            elif signal == 'SELL' and in_position:
                base_amt = get_free_base()
                qty = size_for_sell(base_amt)
                order = place_market_sell(qty)
                if order:
                    in_position = False
                    print(f"✅ SELL filled at {last_price}")

        except Exception as e:
            print("❗ Error:", type(e).__name__, e)
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    run()
