import MetaTrader5 as mt5
from datetime import datetime

class TradeExecutor:
    def __init__(self, symbol, lot=0.1, sl_points=200, tp_points=400):
        """
        TradeExecutor handles placing trades on MT5.

        Args:
            symbol (str): Trading symbol (e.g., "GBPUSD")
            lot (float): Lot size for trades
            sl_points (int): Stop Loss in points
            tp_points (int): Take Profit in points
        """
        self.symbol = symbol
        self.lot = lot
        self.sl_points = sl_points
        self.tp_points = tp_points

    def place_order(self, order_type="buy"):
        """
        Place a trade on MT5.
        Args:
            order_type (str): "buy" or "sell"
        Returns:
            result (mt5.OrderSendResult): The MT5 order send result
        """

        # Get symbol price data
        symbol_info = mt5.symbol_info_tick(self.symbol)
        if symbol_info is None:
            print(f"❌ Symbol {self.symbol} not found. Check your MT5 symbols list.")
            return None

        # Get price depending on order type
        price = symbol_info.ask if order_type.lower() == "buy" else symbol_info.bid

        # Calculate SL and TP levels
        if order_type.lower() == "buy":
            sl_price = price - self.sl_points * 0.0001
            tp_price = price + self.tp_points * 0.0001
            order_type_mt5 = mt5.ORDER_TYPE_BUY
        else:
            sl_price = price + self.sl_points * 0.0001
            tp_price = price - self.tp_points * 0.0001
            order_type_mt5 = mt5.ORDER_TYPE_SELL

        # Prepare the order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": order_type_mt5,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 10,
            "magic": 123456,  # Unique ID for this bot
            "comment": "Bot trade",
            "type_filling": mt5.ORDER_FILLING_FOK,
            "type_time": mt5.ORDER_TIME_GTC,
        }

        # Send the order
        result = mt5.order_send(request)

        # Check the result
        if result is None:
            print("❌ Order failed: No response from MT5.")
            return None
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Order failed, retcode={result.retcode}")
            print(result)
            return None

        print(f"✅ Order placed successfully! Ticket: {result.order}")
        return result
