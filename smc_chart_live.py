import MetaTrader5 as mt5
import pandas as pd
import mplfinance as mpf
import matplotlib.patches as patches
import time

# ====== CONFIG ======
SYMBOL = "GBPUSD"
TIMEFRAME = mt5.TIMEFRAME_M15
BARS = 480
SWING_LEFT = 3
SWING_RIGHT = 3
REFRESH = 60  # seconds

# ====== MT5 DATA FETCH ======
def get_mt5_data():
    if not mt5.initialize():
        raise RuntimeError("MT5 initialize failed - check MT5 login.")
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, BARS)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        raise RuntimeError("No data from MT5.")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df[["time", "open", "high", "low", "close"]]

# ====== SWING DETECTION ======
def detect_swings(df, left=SWING_LEFT, right=SWING_RIGHT):
    highs = df["high"].values
    lows = df["low"].values
    swings = []
    n = len(df)
    for i in range(left, n-right):
        is_high = all(highs[i] > highs[i-j] for j in range(1, left+1)) and all(highs[i] > highs[i+j] for j in range(1, right+1))
        is_low = all(lows[i] < lows[i-j] for j in range(1, left+1)) and all(lows[i] < lows[i+j] for j in range(1, right+1))
        if is_high:
            swings.append({'index': i, 'time': df['time'].iloc[i], 'type': 'H', 'price': float(highs[i])})
        if is_low:
            swings.append({'index': i, 'time': df['time'].iloc[i], 'type': 'L', 'price': float(lows[i])})
    return swings

# ====== BOS / CHoCH DETECTION ======
def detect_bos_choch(swings):
    bos_events = []
    choch_events = []
    last_high, last_low = None, None
    trend = None
    for s in swings:
        if s['type'] == 'H':
            if last_high is None: last_high = s['price']; continue
            if s['price'] > last_high:
                bos_events.append({'time': s['time'], 'type': 'BOS_up', 'price': s['price']})
                if trend == 'down':
                    choch_events.append({'time': s['time'], 'type': 'CHoCH_up', 'price': s['price']})
                trend = 'up'
                last_high = s['price']
        else:
            if last_low is None: last_low = s['price']; continue
            if s['price'] < last_low:
                bos_events.append({'time': s['time'], 'type': 'BOS_down', 'price': s['price']})
                if trend == 'up':
                    choch_events.append({'time': s['time'], 'type': 'CHoCH_down', 'price': s['price']})
                trend = 'down'
                last_low = s['price']
    return bos_events, choch_events

# ====== SUPPLY & DEMAND DETECTION ======
def detect_supply_demand(df, swings):
    zones = []
    for s in swings:
        idx = s['index']
        if s['type'] == 'H':  # Possible supply zone
            if idx+2 < len(df):
                if df['close'].iloc[idx+2] < df['low'].iloc[idx+1]:  # Strong drop
                    zones.append({
                        'type': 'supply',
                        'start': df['time'].iloc[idx],
                        'end': df['time'].iloc[min(idx+5, len(df)-1)],
                        'high': df['high'].iloc[idx],
                        'low': df['low'].iloc[idx]
                    })
        if s['type'] == 'L':  # Possible demand zone
            if idx+2 < len(df):
                if df['close'].iloc[idx+2] > df['high'].iloc[idx+1]:  # Strong rally
                    zones.append({
                        'type': 'demand',
                        'start': df['time'].iloc[idx],
                        'end': df['time'].iloc[min(idx+5, len(df)-1)],
                        'high': df['high'].iloc[idx],
                        'low': df['low'].iloc[idx]
                    })
    return zones

# ====== PLOT ======
def plot_chart(df, bos, choch, zones):
    df_plot = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close'}).set_index('time')
    fig, axlist = mpf.plot(df_plot, type='candle', style='charles',
                           title=f"{SYMBOL} M15 - BOS/CHoCH + SD Zones", returnfig=True, figsize=(13,7))
    ax = axlist[0]

    # BOS/CHoCH markers
    for e in bos:
        color, marker = ('blue', '^') if e['type'] == 'BOS_up' else ('red', 'v')
        ax.plot(e['time'], e['price'], marker=marker, color=color, markersize=10)
    for e in choch:
        ax.plot(e['time'], e['price'], marker='D', color='orange', markersize=9)

    # Draw Supply/Demand Zones
    for z in zones:
        color = 'red' if z['type'] == 'supply' else 'green'
        alpha = 0.2
        rect = patches.Rectangle(
            (z['start'], z['low']), z['end'] - z['start'], z['high'] - z['low'],
            linewidth=1, edgecolor=color, facecolor=color, alpha=alpha
        )
        ax.add_patch(rect)

    mpf.show()

# ====== MAIN LOOP ======
def main():
    while True:
        df = get_mt5_data()
        swings = detect_swings(df)
        bos, choch = detect_bos_choch(swings)
        zones = detect_supply_demand(df, swings)
        print(f"{len(bos)} BOS | {len(choch)} CHoCH | {len(zones)} SD Zones")
        plot_chart(df, bos, choch, zones)
        time.sleep(REFRESH)

if __name__ == "__main__":
    main()
