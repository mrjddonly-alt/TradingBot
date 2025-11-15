import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.strategy_vwap import VWAPStrategy
import pytest
def test_vwap_entry_signal():
    strategy = VWAPStrategy()
    mock_data = {
        'price': 1800,
        'vwap': 1795,
        'volume': 1000
    }
    signal = strategy.generate_signal(mock_data)
    assert signal in ['buy', 'sell', 'hold']