import pandas as pd

class VWAPStrategy:
    def generate_signal(self, data):
        price = data.get('close')
        vwap = data.get('vwap')

        if vwap is None or pd.isna(vwap):
            return "HOLD"

        if price > vwap:
            return "BUY"
        elif price < vwap:
            return "SELL"
        else:
            return "HOLD"