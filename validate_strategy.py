pimport pandas as pd
import glob
import numpy as np

# ==============================================================
# STRATEGY VALIDATION TOOL — ROBUSTNESS TEST
# ==============================================================
# Looks for all files matching "USTEC_trades*.csv"
# and compares metrics across datasets to check stability.
# ==============================================================

def analyze_file(file):
    df = pd.read_csv(file)
    if 'timestamp_entry' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp_entry'])
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    else:
        raise ValueError("No timestamp column found")

    df['date_only'] = df['timestamp'].dt.date

    summary = df.groupby('date_only').agg(
        num_trades=('timestamp', 'count'),
        wins=('outcome', lambda x: (x == 'TP').sum()),
        total_pips=('result_pips', 'sum'),
    )
    summary['profit_per_trade'] = summary['total_pips'] / summary['num_trades']
    summary['win_rate'] = summary['wins'] / summary['num_trades']
    return summary


# --------------------------------------------------------------
# Load all matching trade files
# --------------------------------------------------------------
files = sorted(glob.glob("USTEC_trades*.csv"))
if not files:
    print("❌ No trade files found (expected e.g. USTEC_trades.csv, USTEC_trades_week2.csv).")
    exit()

print(f"📂 Found {len(files)} trade files:")
for f in files:
    print("  •", f)

# --------------------------------------------------------------
# Compute metrics for each file
# --------------------------------------------------------------
reports = []
for file in files:
    try:
        summary = analyze_file(file)
        avg_win_rate = summary['win_rate'].mean()
        avg_profit = summary['profit_per_trade'].mean()
        total_pips = summary['total_pips'].sum()
        num_trades = summary['num_trades'].sum()

        reports.append({
            "file": file,
            "avg_win_rate": round(avg_win_rate * 100, 2),
            "avg_profit_per_trade": round(avg_profit, 3),
            "total_pips": round(total_pips, 2),
            "num_trades": int(num_trades),
        })
    except Exception as e:
        print(f"⚠️ Could not analyze {file}: {e}")

# --------------------------------------------------------------
# Combine results into a comparison table
# --------------------------------------------------------------
if reports:
    df_compare = pd.DataFrame(reports)
    print("\n📊 STRATEGY VALIDATION SUMMARY:")
    print(df_compare.to_string(index=False))

    # ----------------------------------------------------------
    # Robustness Evaluation
    # ----------------------------------------------------------
    mean_win = df_compare['avg_win_rate'].mean()
    std_win = df_compare['avg_win_rate'].std()
    mean_profit = df_compare['avg_profit_per_trade'].mean()

    print("\n🔍 Robustness Check:")
    print(f"• Average Win Rate: {mean_win:.2f}% ± {std_win:.2f}")
    print(f"• Average Profit/Trade: {mean_profit:.3f}")

    # Decision logic
    if mean_win >= 55 and mean_win <= 65 and std_win <= 5:
        print("✅ Strategy appears STABLE across datasets (ready for deeper validation or automation).")
    elif mean_win < 55:
        print("⚠️ Strategy underperforming — needs optimization before automation.")
    else:
        print("⚠️ Strategy unstable — win rate too variable or above realistic threshold.")
else:
    print("❌ No valid reports generated.")
ython -c "import pandas as pd; print(pd.read_csv('backtest_results.csv').head())"
