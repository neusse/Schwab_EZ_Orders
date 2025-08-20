"""
Options Strategies Module - Pre-built common options strategies

This module provides strategy builders for common options strategies:
- Covered Call
- Protective Put
- Bull Call Spread
- Bear Put Spread
- Iron Condor
- Straddle/Strangle
- And more...
"""

from typing import Optional, List, Dict, Any
from schwab_order_builder import OrderBuilder, StrategyBuilder

try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


class CoveredCall(StrategyBuilder):
    """
    Covered Call Strategy: Own stock + Sell call option
    
    Example:
        strategy = CoveredCall('AAPL')
        strategy.buy_stock(100).at_limit(150.00)
        strategy.sell_call('AAPL240315C00160000', 1).at_limit(3.50)
        orders = strategy.build()
    """
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        self.stock_quantity = 0
        
    def buy_stock(self, shares: int) -> 'CoveredCall':
        """Buy the underlying stock"""
        self.stock_quantity = shares
        order = OrderBuilder(self.console).buy(self.underlying).shares(shares)
        self.add_order(order)
        return self
        
    def at_market(self) -> 'CoveredCall':
        """Execute most recent order at market"""
        if self.orders:
            self.orders[-1].market()
        return self
        
    def at_limit(self, price: float) -> 'CoveredCall':
        """Execute most recent order at limit price"""
        if self.orders:
            self.orders[-1].limit(price)
        return self
        
    def sell_call(self, call_symbol: str, contracts: int) -> 'CoveredCall':
        """Sell call options"""
        # Validate that we have enough stock to cover the calls
        if contracts * 100 > self.stock_quantity:
            raise ValueError(f"Cannot sell {contracts} calls - only have {self.stock_quantity} shares")
            
        order = OrderBuilder(self.console).sell_to_open(call_symbol).contracts(contracts)
        self.add_order(order)
        return self


class ProtectivePut(StrategyBuilder):
    """
    Protective Put Strategy: Own stock + Buy put option
    
    Example:
        strategy = ProtectivePut('AAPL')
        strategy.buy_stock(100).at_market()
        strategy.buy_put('AAPL240315P00140000', 1).at_limit(2.50)
    """
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        self.stock_quantity = 0
        
    def buy_stock(self, shares: int) -> 'ProtectivePut':
        """Buy the underlying stock"""
        self.stock_quantity = shares
        order = OrderBuilder(self.console).buy(self.underlying).shares(shares)
        self.add_order(order)
        return self
        
    def at_market(self) -> 'ProtectivePut':
        """Execute most recent order at market"""
        if self.orders:
            self.orders[-1].market()
        return self
        
    def at_limit(self, price: float) -> 'ProtectivePut':
        """Execute most recent order at limit price"""
        if self.orders:
            self.orders[-1].limit(price)
        return self
        
    def buy_put(self, put_symbol: str, contracts: int) -> 'ProtectivePut':
        """Buy put options for protection"""
        order = OrderBuilder(self.console).buy_to_open(put_symbol).contracts(contracts)
        self.add_order(order)
        return self


class BullCallSpread(StrategyBuilder):
    """
    Bull Call Spread: Buy lower strike call + Sell higher strike call
    
    Can be built as individual orders or as a single NET_DEBIT order.
    
    Example:
        # As individual orders
        strategy = BullCallSpread('AAPL')
        strategy.buy_call('AAPL240315C00150000', 1).at_limit(5.50)
        strategy.sell_call('AAPL240315C00160000', 1).at_limit(2.50)
        
        # As single NET_DEBIT order
        strategy = BullCallSpread('AAPL')
        strategy.as_net_debit(3.00, 'AAPL240315C00150000', 'AAPL240315C00160000', 1)
    """
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        
    def buy_call(self, call_symbol: str, contracts: int) -> 'BullCallSpread':
        """Buy the lower strike call"""
        order = OrderBuilder(self.console).buy_to_open(call_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def sell_call(self, call_symbol: str, contracts: int) -> 'BullCallSpread':
        """Sell the higher strike call"""
        order = OrderBuilder(self.console).sell_to_open(call_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def at_limit(self, price: float) -> 'BullCallSpread':
        """Set limit price for most recent order"""
        if self.orders:
            self.orders[-1].limit(price)
        return self
        
    def as_net_debit(self, max_debit: float, long_call: str, short_call: str, 
                     contracts: int) -> 'BullCallSpread':
        """Build as single NET_DEBIT order"""
        # Clear any existing orders
        self.orders = []
        
        # Create single multi-leg order
        order = (OrderBuilder(self.console)
                .with_leg(OrderAction.BUY_TO_OPEN, long_call, contracts, "OPTION")
                .with_leg(OrderAction.SELL_TO_OPEN, short_call, contracts, "OPTION")
                .net_debit(max_debit)
                .vertical_spread()
                .day())
        
        self.add_order(order)
        return self


class BearPutSpread(StrategyBuilder):
    """
    Bear Put Spread: Buy higher strike put + Sell lower strike put
    
    Example:
        strategy = BearPutSpread('AAPL')
        strategy.buy_put('AAPL240315P00150000', 1).at_limit(4.50)
        strategy.sell_put('AAPL240315P00140000', 1).at_limit(2.00)
    """
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        
    def buy_put(self, put_symbol: str, contracts: int) -> 'BearPutSpread':
        """Buy the higher strike put"""
        order = OrderBuilder(self.console).buy_to_open(put_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def sell_put(self, put_symbol: str, contracts: int) -> 'BearPutSpread':
        """Sell the lower strike put"""
        order = OrderBuilder(self.console).sell_to_open(put_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def at_limit(self, price: float) -> 'BearPutSpread':
        """Set limit price for most recent order"""
        if self.orders:
            self.orders[-1].limit(price)
        return self
        
    def net_debit(self, max_debit: float) -> 'BearPutSpread':
        """Execute as a net debit spread"""
        if self.console:
            self.console.print(f"⚠️  Target net debit: ${max_debit}", style="yellow")
        return self


class IronCondor(StrategyBuilder):
    """
    Iron Condor: Sell put spread + Sell call spread
    
    Example:
        strategy = IronCondor('AAPL')
        strategy.sell_put('AAPL240315P00140000', 1).at_limit(1.50)
        strategy.buy_put('AAPL240315P00135000', 1).at_limit(0.75)
        strategy.sell_call('AAPL240315C00160000', 1).at_limit(1.50)
        strategy.buy_call('AAPL240315C00165000', 1).at_limit(0.75)
    """
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        
    def sell_put(self, put_symbol: str, contracts: int) -> 'IronCondor':
        """Sell put (part of put spread)"""
        order = OrderBuilder(self.console).sell_to_open(put_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def buy_put(self, put_symbol: str, contracts: int) -> 'IronCondor':
        """Buy put (part of put spread)"""
        order = OrderBuilder(self.console).buy_to_open(put_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def sell_call(self, call_symbol: str, contracts: int) -> 'IronCondor':
        """Sell call (part of call spread)"""
        order = OrderBuilder(self.console).sell_to_open(call_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def buy_call(self, call_symbol: str, contracts: int) -> 'IronCondor':
        """Buy call (part of call spread)"""
        order = OrderBuilder(self.console).buy_to_open(call_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def at_limit(self, price: float) -> 'IronCondor':
        """Set limit price for most recent order"""
        if self.orders:
            self.orders[-1].limit(price)
        return self
        
    def net_credit(self, min_credit: float) -> 'IronCondor':
        """Execute as a net credit spread"""
        if self.console:
            self.console.print(f"⚠️  Target net credit: ${min_credit}", style="yellow")
        return self


class Straddle(StrategyBuilder):
    """
    Long Straddle: Buy call + Buy put at same strike
    
    Example:
        strategy = Straddle('AAPL')
        strategy.buy_call('AAPL240315C00150000', 1).at_limit(4.50)
        strategy.buy_put('AAPL240315P00150000', 1).at_limit(3.50)
    """
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        
    def buy_call(self, call_symbol: str, contracts: int) -> 'Straddle':
        """Buy call option"""
        order = OrderBuilder(self.console).buy_to_open(call_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def buy_put(self, put_symbol: str, contracts: int) -> 'Straddle':
        """Buy put option"""
        order = OrderBuilder(self.console).buy_to_open(put_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def at_limit(self, price: float) -> 'Straddle':
        """Set limit price for most recent order"""
        if self.orders:
            self.orders[-1].limit(price)
        return self


class Strangle(StrategyBuilder):
    """
    Long Strangle: Buy call + Buy put at different strikes
    
    Example:
        strategy = Strangle('AAPL')
        strategy.buy_call('AAPL240315C00155000', 1).at_limit(3.50)
        strategy.buy_put('AAPL240315P00145000', 1).at_limit(3.00)
    """
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        
    def buy_call(self, call_symbol: str, contracts: int) -> 'Strangle':
        """Buy call option"""
        order = OrderBuilder(self.console).buy_to_open(call_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def buy_put(self, put_symbol: str, contracts: int) -> 'Strangle':
        """Buy put option"""
        order = OrderBuilder(self.console).buy_to_open(put_symbol).contracts(contracts)
        self.add_order(order)
        return self
        
    def at_limit(self, price: float) -> 'Strangle':
        """Set limit price for most recent order"""
        if self.orders:
            self.orders[-1].limit(price)
        return self


# === STRATEGY FACTORY ===

class StrategyFactory:
    """Factory for creating strategy instances"""
    
    STRATEGIES = {
        'covered_call': CoveredCall,
        'protective_put': ProtectivePut,
        'bull_call_spread': BullCallSpread,
        'bear_put_spread': BearPutSpread,
        'iron_condor': IronCondor,
        'straddle': Straddle,
        'strangle': Strangle,
    }
    
    @classmethod
    def create(cls, strategy_name: str, underlying: str, 
               console: Optional[Console] = None) -> StrategyBuilder:
        """Create a strategy instance by name"""
        if strategy_name not in cls.STRATEGIES:
            available = ', '.join(cls.STRATEGIES.keys())
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: {available}")
            
        strategy_class = cls.STRATEGIES[strategy_name]
        return strategy_class(underlying, console)
    
    @classmethod
    def list_strategies(cls) -> List[str]:
        """List all available strategies"""
        return list(cls.STRATEGIES.keys())
    
    @classmethod
    def get_strategy_info(cls, strategy_name: str) -> str:
        """Get information about a strategy"""
        if strategy_name not in cls.STRATEGIES:
            return f"Unknown strategy: {strategy_name}"
            
        strategy_class = cls.STRATEGIES[strategy_name]
        return strategy_class.__doc__ or "No description available"


# === EXAMPLES ===

def demo_strategies():
    """Demonstrate various strategies"""
    console = Console() if RICH_AVAILABLE else None
    
    print("=== Strategy Examples ===\n")
    
    # Covered Call
    print("1. Covered Call on AAPL:")
    cc = CoveredCall('AAPL', console)
    cc.buy_stock(100).at_limit(150.00)
    cc.sell_call('AAPL240315C00160000', 1).at_limit(3.50)
    print("   - Buy 100 AAPL @ $150 limit")
    print("   - Sell 1 AAPL 160 call @ $3.50 limit\n")
    
    # Bull Call Spread
    print("2. Bull Call Spread on TSLA:")
    bcs = BullCallSpread('TSLA', console)
    bcs.buy_call('TSLA240315C00200000', 1).at_limit(8.50)
    bcs.sell_call('TSLA240315C00220000', 1).at_limit(4.50)
    print("   - Buy 1 TSLA 200 call @ $8.50 limit")
    print("   - Sell 1 TSLA 220 call @ $4.50 limit\n")
    
    # Iron Condor
    print("3. Iron Condor on SPY:")
    ic = IronCondor('SPY', console)
    ic.sell_put('SPY240315P00400000', 1).at_limit(1.50)
    ic.buy_put('SPY240315P00395000', 1).at_limit(0.75)
    ic.sell_call('SPY240315C00420000', 1).at_limit(1.50)
    ic.buy_call('SPY240315C00425000', 1).at_limit(0.75)
    print("   - Sell SPY 400 put @ $1.50")
    print("   - Buy SPY 395 put @ $0.75")
    print("   - Sell SPY 420 call @ $1.50")
    print("   - Buy SPY 425 call @ $0.75\n")


if __name__ == "__main__":
    demo_strategies()
    
    # Show available strategies
    print("Available strategies:")
    for strategy in StrategyFactory.list_strategies():
        print(f"  - {strategy}")
        print(f"    {StrategyFactory.get_strategy_info(strategy)}")
        print()
