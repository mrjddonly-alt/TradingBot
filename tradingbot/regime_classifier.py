import pandas as pd

class RegimeClassifier:
    def classify(self, df: pd.DataFrame) -> str:
        df['volatility'] = df['close'].rolling(window=20).std()
        df['ma_fast'] = df['close'].rolling(window=10).mean()
        df['ma_slow'] = df['close'].rolling(window=50).mean()

        latest = df.iloc[-1]
        if latest['volatility'] > df['volatility'].mean():
            return 'volatility'
        elif latest['ma_fast'] > latest['ma_slow']:
            return 'trend'
        else:
            return 'range'