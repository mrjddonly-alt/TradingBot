# tg_executor.py
"""
Trading-Geek style 1m scalper execution module
- Modes: "paper" (default) or "live"
- Backtest: iterate historical candles in paper mode
- Live: monitor M1 in realtime and send market orders using TradeExecutor if available
"""

import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
    MT5_PRESENT = True
except Exception:
    MT5_PRESENT = False

# Optional import: if you created trade_executor.py earlier, the module will use it
try:
    from trade_executor import TradeExecutor
    HAVE_TE = True
except Exception:
    HAVE_TE = False

# -------------------------
# CONFIG (Tune these)
# -------------------------
SYMBOL = "GBPUSD"
HIGHER_TF = mt5.TIMEFRAME_M15 if MT5_PRESENT else "M15"
ENTRY_TF = mt5.TIMEFRAME_M1 if MT5_PRESENT else "M1"
BARS_HIGHER_TF = 480
BARS_ENTRY_TF = 1200   # for backtest window if needed
MODE = "paper"         # "paper" or "live"
RISK_PCT = 0.5         # percent of account risk per trade (only used in live when using TradeExecutor.calc_lot_from_risk)
RR = 1.5               # take profit = SL * RR
BUFFER_PIPS = 1.5      # buffer beyond zone (in pips)
MIN_ZONE_WIDTH_PIPS = 2.0  # ignore tiny zones
MAX_OPEN_TRADES = 2
BACKTEST = False       # If True, run historic backtest on given dataframe

PIP_SCALE = 0.0001    # for GBPUSD usual pip

# -------------------------
# Helper utilities
# -------------------------
def pips_to_price(pips):
    return pips * PIP_SCALE

def price_to_pips(price_diff):
    return price_diff / PIP_SCALE

# -------------------------
# DATA FETCH (MT5) helpers
# -------------------------
def fetch_mt5_rates(symbol, timeframe, bars):
    if not MT5_PRESENT:
        raise RuntimeError("MetaTrader5 package not available")
    if not mt5.initialize():
        raise RuntimeError("MT5 initialization failed")
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        raise RuntimeError("No data returned")
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

# -------------------------
# SMC helpers (simple heuristics)
# -------------------------
def detect_swings(df, left=3, right=3):
    highs = df['high'].values
    lows = df['low'].values
    swings = []
    n = len(df)
    for i in range(left, n-right):
        is_h = True
        is_l = True
        for j in range(1, left+1):
            if highs[i] <= highs[i-j]: is_h = False
            if lows[i] >= lows[i-j]: is_l = False
        for j in range(1, right+1):
            if highs[i] <= highs[i+j]: is_h = False
            if lows[i] >= lows[i+j]: is_l = False
        if is_h: swings.append({'index': i, 'time': df['time'].iloc[i], 'type': 'H', 'price': highs[i]})
        if is_l: swings.append({'index': i, 'time': df['time'].iloc[i], 'type': 'L', 'price': lows[i]})
    return swings

def detect_order_blocks_and_fvgs(df):
    """
    Heuristic detection:
    - Order block candidate: candle that has a strong subsequent move in opposite direction
    - FVG (3-candle gap) detection as in SMC
    Returns lists: ob_zones, fvg_zones where zone is dict with low/high/start_time
    """
    obs = []
    fvgs = []
    n = len(df)
    for i in range(2, n-1):
        c1 = df.iloc[i-2]; c2 = df.iloc[i-1]; c3 = df.iloc[i]
        # FVG bullish
        if c3['low'] > c1['high']:
            fvgs.append({'type': 'bull', 'start': c1['time'], 'end': c3['time'], 'low': c1['high'], 'high': c3['low']})
        # FVG bearish
        if c3['high'] < c1['low']:
            fvgs.append({'type': 'bear', 'start': c1['time'], 'end': c3['time'], 'low': c3['high'], 'high': c1['low']})
    # simple OB detection: find candles where next N bars move substantially
    lookahead = 8
    avg_range = (df['high'] - df['low']).mean()
    for i in range(1, n-lookahead):
        base_h = df['high'].iloc[i]
        base_l = df['low'].iloc[i]
        future_max = df['high'].iloc[i+1:i+1+lookahead].max()
        future_min = df['low'].iloc[i+1:i+1+lookahead].min()
        # Bullish OB candidate (bearish candle then strong rally)
        if df['close'].iloc[i] < df['open'].iloc[i] and future_max > base_h + avg_range*0.5:
            obs.append({'type': 'bull', 'time': df['time'].iloc[i], 'low': base_l, 'high': base_h})
        # Bearish OB candidate (bullish candle then strong drop)
        if df['close'].iloc[i] > df['open'].iloc[i] and future_min < base_l - avg_range*0.5:
            obs.append({'type': 'bear', 'time': df['time'].iloc[i], 'low': base_l, 'high': base_h})
    return obs, fvgs

# -------------------------
# Zone filter: remove tiny zones
# -------------------------
def filter_zones(zones):
    filtered = []
    for z in zones:
        width_pips = price_to_pips(abs(z['high'] - z['low']))
        if width_pips >= MIN_ZONE_WIDTH_PIPS:
            filtered.append(z)
    return filtered

# -------------------------
# Entry detector (1m)
# -------------------------
def find_entries_1m(higher_df, entry_df):
    """
    Basic logic:
    - build zones from higher_df (OBs & FVGs)
    - determine higher timeframe trend by last BOS (simpler: slope of last N closes)
    - watch entry_df (1m) for price entering a zone and a confirmation candle closing in bias
    Returns list of candidate signals: dict {side, time, price, sl, tp, zone}
    """
    obs, fvgs = detect_order_blocks_and_fvgs(higher_df)
    all_zones = []
    for o in obs:
        all_zones.append({'type': 'OB_'+o['type'], 'low': o['low'], 'high': o['high'], 'time': o['time']})
    for f in fvgs:
        tag = 'FVG_bull' if f['type']=='bull' else 'FVG_bear'
        all_zones.append({'type': tag, 'low': f['low'], 'high': f['high'], 'time': f['start']})

    all_zones = filter_zones(all_zones)

    # trend: simple slope on higher timeframe
    closes = higher_df['close'].values
    trend = 'bull' if closes[-1] > closes[-10] else 'bear'

    signals = []
    # iterate entry candles; when price enters zone, check confirmation candle
    for i in range(2, len(entry_df)):
        close = entry_df['close'].iloc[i]
        t = entry_df['time'].iloc[i]
        prev_c = entry_df.iloc[i-1]
        # check zones
        for z in all_zones:
            if z['low'] <= close <= z['high']:
                # require bias match: if zone is bullish FVG or OB_bull expect buy when higher TF is bull
                want_buy = ('bull' in z['type'] and trend=='bull')
                want_sell = ('bear' in z['type'] and trend=='bear')
                # confirmation: current candle close > previous high for buy, or < prev low for sell
                if want_buy and close > prev_c['high']:
                    sl = z['low'] - pips_to_price(BUFFER_PIPS)
                    tp = close + (close - sl) * RR
                    signals.append({'side':'buy','time':t,'price':close,'sl':sl,'tp':tp,'zone':z})
                if want_sell and close < prev_c['low']:
                    sl = z['high'] + pips_to_price(BUFFER_PIPS)
                    tp = close - (sl - close) * RR
                    signals.append({'side':'sell','time':t,'price':close,'sl':sl,'tp':tp,'zone':z})
    return signals

# -------------------------
# Simple Backtester (paper)
# -------------------------
def backtest_on_data(higher_df, entry_df):
    signals = find_entries_1m(higher_df, entry_df)
    trades = []
    for s in signals:
        # simulate execution at s['price']; then scan future candles to see SL/TP
        entry_index = entry_df[entry_df['time'] == s['time']].index[0]
        for j in range(entry_index+1, len(entry_df)):
            hi = entry_df['high'].iloc[j]; lo = entry_df['low'].iloc[j]
            if s['side']=='buy':
                if lo <= s['sl']:
                    trades.append({'side':'buy','entry':s['price'],'exit':s['sl'],'result':'loss','pips':price_to_pips(s['sl']-s['price'])})
                    break
                if hi >= s['tp']:
                    trades.append({'side':'buy','entry':s['price'],'exit':s['tp'],'result':'win','pips':price_to_pips(s['tp']-s['price'])})
                    break
            else:
                if hi >= s['sl']:
                    trades.append({'side':'sell','entry':s['price'],'exit':s['sl'],'result':'loss','pips':price_to_pips(s['price']-s['sl'])})
                    break
                if lo <= s['tp']:
                    trades.append({'side':'sell','entry':s['price'],'exit':s['tp'],'result':'win','pips':price_to_pips(s['price']-s['tp'])})
                    break
    wins = sum(1 for t in trades if t['result']=='win')
    losses = len(trades)-wins
    print(f"Backtest signals: {len(trades)}, wins: {wins}, losses: {losses}")
    return trades

# -------------------------
# Live runner (paper/live)
# -------------------------
class TGRunner:
    def __init__(self, symbol=SYMBOL, mode='paper'):
        self.symbol = symbol
        self.mode = mode
        self.executor = None
        if self.mode=='live' and HAVE_TE:
            self.executor = TradeExecutor(symbol)
            self.executor.connect()
        elif self.mode=='live' and not HAVE_TE:
            raise RuntimeError("Live mode requested but trade_executor not found")

        # track opened trades for auto-close logic
        self.open_trades = []

    def shutdown(self):
        if self.executor: self.executor.disconnect()

    def run_once(self):
        # fetch higher tf and entry tf
        if MT5_PRESENT:
            higher_df = fetch_mt5_rates(self.symbol, HIGHER_TF, BARS_HIGHER_TF)
            entry_df = fetch_mt5_rates(self.symbol, ENTRY_TF, BARS_ENTRY_TF)
        else:
            raise RuntimeError("MT5 not installed/available in this environment.")

        signals = find_entries_1m(higher_df, entry_df)
        if not signals:
            print(f"[{datetime.now()}] No signals")
            return

        print(f"[{datetime.now()}] Signals found: {len(signals)}")
        for s in signals:
            # limit concurrent trades
            if len(self.open_trades) >= MAX_OPEN_TRADES:
                print("Max open trades reached, skipping")
                continue

            if self.mode == 'paper':
                # record paper trade
                self.open_trades.append({'side':s['side'],'entry':s['price'],'sl':s['sl'],'tp':s['tp'],'time':s['time'],'status':'open'})
                print("Paper trade logged:", s)
            else:
                # live execution: compute lot by risk % using TradeExecutor
                lot = self.executor.calc_lot_from_risk(account_risk_pct=RISK_PCT, stop_loss_pips=abs(price_to_pips(s['sl']-s['price'])))
                try:
                    if s['side']=='buy':
                        res = self.executor.market_buy(lot=lot, stop_loss_pips=abs(price_to_pips(s['sl']-s['price'])), take_profit_pips=abs(price_to_pips(s['tp']-s['price'])))
                    else:
                        res = self.executor.market_sell(lot=lot, stop_loss_pips=abs(price_to_pips(s['sl']-s['price'])), take_profit_pips=abs(price_to_pips(s['price']-s['tp'])))
                    print("Order result:", res)
                    self.open_trades.append({'side':s['side'],'entry':s['price'],'sl':s['sl'],'tp':s['tp'],'time':s['time'],'status':'open','order':res})
                except Exception as ex:
                    print("Order failed:", ex)

    def monitor_loop(self, interval_seconds=5):
        try:
            while True:
                self.run_once()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("Shutting down runner...")
            self.shutdown()

# -------------------------
# Run / Example usage
# -------------------------
if __name__ == "__main__":
    # Choose mode: "paper" or "live"
    runner = TGRunner(mode=MODE)
    if BACKTEST:
        # simple backtest example: pull higher tf and entry tf once and backtest on data
        if MT5_PRESENT:
            higher_df = fetch_mt5_rates(SYMBOL, HIGHER_TF, BARS_HIGHER_TF)
            entry_df = fetch_mt5_rates(SYMBOL, ENTRY_TF, BARS_ENTRY_TF)
            trades = backtest_on_data(higher_df, entry_df)
            print(trades[:10])
        else:
            print("MT5 not available for backtest in this environment.")
    else:
        runner.monitor_loop(interval_seconds=5)
