# fx_gold_engine.py
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from pypfopt.hierarchical_portfolio import HRPOpt

# -----------------------------
# Config (you can tweak these)
# -----------------------------
SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "XAUUSD=X"]
TRAIN_DAYS = 180
TEST_DAYS = 30
COST = 0.0002          # 2 bps per trade
TARGET_VOL = 0.01      # target daily vol ~1%
KILL_SWITCH_DD = -0.20 # stop if drawdown worse than -20%

# -----------------------------
# Data
# -----------------------------
prices = yf.download(SYMBOLS, start="2015-01-01", end="2023-01-01")["Close"].dropna()
returns = prices.pct_change().dropna()

# -----------------------------
# Kill-Switch
# -----------------------------
def apply_kill_switch(equity_curve, max_dd=-0.20):
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    breach = drawdown < max_dd
    if breach.any():
        stop_idx = breach.idxmax()
        equity_curve.loc[stop_idx:] = equity_curve.loc[stop_idx]
    return equity_curve

# -----------------------------
# Costs + Vol Targeting
# -----------------------------
def apply_costs_and_voltarget(asset_returns, signals, cost=COST, target_vol=TARGET_VOL, lookback=20):
    strat_ret = signals.shift(1).fillna(0) * asset_returns
    trades = signals.diff().abs().fillna(0)
    strat_ret -= trades * cost
    rolling_vol = strat_ret.rolling(lookback).std()
    scaling = target_vol / rolling_vol
    scaling = scaling.replace([np.inf, -np.inf], 0).fillna(0)
    return strat_ret * scaling

# -----------------------------
# Strategies
# -----------------------------
class Strategy:
    def __init__(self, name): self.name = name
    def generate_signals(self, series): raise NotImplementedError

class SMACrossover(Strategy):
    def __init__(self, short=20, long=100):
        super().__init__(f"SMA({short},{long})")
        self.short, self.long = short, long
    def generate_signals(self, series):
        sma_s = series.rolling(self.short).mean()
        sma_l = series.rolling(self.long).mean()
        return (sma_s > sma_l).astype(int).shift(1).fillna(0)

class RSI(Strategy):
    def __init__(self, period=14, overbought=70, oversold=30):
        super().__init__(f"RSI({period})")
        self.period, self.overbought, self.oversold = period, overbought, oversold
    def generate_signals(self, series):
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(self.period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.period).mean()
        rs = gain / (loss.replace(0, np.nan))
        rsi = 100 - (100 / (1 + rs))
        sig = pd.Series(0, index=series.index)
        sig[rsi < self.oversold] = 1
        sig[rsi > self.overbought] = -1
        return sig.shift(1).fillna(0)

# -----------------------------
# Walk-Forward (per-asset strategies)
# -----------------------------
def walkforward_per_asset(prices_df, strategy, window_size=TRAIN_DAYS, test_size=TEST_DAYS, max_dd=KILL_SWITCH_DD):
    start, end = 0, len(prices_df)
    portfolio_curve = []

    while start + window_size + test_size <= end:
        test_prices = prices_df.iloc[start+window_size:start+window_size+test_size]
        test_returns = test_prices.pct_change().dropna()

        strat_returns = []
        for col in prices_df.columns:
            signals = strategy.generate_signals(test_prices[col])
            signals = signals.reindex(test_returns.index).fillna(0)
            asset_ret = apply_costs_and_voltarget(test_returns[col], signals)
            strat_returns.append(asset_ret)

        strat_matrix = pd.concat(strat_returns, axis=1)
        strat_matrix.columns = prices_df.columns
        port_ret = strat_matrix.mean(axis=1)
        portfolio_curve.extend(port_ret.cumsum().tolist())
        start += test_size

    idx = prices_df.index[window_size:window_size+len(portfolio_curve)]
    eq = pd.Series(portfolio_curve, index=idx, name=strategy.name)
    return apply_kill_switch(eq, max_dd=max_dd)

# -----------------------------
# Walk-Forward HRP (portfolio-native)
# -----------------------------
def walkforward_hrp(returns_df, window_size=TRAIN_DAYS, test_size=TEST_DAYS, target_vol=TARGET_VOL, max_dd=KILL_SWITCH_DD):
    start, end = 0, len(returns_df)
    portfolio_curve = []

    while start + window_size + test_size <= end:
        train = returns_df.iloc[start:start+window_size]
        test = returns_df.iloc[start+window_size:start+window_size+test_size]

        hrp = HRPOpt(train)
        weights = pd.Series(hrp.optimize()).reindex(returns_df.columns).fillna(0)

        port_ret = (test @ weights)
        rolling_vol = port_ret.rolling(20).std()
        scaling = target_vol / rolling_vol
        scaling = scaling.replace([np.inf, -np.inf], 0).fillna(0)
        port_ret = port_ret * scaling

        portfolio_curve.extend(port_ret.cumsum().tolist())
        start += test_size

    idx = returns_df.index[window_size:window_size+len(portfolio_curve)]
    eq = pd.Series(portfolio_curve, index=idx, name="HRP (Costs+VolTarget+KillSwitch)")
    return apply_kill_switch(eq, max_dd=max_dd)

# -----------------------------
# Metrics
# -----------------------------
def performance_metrics(equity_curve, rf=0.02, periods_per_year=252):
    daily_returns = equity_curve.diff().dropna()
    ann_return = daily_returns.mean() * periods_per_year
    ann_vol = daily_returns.std() * np.sqrt(periods_per_year)
    sharpe = (ann_return - rf) / ann_vol if ann_vol > 0 else np.nan
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_dd = drawdown.min()
    return {"Return": ann_return, "Volatility": ann_vol, "Sharpe": sharpe, "MaxDD": max_dd}

# -----------------------------
# Run
# -----------------------------
def main():
    sma = SMACrossover(20, 100)
    rsi = RSI(14, 70, 30)

    eq_sma = walkforward_per_asset(prices[SYMBOLS], sma)
    eq_rsi = walkforward_per_asset(prices[SYMBOLS], rsi)
    eq_hrp = walkforward_hrp(returns[SYMBOLS])

    metrics = {
        eq_sma.name: performance_metrics(eq_sma),
        eq_rsi.name: performance_metrics(eq_rsi),
        eq_hrp.name: performance_metrics(eq_hrp),
    }
    comparison = pd.DataFrame(metrics).T

    plt.figure(figsize=(12,6))
    eq_sma.plot(label=eq_sma.name)
    eq_rsi.plot(label=eq_rsi.name)
    eq_hrp.plot(label=eq_hrp.name)
    plt.title("Walk-Forward Portfolio Equity Curves (Train=180, Test=30, Costs+VolTarget+KillSwitch)")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.show()

    print("\nStrategy comparison (ranked by Sharpe):")
    print(comparison.sort_values("Sharpe", ascending=False))

if __name__ == "__main__":
    main()