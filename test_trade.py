import MetaTrader5 as mt5
from trade_executor import TradeExecutor

# Connect to MT5
if not mt5.initialize():
    print("❌ MT5 initialization failed:", mt5.last_error())
    quit()
print("✅ Connected to MT5")

# Create executor and test placing an order
executor = TradeExecutor("GBPUSD", lot=0.1, sl_points=200, tp_points=400)
executor.place_order(order_type="buy")

# Shutdown MT5 connection
mt5.shutdown()
