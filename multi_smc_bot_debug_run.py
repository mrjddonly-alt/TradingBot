import MetaTrader5 as mt5
from datetime import datetime

SYMBOLS = ["GBPUSD", "XAUUSD", "EURUSD"]

def log(msg):
    print(f"{datetime.now()} | {msg}")

def main():
    print("🚀 Starting Multi-SMC Debug Test...")

    if not mt5.initialize():
        print("❌ MT5 init failed")
        return

    if not mt5.login(5039796656, "E!B0BnPx", "MetaQuotes-Demo"):
        print("❌ Login failed")
        mt5.shutdown()
        return

    log("✅ MT5 connected and logged in")

    for symbol in SYMBOLS:
        si = mt5.symbol_info(symbol)
        if si is None:
            log(f"❌ Symbol {symbol} not found")
            continue
        if not si.visible:
            if not mt5.symbol_select(symbol, True):
                log(f"❌ Failed to enable {symbol}")
                continue
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            log(f"ℹ️ {symbol} Tick: bid={tick.bid}, ask={tick.ask}")
        else:
            log(f"⚠️ {symbol} tick unavailable")

    mt5.shutdown()
    log("🔒 MT5 shutdown complete")

if __name__ == "__main__":
    main()
