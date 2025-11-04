import MetaTrader5 as mt5
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import time

# =========================
# SETTINGS
# =========================
SYMBOL = "GBPUSD"
TIMEFRAME = mt5.TIMEFRAME_M15
BARS = 480
REFRESH_SECONDS = 30  # Auto-refresh interval
IMPULSE_FACTOR = 1.5  # Multiplier to detect strong moves

# =========================
# FETCH DATA FROM MT5
# =========================
def fetch_mt5_data(symbol, timeframe, bars):
    if not mt5.initialize():
        raise RuntimeError("MT5 initialization failed")

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        raise RuntimeError("Failed to get data from MT5")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

# =========================
# DETECT SWINGS
# =========================
def find_swings(df, lookback=2):
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(df)-lookback):
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]
        if high == max(df["high"].iloc[i-lookback:i+lookback+1]):
            swing_highs.append((df["time"].iloc[i], high))
        if low == min(df["low"].iloc[i-lookback:i+lookback+1]):
            swing_lows.append((df["time"].iloc[i], low))

    return swing_highs, swing_lows

# =========================
# DETECT BOS & CHoCH
# =========================
def detect_bos_choch(swing_highs, swing_lows):
    bos_points = []
    choch_points = []
    trend = None

    for i in range(1, len(swing_highs)):
        if swing_highs[i][1] > swing_highs[i-1][1]:
            if trend == "down":
                choch_points.append(swing_highs[i])
            bos_points.append(swing_highs[i])
            trend = "up"

    for i in range(1, len(swing_lows)):
        if swing_lows[i][1] < swing_lows[i-1][1]:
            if trend == "up":
                choch_points.append(swing_lows[i])
            bos_points.append(swing_lows[i])
            trend = "down"

    return bos_points, choch_points

# =========================
# DETECT LIQUIDITY POOLS
# =========================
def detect_liquidity_pools(swing_highs, swing_lows, tolerance=0.0005):
    liquidity_highs = []
    liquidity_lows = []

    for i in range(len(swing_highs)-1):
        if abs(swing_highs[i][1] - swing_highs[i+1][1]) <= tolerance:
            liquidity_highs.append(swing_highs[i])
            liquidity_highs.append(swing_highs[i+1])

    for i in range(len(swing_lows)-1):
        if abs(swing_lows[i][1] - swing_lows[i+1][1]) <= tolerance:
            liquidity_lows.append(swing_lows[i])
            liquidity_lows.append(swing_lows[i+1])

    liquidity_highs = list(set(liquidity_highs))
    liquidity_lows = list(set(liquidity_lows))

    return liquidity_highs, liquidity_lows

# =========================
# DETECT FAIR VALUE GAPS
# =========================
def detect_fvgs(df):
    fvg_zones = []

    for i in range(2, len(df)):
        c1 = df.iloc[i-2]
        c3 = df.iloc[i]

        if c3["low"] > c1["high"]:  # Bullish FVG
            fvg_zones.append((c1["time"], c3["time"], c1["high"], c3["low"], "bullish"))
        if c3["high"] < c1["low"]:  # Bearish FVG
            fvg_zones.append((c1["time"], c3["time"], c3["high"], c1["low"], "bearish"))

    return fvg_zones

# =========================
# DETECT SUPPLY & DEMAND ZONES (EXTENDED)
# =========================
def detect_supply_demand(df):
    zones = []
    avg_range = df["high"] - df["low"]
    avg_candle = avg_range.mean()

    for i in range(2, len(df)-2):
        # Demand Zone: Big bullish impulse
        if df["close"].iloc[i+1] > df["high"].iloc[i] + avg_candle * IMPULSE_FACTOR:
            zones.append({
                "time": df["time"].iloc[i],
                "low": df["low"].iloc[i],
                "high": df["high"].iloc[i],
                "type": "demand",
                "valid": True
            })

        # Supply Zone: Big bearish impulse
        if df["close"].iloc[i+1] < df["low"].iloc[i] - avg_candle * IMPULSE_FACTOR:
            zones.append({
                "time": df["time"].iloc[i],
                "low": df["low"].iloc[i],
                "high": df["high"].iloc[i],
                "type": "supply",
                "valid": True
            })

    # Invalidate zones if price later fully breaks them
    for z in zones:
        if z["type"] == "demand" and (df["close"] < z["low"]).any():
            z["valid"] = False
        if z["type"] == "supply" and (df["close"] > z["high"]).any():
            z["valid"] = False

    return zones

# =========================
# PLOT SUPPLY/DEMAND ZONES
# =========================
def plot_supply_demand(ax, df, zones):
    last_time = df["time"].iloc[-1]
    for z in zones:
        if not z.get("valid", True):
            continue
        color = "green" if z["type"] == "demand" else "red"
        ax.add_patch(plt.Rectangle(
            (z["time"], z["low"]),
            last_time - z["time"],
            z["high"] - z["low"],
            facecolor=color,
            alpha=0.18,
            edgecolor=color,
            linewidth=0.8
        ))

# =========================
# PLOT CHART
# =========================
def plot_chart(df, bos_points, choch_points, liq_highs, liq_lows, fvgs, zones):
    plt.clf()
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_title(f"{SYMBOL} M15 - SMC with Supply/Demand", fontsize=14, fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")

    # Candlesticks
    for i in range(len(df)):
        color = "green" if df["close"].iloc[i] > df["open"].iloc[i] else "red"
        ax.plot([df["time"].iloc[i], df["time"].iloc[i]], [df["low"].iloc[i], df["high"].iloc[i]], color="black")
        ax.add_patch(plt.Rectangle(
            (df["time"].iloc[i], min(df["open"].iloc[i], df["close"].iloc[i])),
            pd.Timedelta(minutes=15),
            abs(df["close"].iloc[i] - df["open"].iloc[i]),
            color=color
        ))

    # BOS
    for t, p in bos_points:
        ax.scatter(t, p, color="blue", marker="^", s=100)

    # CHoCH
    for t, p in choch_points:
        ax.scatter(t, p, color="orange", marker="v", s=100)

    # Liquidity Pools
    for _, p in liq_highs:
        ax.axhline(y=p, color="purple", linestyle="--", alpha=0.7)
    for _, p in liq_lows:
        ax.axhline(y=p, color="brown", linestyle="--", alpha=0.7)

    # FVG Zones
    for start, end, high, low, fvg_type in fvgs:
        color = "yellow" if fvg_type == "bullish" else "gray"
        ax.add_patch(plt.Rectangle(
            (start, low), end - start, high - low, facecolor=color, alpha=0.3
        ))

    # Supply/Demand Zones
    plot_supply_demand(ax, df, zones)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d, %H:%M'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.pause(0.1)

# =========================
# MAIN (AUTO-REFRESH)
# =========================
def main():
    plt.ion()
    while True:
        df = fetch_mt5_data(SYMBOL, TIMEFRAME, BARS)
        swing_highs, swing_lows = find_swings(df)
        bos_points, choch_points = detect_bos_choch(swing_highs, swing_lows)
        liq_highs, liq_lows = detect_liquidity_pools(swing_highs, swing_lows)
        fvgs = detect_fvgs(df)
        zones = detect_supply_demand(df)
        plot_chart(df, bos_points, choch_points, liq_highs, liq_lows, fvgs, zones)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Chart updated.")
        time.sleep(REFRESH_SECONDS)

if __name__ == "__main__":
    main()
