import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

# -----------------------------
# CONFIGURATION
# -----------------------------
SYMBOL = "USTEC"
TIMEFRAME = mt5.TIMEFRAME_M1  # 1-minute candles (adjust if needed)
DAYS_BACK = 5  # Week 2 = 5 trading days
OUTPUT_FILE = "USTEC_week2_candles.csv"

# -----------------------------
# CONNECT TO MT5
# -----------------------------
if not mt5.initialize():
    print("❌ MT5 initialization failed")
    mt5.shutdown()
    exit()
print("✅ MT5 initialized")

# -----------------------------
# DEFINE START AND END DATES
# -----------------------------
# Week 2: 2025-10-13 to 2025-10-17
start_date = datetime(2025, 10, 13)
end_date = datetime(2025, 10, 17, 23, 59)

print(f"📅 Requesting candles from {start_date} to {end_date}...")

# -----------------------------
# EXPORT CANDLES
# -----------------------------
rates = mt5.copy_rates_range(SYMBOL, TIMEFRAME, start_date, end_date)

if rates is None or len(rates) == 0:
    print("⚠️ No candle data received. Check symbol or timeframe.")
else:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Exported {len(df)} candles to {OUTPUT_FILE}")

# -----------------------------
# SHUTDOWN MT5
# -----------------------------
mt5.shutdown()
print("🏁 Done.")
