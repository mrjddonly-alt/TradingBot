import pandas as pd

# Load trades
trades = pd.read_csv("USTEC_Week4_trades.csv")

# Core stats
total_profit = trades['result_pips'].sum()
outcome_counts = trades['outcome'].value_counts()
num_trades = len(trades)
wins = (trades['result_pips'] > 0).sum()
win_rate = wins / num_trades * 100
expectancy = trades['result_pips'].mean()

# Print results
print(f"📊 Week 4 Analysis")
print(f"Total trades: {num_trades}")
print(f"Total net profit: {total_profit:.2f} points")
print("Outcome breakdown:")
print(outcome_counts)
print(f"Win rate: {win_rate:.2f}%")
print(f"Expectancy per trade: {expectancy:.2f} points")