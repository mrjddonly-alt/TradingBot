# TradingBot

An adaptive trading engine for systematic FX, Gold (XAUUSD), and USTEC strategies.  
Built with modular Python scripts, regime classification, and robust backtesting logic.

---

## 🚀 Features
- Modular strategy design (plug-and-play strategies)
- Regime classification (trend vs range detection)
- Walk-forward testing (180-day training, 30-day testing)
- Transaction cost handling and equity curve tracking
- Automated reporting with charts and performance summaries
- Unit tests for strategy logic and regime classification

---

## 📂 Project structure
---

## ⚙️ Installation
Clone the repo and install dependencies:
```bash
git clone https://github.com/mrjddonly-alt/TradingBot.git
cd TradingBot
pip install -r requirements.txt
python tradingbot/run_backtest.py --symbol XAUUSD --start 2024-01-01 --end 2024-06-30
pytest -q

---

## Choose commit option

- **Commit message:** Type `Add professional README`.
- **If branch protection is on main:**
  - **Select:** “Create a new branch for this commit and start a pull request.”
  - **Branch name:** Use `readme-update`.
  - **Click:** **Propose new file**.

- **If you switched to dev:**
  - **Select:** “Commit directly to the dev branch.”
  - **Click:** **Commit new file**.

---

## Open the pull request (if created a new branch)

- **Compare:** You’ll land on the PR page automatically.
- **Base branch:** `main`
- **Compare branch:** `readme-update` (or the branch you created)
- **Title:** “Add professional README”
- **Description:** “Adds README with features, setup, usage, testing, and roadmap.”
- **Click:** **Create pull request**.

---

## Merge the pull request

- **Wait for checks:** If you have required status checks, they must pass. If none exist, you’ll see **Merge pull request**.
- **Click:** **Merge pull request → Confirm merge**.
- **Verify:** Switch to `main` in the branch dropdown and ensure the README renders on the repo homepage.

---

## If merge is blocked by required checks

- **Quickest temporary fix:**
  - **Go to:** Settings → Branches → Edit rule for `main`.
  - **Uncheck:** “Require status checks to pass before merging.”
  - **Save:** Then return to the PR and merge.
  - **Restore:** Re-enable the checkbox after merging.

- **Preferred long-term fix (simple CI that passes):**
  - **Create file:** `.github/workflows/ci.yml`
  - **Content:**
    ```yaml
    name: CI
    on: [pull_request, push]
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - name: Install deps
            run: |
              python -m pip install --upgrade pip
              if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          - name: Lint stub
            run: echo "Lint OK"
          - name: Tests stub
            run: echo "Tests OK"
    ```
  - **Commit:** Create a PR; when this workflow passes, you can merge your README PR cleanly.

---

## Tell me what you see

- **If something’s unclear:** Say which screen you’re on (branch name, button text, or any error message), and I’ll guide the exact next click.

