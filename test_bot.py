import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

print("✅ Libraries are working!")

# Example: connect to Binance exchange (public data, no API key needed yet)
exchange = ccxt.binance()
markets = exchange.load_markets()

print("Number of markets on Binance:", len(markets))
