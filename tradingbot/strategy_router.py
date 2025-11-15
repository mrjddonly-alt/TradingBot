from .strategies.strategy_vwap import VWAPStrategy
from .strategies.strategy_momentum import MomentumStrategy
from .strategies.strategy_smc import SMCStrategy

class StrategyRouter:
    def __init__(self):
        self.strategies = {
            'trend': VWAPStrategy(),
            'range': SMCStrategy(),
            'volatility': MomentumStrategy()
        }

    def route(self, regime, data):
        strategy = self.strategies.get(regime)
        if strategy:
            return strategy.generate_signal(data)
        else:
            return 'hold'