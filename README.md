# TradingBot

An adaptive trading engine for systematic FX, Gold (XAUUSD), and USTEC strategies.
Built with modular Python, regime classification, backtesting, and transparent reporting.

---

## 🚀 Features
- **Modular strategies:** Plug-and-play strategy modules with a router.
- **Regime classification:** Detect trend vs. range regimes for adaptive logic.
- **Walk-forward testing:** Train/test windows for realistic evaluation.
- **Costs & equity tracking:** Transaction costs and equity curve outputs.
- **Reporting:** Summaries, metrics, and chart exports.
- **Tests:** Unit tests for strategies and classification components.

---

## 📂 Project structure
---

## ⚙️ Installation
```bash
git clone https://github.com/<your-username>/TradingBot.git
cd TradingBot
pip install -r requirements.txt
python tradingbot/run_backtest.py --symbol USTEC --start 2025-10-01 --end 2025-11-01
pytest -q

---

## Final checks and tidy-up

- **Confirm protection:** Settings → Branches → ensure rules are active on `main` (and `dev` if desired).
- **Auto-delete merged branches (optional):**
  - Settings → General → Pull Requests → enable **Automatically delete head branches**.
- **Visibility:** Switch to `main` and confirm the new README shows.

---

If any screen looks unfamiliar or blocks you, tell me exactly what you see (branch names, button labels, or warning text), and I’ll guide the precise next click.
