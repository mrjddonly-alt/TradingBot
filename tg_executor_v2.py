"""
Trading Geek Executor Bot v2
Executes trades using Smart Money Concepts (SMC) strategy.
Fully combined with TradeExecutor for safe MT5 execution.
"""

import MetaTrader5 as mt5
import pandas as pd
import time
import logging
from datetime import datetime

# =========================
# LOGGING SETUP
# =========================
logging.basicConfig(
    filename='tg_bot_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =========================
# TRADE EXECUTOR CLASS
# =========================
class TradeExecutor:
    def __init__(self, symbol, lot=0.1, sl_points=200, tp_points=400, comment="TG Bot Trade"):
        self.symbol = symbol
        self.lot = lot
        self.sl_points = sl_points
        self.tp_points = tp_points
        self.comment = comment

        # Ensure symbol is available
        if not mt5.symbol_select(self.symbol, True):
            logging.error(f"Failed to select symbol: {self.symbol}")
            raise RuntimeError(f"Failed to select symbol: {self.symbol}")
        logging.info(f"TradeExecutor ready for {self.symbol}")

    def place_order(self, order_type="buy"):
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logging.error(f"No tick data available for {self.symbol}")
            return False

        price = tick.ask if order_type == "buy" else tick.bid
        point = mt5.symbol_info(self.symbol).point
        deviation = 10

        sl = price - self.sl_points * point if order_type == "buy" else price + self.sl_points * point
        tp = price + self.tp_points * point if order_type == "buy" else price - self.tp_points * point

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": deviation,
            "magic": 234000,
            "comment": self.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed ({order_type.upper()}): {result}")
            return False

        logging.info(f"Order placed successfully ({order_type.upper()}): {result}")
        return True

# =========================
# TRADING GEEK BOT CLASS
# =========================
class TradingGeekBot:
    def __init__(self, symbol="GBPUSD", lot=0.1, sl_points=200, tp_points=400, mode="live"):
        self.symbol = symbol
        self.mode = mode
        self.executor = None

        # Initialize MT5 safely
        if not mt5.initialize():
            logging.error(f"MT5 initialization failed: {mt5.last_error()}")
            raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
        logging.info(f"Connected to MT5 - Mode: {self.mode}")
        print(f"Connected to MT5 - Mode: {self.mode}")

        # Initialize TradeExecutor
        try:
            self.executor = TradeExecutor(
                symbol=self.symbol,
                lot=lot,
                sl_points=sl_points,
                tp_points=tp_points,
                comment="TG Bot Trade"
            )
            logging.info("TradeExecutor initialized successfully")
        except Exception as e:
            logging.error(f"TradeExecutor initialization failed: {e}")
            raise RuntimeError(f"TradeExecutor initialization failed: {e}")

    def get_data(self, timeframe=mt5.TIMEFRAME_M1, bars=100):
        """Fetch recent price data"""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, bars)
        if rates is None:
            logging.error(f"Failed to fetch data for {self.symbol}")
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def trading_geek_strategy(self, df):
        """Simple SMC strategy placeholder"""
        if df.empty:
            return None
        last = df.iloc[-1]
        if last['close'] > last['open']:
            return "buy"
        elif last['close'] < last['open']:
            return "sell"
        return None

    def run(self):
        """Main bot loop"""
        logging.info("Starting Trading Geek Bot main loop")
        while True:
            df = self.get_data()
            signal = self.trading_geek_strategy(df)

            if signal:
                logging.info(f"Signal generated: {signal.upper()}")
                print(f"Signal: {signal.upper()}")
                if self.mode == "live" and self.executor:
                    success = self.executor.place_order(order_type=signal)
                    if success:
                        logging.info(f"{signal.upper()} order placed successfully")
                    else:
                        logging.error(f"{signal.upper()} order failed")
                else:
                    logging.info(f"[BACKTEST] Would place {signal.upper()} trade")
                    print(f"[BACKTEST] Would place {signal.upper()} trade")

            time.sleep(60)  # Run every 1 minute

# =========================
# MAIN EXECUTION
# =========================
if __name__ == "__main__":
    try:
        bot = TradingGeekBot(symbol="GBPUSD", lot=0.1, sl_points=200, tp_points=400, mode="live")
        bot.run()
    finally:
        mt5.shutdown()
        logging.info("MT5 shutdown successfully")
        print("MT5 shutdown successfully")
