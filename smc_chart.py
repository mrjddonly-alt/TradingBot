import MetaTrader5 as mt5
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime


# =========================
# CONNECT TO MT5
# =========================
def initialize_mt5():
    if not mt5.initialize():
        print("MT5 Initialize failed!")
        quit()
    else:
        print("✅ MT5 initialized successfully.")


def get_data(symbol="GBPUSD", timeframe=mt5.TIMEFRAME_M15, bars=480):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


# =========================
# SUPPLY & DEMAND ZONES
# =========================
def detect_zones(df, lookback=10):
    zones = []
    for i in range(lookback, len(df)):
        high = df["high"].iloc[i-lookback:i].max()
        low = df["low"].iloc[i-lookback:i].min()
        zones.append({"type": "supply", "high": high, "low": low * 1.001})
        zones.append({"type": "demand", "high": high * 0.999, "low": low})
    return zones


# =========================
# BOS & CHoCH
# =========================
def detect_bos_choch(df):
    bos_points = []
    choch_points = []
    for i in range(2, len(df)-2):
        # BOS detection (higher high)
        if df["high"].iloc[i] > df["high"].iloc[i-2] and df["high"].iloc[i] > df["high"].iloc[i+2]:
            bos_points.append((df["time"].iloc[i], df["high"].iloc[i]))

        # CHoCH detection (lower low)
        if df["low"].iloc[i] < df["low"].iloc[i-2] and df["low"].iloc[i] < df["low"].iloc[i+2]:
            choch_points.append((df["time"].iloc[i], df["low"].iloc[i]))

    return bos_points, choch_points


# =========================
# ENTRY SIGNALS
# =========================
def detect_entries(df, zones, bos_points, choch_points):
    entries = []
    for i in range(len(df)):
        price = df["close"].iloc[i]

        for z in zones:
            # Buy in demand zone
            if z["type"] == "demand" and z["low"] <= price <= z["high"]:
                if any(t <= df["time"].iloc[i] for t, _ in bos_points + choch_points):
                    entries.append(("buy", df["time"].iloc[i], price))

            # Sell in supply zone
            if z["type"] == "supply" and z["low"] <= price <= z["high"]:
                if any(t <= df["time"].iloc[i] for t, _ in bos_points + choch_points):
                    entries.append(("sell", df["time"].iloc[i], price))

    return entries


# =========================
# PLOT CHART
# =========================
def plot_chart(df, zones, bos_points, choch_points, entries):
    """
    Plots chart with candles, zones, BOS/CHoCH, and entries.
    """
    fig, ax = plt.subplots(figsize=(16, 8))

    # Candlesticks
    mpf.plot(
        df.set_index("time"),
        type="candle",
        ax=ax,
        style="charles",
        show_nontrading=True
    )

    # Zones
    for z in zones:
        color = "green" if z["type"] == "demand" else "red"
        ax.axhspan(z["low"], z["high"], color=color, alpha=0.15)

    # BOS & CHoCH
    for t, p in bos_points:
        ax.scatter(t, p, color="blue", marker="o", s=100, edgecolor="black", linewidth=0.7, label="BOS")
    for t, p in choch_points:
        ax.scatter(t, p, color="orange", marker="o", s=100, edgecolor="black", linewidth=0.7, label="CHoCH")

    # Entries
    for entry_type, t, p in entries:
        if entry_type == "buy":
            ax.scatter(t, p, color="lime", marker="^", s=150, edgecolor="black", linewidth=0.7, label="Buy")
        else:
            ax.scatter(t, p, color="red", marker="v", s=150, edgecolor="black", linewidth=0.7, label="Sell")

    plt.title("GBPUSD 15M - Supply/Demand, BOS, CHoCH, Entries")
    plt.grid()
    plt.show()


# =========================
# MAIN SCRIPT
# =========================
if __name__ == "__main__":
    initialize_mt5()
    df = get_data("GBPUSD", mt5.TIMEFRAME_M15, 480)
    zones = detect_zones(df)
    bos_points, choch_points = detect_bos_choch(df)
    entries = detect_entries(df, zones, bos_points, choch_points)
    plot_chart(df, zones, bos_points, choch_points, entries)
    mt5.shutdown()
