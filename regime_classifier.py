import pandas as pd
import numpy as np

def classify_regime(df, atr_window=14, slope_window=10, atr_percentile=0.7, slope_threshold=2.0):
    df = df.copy()

    if 'atr' not in df.columns:
        high_low   = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close  = np.abs(df['low']  - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(atr_window).mean()

    df['vwap_slope'] = df['vwap'].diff(slope_window)
    df['atr_rolling'] = df['atr'].rolling(60).mean()
    atr_thresh = df['atr_rolling'].quantile(atr_percentile)

    df['regime'] = 'choppy'
    trending_mask = (df['atr_rolling'] > atr_thresh) & (df['vwap_slope'].abs() > slope_threshold)
    df.loc[trending_mask, 'regime'] = 'trending'

    return df