import pandas as pd
from .regime_classifier import RegimeClassifier
from .strategy_router import StrategyRouter

class Backtester:
    def __init__(self, df: pd.DataFrame, stop_loss=50, take_profit=100,
                 transaction_cost=2.0, initial_equity=10000):
        self.df = df
        self.router = StrategyRouter()
        self.classifier = RegimeClassifier()
        self.results = []
        self.trades = []
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.transaction_cost = transaction_cost
        self.equity = initial_equity
        self.equity_curve = []   # track balance over time

    def run_walk_forward(self, train_days=180, test_days=30):
        total_days = len(self.df)
        start = 0
        position = None
        entry_price = None

        while start + train_days + test_days <= total_days:
            train_df = self.df.iloc[start:start + train_days]
            test_df = self.df.iloc[start + train_days:start + train_days + test_days]

            for i in range(len(test_df)):
                window = pd.concat([train_df, test_df.iloc[:i+1]])
                regime = self.classifier.classify(window)
                data = test_df.iloc[i].to_dict()
                signal = self.router.route(regime, data)

                price = data['close']

                # --- Risk management checks ---
                if position == "LONG":
                    if price <= entry_price - self.stop_loss:
                        pnl = price - entry_price - self.transaction_cost
                        self.trades.append({"exit_date": test_df.index[i], "pnl": pnl, "reason": "STOP"})
                        self.equity += pnl
                        position, entry_price = None, None
                    elif price >= entry_price + self.take_profit:
                        pnl = price - entry_price - self.transaction_cost
                        self.trades.append({"exit_date": test_df.index[i], "pnl": pnl, "reason": "TP"})
                        self.equity += pnl
                        position, entry_price = None, None

                elif position == "SHORT":
                    if price >= entry_price + self.stop_loss:
                        pnl = entry_price - price - self.transaction_cost
                        self.trades.append({"exit_date": test_df.index[i], "pnl": pnl, "reason": "STOP"})
                        self.equity += pnl
                        position, entry_price = None, None
                    elif price <= entry_price - self.take_profit:
                        pnl = entry_price - price - self.transaction_cost
                        self.trades.append({"exit_date": test_df.index[i], "pnl": pnl, "reason": "TP"})
                        self.equity += pnl
                        position, entry_price = None, None

                # --- Signal handling ---
                if signal == "BUY" and position != "LONG":
                    if position == "SHORT":
                        pnl = entry_price - price - self.transaction_cost
                        self.trades.append({"exit_date": test_df.index[i], "pnl": pnl, "reason": "REVERSAL"})
                        self.equity += pnl
                    position, entry_price = "LONG", price

                elif signal == "SELL" and position != "SHORT":
                    if position == "LONG":
                        pnl = price - entry_price - self.transaction_cost
                        self.trades.append({"exit_date": test_df.index[i], "pnl": pnl, "reason": "REVERSAL"})
                        self.equity += pnl
                    position, entry_price = "SHORT", price

                # record signals + equity
                self.results.append({
                    'date': test_df.index[i],
                    'regime': regime,
                    'signal': signal,
                    'price': price,
                    'equity': self.equity
                })
                self.equity_curve.append({"date": test_df.index[i], "equity": self.equity})

            start += test_days

        # close any open position at the end
        if position == "LONG":
            pnl = self.df.iloc[-1]['close'] - entry_price - self.transaction_cost
            self.trades.append({"exit_date": self.df.index[-1], "pnl": pnl, "reason": "END"})
            self.equity += pnl
        elif position == "SHORT":
            pnl = entry_price - self.df.iloc[-1]['close'] - self.transaction_cost
            self.trades.append({"exit_date": self.df.index[-1], "pnl": pnl, "reason": "END"})
            self.equity += pnl

    def get_results(self):
        return pd.DataFrame(self.results)

    def get_trades(self):
        return pd.DataFrame(self.trades)

    def get_equity_curve(self):
        return pd.DataFrame(self.equity_curve)

    def get_summary(self):
        trades_df = self.get_trades()
        total_pnl = trades_df['pnl'].sum()
        avg_pnl = trades_df['pnl'].mean()
        win_rate = (trades_df['pnl'] > 0).mean()
        return {
            "final_equity": self.equity,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "win_rate": win_rate
        }