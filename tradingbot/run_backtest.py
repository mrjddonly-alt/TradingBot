import os
import pandas as pd
import matplotlib.pyplot as plt
from tradingbot.backtester import Backtester

# --- Resolve path to your CSV ---
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_path = os.path.join(base_dir, "data", "ustec.csv")

# --- Load data ---
df = pd.read_csv(data_path, parse_dates=['timestamp'], index_col='timestamp')

# --- Run backtest with risk management ---
bt = Backtester(df, stop_loss=50, take_profit=100)
bt.run_walk_forward(train_days=180, test_days=30)

# --- Show outputs ---
print("Signals (first 5 rows):")
print(bt.get_results().head())

print("\nTrades:")
print(bt.get_trades())

print("\nSummary:")
print(bt.get_summary())

# --- Plot trades ---
signals = bt.get_results()
trades = bt.get_trades()

plt.figure(figsize=(12,6))
df['close'].plot(label='Close Price', color='black')

# Plot BUY/SELL signals
buy_signals = signals[signals['signal'] == 'BUY']
sell_signals = signals[signals['signal'] == 'SELL']
plt.scatter(buy_signals['date'], buy_signals['price'], marker='^', color='green', label='BUY', alpha=0.7)
plt.scatter(sell_signals['date'], sell_signals['price'], marker='v', color='red', label='SELL', alpha=0.7)

# Plot trade exits by reason
for reason, color in [('TP','green'), ('STOP','red'), ('REVERSAL','blue'), ('END','gray')]:
    exits = trades[trades['reason'] == reason]
    plt.scatter(exits['exit_date'],
                df.loc[exits['exit_date'], 'close'],
                marker='o', color=color, label=reason, alpha=0.7)

plt.legend()
plt.title("Trade Visualization with Stop/TP Exits")
plt.xlabel("Date")
plt.ylabel("Price")
plt.show()
