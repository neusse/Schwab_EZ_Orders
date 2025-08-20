"""
Enhanced Schwab Order Builder - A more user-friendly wrapper for schwab-py orders

This module provides a fluent API for building Schwab orders with:
- Simplified method chaining
- Built-in validation and safeguards
- Common options strategies
- Template save/load functionality
- Rich console integration
"""

import json
import os
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

# Simplified enums for common use cases
class OrderAction:
    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_OPEN = "BUY_TO_OPEN"
    SELL_TO_CLOSE = "SELL_TO_CLOSE"
    SELL_TO_OPEN = "SELL_TO_OPEN"
    BUY_TO_CLOSE = "BUY_TO_CLOSE"
    SELL_SHORT = "SELL_SHORT"
    BUY_TO_COVER = "BUY_TO_COVER"

class TimeInForce:
    DAY = "DAY"
    GTC = "GOOD_TILL_CANCEL"  # Good Till Cancel
    IOC = "IMMEDIATE_OR_CANCEL"
    FOK = "FILL_OR_KILL"

class OrderPricing:
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    TRAILING_STOP_LIMIT = "TRAILING_STOP_LIMIT"
    NET_DEBIT = "NET_DEBIT"
    NET_CREDIT = "NET_CREDIT"
    NET_ZERO = "NET_ZERO"

class ComplexOrderStrategy:
    NONE = "NONE"
    COVERED = "COVERED"
    VERTICAL = "VERTICAL"
    BACK_RATIO = "BACK_RATIO"
    CALENDAR = "CALENDAR"
    DIAGONAL = "DIAGONAL"
    STRADDLE = "STRADDLE"
    STRANGLE = "STRANGLE"
    BUTTERFLY = "BUTTERFLY"
    CONDOR = "CONDOR"
    IRON_CONDOR = "IRON_CONDOR"
    CUSTOM = "CUSTOM"

class OrderStrategy:
    SINGLE = "SINGLE"
    OCO = "OCO"           # One Cancels Other
    TRIGGER = "TRIGGER"   # One Triggers Another

class StopPriceLinkBasis:
    MANUAL = "MANUAL"
    BASE = "BASE"
    TRIGGER = "TRIGGER"
    LAST = "LAST"
    BID = "BID"
    ASK = "ASK"
    MARK = "MARK"

class StopPriceLinkType:
    VALUE = "VALUE"
    PERCENT = "PERCENT"
    TICK = "TICK"

@dataclass
class OrderLeg:
    """Represents a single leg of an order"""
    action: str
    symbol: str
    quantity: int
    asset_type: str = "EQUITY"
    
class ValidationError(Exception):
    """Raised when order validation fails"""
    pass

class OrderBuilder:
    """
    Fluent API for building Schwab orders with validation and safeguards.
    
    Example usage:
        # Simple equity order
        order = OrderBuilder().buy('AAPL').shares(100).limit(150.50).day()
        
        # Options order
        order = OrderBuilder().sell_to_close('AAPL240119C00150000').contracts(1).limit(6.00)
        
        # With safeguards
        order = OrderBuilder().sell('AAPL').shares(1000).market().require_confirmation()
    """
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or (Console() if RICH_AVAILABLE else None)
        self.reset()
        
    def reset(self):
        """Reset the builder to initial state"""
        self.legs: List[OrderLeg] = []
        self.order_type = None
        self.price = None
        self.stop_price = None
        self.time_in_force = TimeInForce.DAY
        self.session = "NORMAL"
        self.require_confirm = False
        self.warnings: List[str] = []
        
        # Extended properties for complex orders
        self.complex_order_strategy = ComplexOrderStrategy.NONE
        self.order_strategy = OrderStrategy.SINGLE
        self.child_orders: List['OrderBuilder'] = []
        
        # Trailing stop properties
        self.stop_price_link_basis = None
        self.stop_price_link_type = None
        self.stop_price_offset = None
        
        return self
        
    # === BASIC ACTIONS ===
    
    def buy(self, symbol: str) -> 'OrderBuilder':
        """Start a buy order for the given symbol"""
        self._add_leg(OrderAction.BUY, symbol.upper())
        return self
        
    def sell(self, symbol: str) -> 'OrderBuilder':
        """Start a sell order for the given symbol"""
        self._add_leg(OrderAction.SELL, symbol.upper())
        return self
        
    def sell_short(self, symbol: str) -> 'OrderBuilder':
        """Start a short sell order"""
        self._add_leg(OrderAction.SELL_SHORT, symbol.upper())
        return self
        
    def buy_to_cover(self, symbol: str) -> 'OrderBuilder':
        """Start a buy to cover order"""
        self._add_leg(OrderAction.BUY_TO_COVER, symbol.upper())
        return self
        
    # === OPTIONS ACTIONS ===
    
    def buy_to_open(self, symbol: str) -> 'OrderBuilder':
        """Buy to open an options position"""
        self._add_leg(OrderAction.BUY_TO_OPEN, symbol.upper(), asset_type="OPTION")
        return self
        
    def sell_to_close(self, symbol: str) -> 'OrderBuilder':
        """Sell to close an options position"""
        self._add_leg(OrderAction.SELL_TO_CLOSE, symbol.upper(), asset_type="OPTION")
        return self
        
    def sell_to_open(self, symbol: str) -> 'OrderBuilder':
        """Sell to open an options position"""
        self._add_leg(OrderAction.SELL_TO_OPEN, symbol.upper(), asset_type="OPTION")
        return self
        
    def buy_to_close(self, symbol: str) -> 'OrderBuilder':
        """Buy to close an options position"""
        self._add_leg(OrderAction.BUY_TO_CLOSE, symbol.upper(), asset_type="OPTION")
        return self
        
    # === MULTI-LEG HELPERS ===
    
    def add_leg(self, action: str, symbol: str, asset_type: str = "EQUITY") -> 'OrderBuilder':
        """Add a leg to multi-leg order"""
        self._add_leg(action, symbol.upper(), asset_type)
        return self
        
    def with_leg(self, action: str, symbol: str, quantity: int, 
                 asset_type: str = "EQUITY") -> 'OrderBuilder':
        """Add a complete leg in one call"""
        self._add_leg(action, symbol.upper(), asset_type)
        self.legs[-1].quantity = quantity
        return self
        
    # === QUANTITY ===
    
    def shares(self, quantity: int) -> 'OrderBuilder':
        """Set the number of shares"""
        return self._set_quantity(quantity, "shares")
        
    def contracts(self, quantity: int) -> 'OrderBuilder':
        """Set the number of option contracts"""
        return self._set_quantity(quantity, "contracts")
        
    # === PRICING ===
    
    def market(self) -> 'OrderBuilder':
        """Set as market order"""
        self.order_type = OrderPricing.MARKET
        self.price = None
        if len(self.legs) > 0 and self.legs[-1].quantity > 500:
            self._add_warning("Large market order - consider using limit order")
        return self
        
    def limit(self, price: float) -> 'OrderBuilder':
        """Set limit price"""
        self.order_type = OrderPricing.LIMIT
        self.price = self._format_price(price)
        return self
        
    def stop(self, stop_price: float) -> 'OrderBuilder':
        """Set stop order"""
        self.order_type = OrderPricing.STOP
        self.stop_price = self._format_price(stop_price)
        return self
        
    def stop_limit(self, stop_price: float, limit_price: float) -> 'OrderBuilder':
        """Set stop-limit order"""
        self.order_type = OrderPricing.STOP_LIMIT
        self.stop_price = self._format_price(stop_price)
        self.price = self._format_price(limit_price)
        return self
        
    def trailing_stop(self, offset: float, offset_type: str = "VALUE", 
                     basis: str = "BID") -> 'OrderBuilder':
        """Set trailing stop order"""
        self.order_type = OrderPricing.TRAILING_STOP
        self.stop_price_link_basis = basis
        self.stop_price_link_type = offset_type
        self.stop_price_offset = offset
        return self
        
    def trailing_stop_limit(self, offset: float, limit_price: float,
                           offset_type: str = "VALUE", basis: str = "BID") -> 'OrderBuilder':
        """Set trailing stop-limit order"""
        self.order_type = OrderPricing.TRAILING_STOP_LIMIT
        self.price = self._format_price(limit_price)
        self.stop_price_link_basis = basis
        self.stop_price_link_type = offset_type
        self.stop_price_offset = offset
        return self
        
    def net_debit(self, max_debit: float) -> 'OrderBuilder':
        """Set as net debit order (for options spreads)"""
        self.order_type = OrderPricing.NET_DEBIT
        self.price = self._format_price(max_debit)
        return self
        
    def net_credit(self, min_credit: float) -> 'OrderBuilder':
        """Set as net credit order (for options spreads)"""
        self.order_type = OrderPricing.NET_CREDIT
        self.price = self._format_price(min_credit)
        return self
        
    def net_zero(self) -> 'OrderBuilder':
        """Set as net zero order (for options spreads)"""
        self.order_type = OrderPricing.NET_ZERO
        self.price = "0.00"
        return self
        
    # === TIME IN FORCE ===
    
    def day(self) -> 'OrderBuilder':
        """Set as day order"""
        self.time_in_force = TimeInForce.DAY
        return self
        
    def gtc(self) -> 'OrderBuilder':
        """Set as Good Till Cancel"""
        self.time_in_force = TimeInForce.GTC
        return self
        
    def ioc(self) -> 'OrderBuilder':
        """Set as Immediate or Cancel"""
        self.time_in_force = TimeInForce.IOC
        return self
        
    def fok(self) -> 'OrderBuilder':
        """Set as Fill or Kill"""
        self.time_in_force = TimeInForce.FOK
        return self
        
    # === COMPLEX STRATEGIES ===
    
    def vertical_spread(self) -> 'OrderBuilder':
        """Mark as vertical spread strategy"""
        self.complex_order_strategy = ComplexOrderStrategy.VERTICAL
        return self
        
    def iron_condor_strategy(self) -> 'OrderBuilder':
        """Mark as iron condor strategy"""
        self.complex_order_strategy = ComplexOrderStrategy.IRON_CONDOR
        return self
        
    def straddle_strategy(self) -> 'OrderBuilder':
        """Mark as straddle strategy"""
        self.complex_order_strategy = ComplexOrderStrategy.STRADDLE
        return self
        
    def strangle_strategy(self) -> 'OrderBuilder':
        """Mark as strangle strategy"""
        self.complex_order_strategy = ComplexOrderStrategy.STRANGLE
        return self
        
    def butterfly_strategy(self) -> 'OrderBuilder':
        """Mark as butterfly strategy"""
        self.complex_order_strategy = ComplexOrderStrategy.BUTTERFLY
        return self
        
    def custom_strategy(self) -> 'OrderBuilder':
        """Mark as custom multi-leg strategy"""
        self.complex_order_strategy = ComplexOrderStrategy.CUSTOM
        return self
        
    # === CONDITIONAL ORDERS ===
    
    def one_triggers_other(self, triggered_order: 'OrderBuilder') -> 'OrderBuilder':
        """Create one-triggers-other conditional order"""
        self.order_strategy = OrderStrategy.TRIGGER
        self.child_orders.append(triggered_order)
        return self
        
    def one_cancels_other(self, other_order: 'OrderBuilder') -> 'OrderBuilder':
        """Create one-cancels-other conditional order"""
        self.order_strategy = OrderStrategy.OCO
        self.child_orders.append(other_order)
        return self
        
    # === SAFEGUARDS ===
    
    def require_confirmation(self) -> 'OrderBuilder':
        """Require manual confirmation before submitting"""
        self.require_confirm = True
        return self
        
    # === VALIDATION & BUILDING ===
    
    def validate(self) -> bool:
        """Validate the order and return True if valid"""
        try:
            self._validate_order()
            return True
        except ValidationError:
            return False
            
    def build(self) -> Dict[str, Any]:
        """Build and return the Schwab API compatible order JSON"""
        self._validate_order()
        
        if self.require_confirm and self.console:
            if not self._confirm_order():
                raise ValidationError("Order cancelled by user")
                
        return self._build_schwab_order()
        
    # === TEMPLATES ===
    
    def save_template(self, name: str, description: str = "") -> 'OrderBuilder':
        """Save current order as a template"""
        template = {
            'name': name,
            'description': description,
            'created': datetime.now().isoformat(),
            'legs': [asdict(leg) for leg in self.legs],
            'order_type': self.order_type,
            'price': self.price,
            'stop_price': self.stop_price,
            'time_in_force': self.time_in_force,
            'session': self.session
        }
        
        templates_dir = Path("order_templates")
        templates_dir.mkdir(exist_ok=True)
        
        template_file = templates_dir / f"{name}.json"
        with open(template_file, 'w') as f:
            json.dump(template, f, indent=2)
            
        if self.console:
            self.console.print(f"✅ Template saved: {template_file}")
            
        return self
        
    @classmethod
    def load_template(cls, name: str, console: Optional[Console] = None) -> 'OrderBuilder':
        """Load an order template"""
        template_file = Path("order_templates") / f"{name}.json"
        
        if not template_file.exists():
            raise FileNotFoundError(f"Template not found: {name}")
            
        with open(template_file, 'r') as f:
            template = json.load(f)
            
        builder = cls(console)
        builder.legs = [OrderLeg(**leg) for leg in template['legs']]
        builder.order_type = template['order_type']
        builder.price = template['price']
        builder.stop_price = template['stop_price']
        builder.time_in_force = template['time_in_force']
        builder.session = template['session']
        
        return builder
        
    @classmethod
    def list_templates(cls) -> List[str]:
        """List available templates"""
        templates_dir = Path("order_templates")
        if not templates_dir.exists():
            return []
            
        return [f.stem for f in templates_dir.glob("*.json")]
        
    # === PRIVATE METHODS ===
    
    def _add_leg(self, action: str, symbol: str, asset_type: str = "EQUITY"):
        """Add an order leg"""
        leg = OrderLeg(action=action, symbol=symbol, quantity=0, asset_type=asset_type)
        self.legs.append(leg)
        
    def _set_quantity(self, quantity: int, unit: str) -> 'OrderBuilder':
        """Set quantity for the most recent leg"""
        if not self.legs:
            raise ValidationError("Must specify buy/sell action before quantity")
            
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
            
        self.legs[-1].quantity = quantity
        
        # Safeguards
        if unit == "shares" and quantity > 1000:
            self._add_warning(f"Large order: {quantity:,} shares")
        elif unit == "contracts" and quantity > 10:
            self._add_warning(f"Large options order: {quantity} contracts")
            
        return self
        
    def _format_price(self, price: float) -> str:
        """Format price according to Schwab requirements"""
        if price <= 0:
            raise ValidationError("Price must be positive")
            
        # Schwab truncation logic from documentation
        if abs(price) < 1.0:
            # Truncate to 4 decimal places for prices < $1
            decimal_price = Decimal(str(price)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
        else:
            # Truncate to 2 decimal places for prices >= $1
            decimal_price = Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            
        return str(decimal_price)
        
    def _add_warning(self, message: str):
        """Add a warning message"""
        self.warnings.append(message)
        if self.console:
            self.console.print(f"⚠️  {message}", style="yellow")
            
    def _validate_order(self):
        """Validate the complete order"""
        if not self.legs:
            raise ValidationError("Order must have at least one leg")
            
        for leg in self.legs:
            if leg.quantity <= 0:
                raise ValidationError(f"Invalid quantity for {leg.symbol}: {leg.quantity}")
                
        if self.order_type == OrderPricing.LIMIT and self.price is None:
            raise ValidationError("Limit orders require a price")
            
        if self.order_type == OrderPricing.STOP and self.stop_price is None:
            raise ValidationError("Stop orders require a stop price")
            
        if self.order_type == OrderPricing.STOP_LIMIT and (self.price is None or self.stop_price is None):
            raise ValidationError("Stop-limit orders require both stop price and limit price")
            
        if self.order_type in [OrderPricing.NET_DEBIT, OrderPricing.NET_CREDIT] and self.price is None:
            raise ValidationError("Net debit/credit orders require a price")
            
        if self.order_type in [OrderPricing.TRAILING_STOP, OrderPricing.TRAILING_STOP_LIMIT]:
            if self.stop_price_offset is None:
                raise ValidationError("Trailing stop orders require an offset")
                
        # Validate multi-leg options strategies
        if len(self.legs) > 1:
            option_legs = [leg for leg in self.legs if leg.asset_type == "OPTION"]
            if option_legs and self.complex_order_strategy == ComplexOrderStrategy.NONE:
                self._add_warning("Multi-leg options order should specify complex strategy type")
                
        # Validate conditional orders
        if self.order_strategy in [OrderStrategy.OCO, OrderStrategy.TRIGGER]:
            if not self.child_orders:
                raise ValidationError("Conditional orders require child orders")
            
    def _confirm_order(self) -> bool:
        """Show order summary and get user confirmation"""
        if not self.console:
            return True
            
        # Create order summary table
        table = Table(title="Order Confirmation")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        
        for i, leg in enumerate(self.legs):
            table.add_row(f"Leg {i+1}", f"{leg.action} {leg.quantity} {leg.symbol}")
            
        table.add_row("Order Type", self.order_type or "MARKET")
        if self.price:
            table.add_row("Price", f"${self.price}")
        if self.stop_price:
            table.add_row("Stop Price", f"${self.stop_price}")
        table.add_row("Time in Force", self.time_in_force)
        
        self.console.print(table)
        
        if self.warnings:
            warning_text = Text("\nWarnings:\n", style="yellow bold")
            for warning in self.warnings:
                warning_text.append(f"• {warning}\n", style="yellow")
            self.console.print(Panel(warning_text, border_style="yellow"))
            
        response = input("\nConfirm order? (y/N): ").strip().lower()
        return response in ['y', 'yes']
        
    def _build_schwab_order(self) -> Dict[str, Any]:
        """Build the final Schwab API order JSON"""
        order = {
            "session": self.session,
            "duration": self.time_in_force,
            "orderType": self.order_type or "MARKET",
            "orderStrategyType": self.order_strategy
        }
        
        # Add complex order strategy for options
        if self.complex_order_strategy != ComplexOrderStrategy.NONE:
            order["complexOrderStrategyType"] = self.complex_order_strategy
        
        # Add pricing
        if self.price:
            order["price"] = self.price
        if self.stop_price:
            order["stopPrice"] = self.stop_price
            
        # Add trailing stop configuration
        if self.stop_price_link_basis:
            order["stopPriceLinkBasis"] = self.stop_price_link_basis
        if self.stop_price_link_type:
            order["stopPriceLinkType"] = self.stop_price_link_type
        if self.stop_price_offset is not None:
            order["stopPriceOffset"] = self.stop_price_offset
            
        # Build order legs
        order_legs = []
        for leg in self.legs:
            leg_dict = {
                "instruction": leg.action,
                "quantity": leg.quantity,
                "instrument": {
                    "symbol": leg.symbol,
                    "assetType": leg.asset_type
                }
            }
            order_legs.append(leg_dict)
            
        order["orderLegCollection"] = order_legs
        
        # Add child orders for conditional strategies
        if self.child_orders:
            child_strategies = []
            for child_order in self.child_orders:
                child_order_json = child_order._build_schwab_order()
                child_strategies.append(child_order_json)
            order["childOrderStrategies"] = child_strategies
        
        return order
        
    def __str__(self) -> str:
        """String representation of the order"""
        if not self.legs:
            return "Empty order"
            
        parts = []
        for leg in self.legs:
            parts.append(f"{leg.action} {leg.quantity} {leg.symbol}")
            
        order_desc = " + ".join(parts)
        
        if self.order_type and self.order_type != "MARKET":
            if self.price:
                order_desc += f" @ ${self.price} {self.order_type}"
            if self.stop_price:
                order_desc += f" (stop: ${self.stop_price})"
        elif self.order_type == "MARKET":
            order_desc += " @ MARKET"
            
        order_desc += f" ({self.time_in_force})"
        
        return order_desc


# === STRATEGY BUILDER ===

class StrategyBuilder:
    """Base class for building common options strategies"""
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        self.underlying = underlying.upper()
        self.console = console
        self.orders: List[OrderBuilder] = []
        
    def add_order(self, order: OrderBuilder):
        """Add an order to the strategy"""
        self.orders.append(order)
        return self
        
    def build_all(self) -> List[Dict[str, Any]]:
        """Build all orders in the strategy"""
        return [order.build() for order in self.orders]
        
    def save_strategy(self, name: str, description: str = ""):
        """Save the strategy as a template"""
        strategy = {
            'name': name,
            'description': description,
            'underlying': self.underlying,
            'created': datetime.now().isoformat(),
            'orders': [order.build() for order in self.orders]
        }
        
        strategies_dir = Path("strategies")
        strategies_dir.mkdir(exist_ok=True)
        
        strategy_file = strategies_dir / f"{name}.json"
        with open(strategy_file, 'w') as f:
            json.dump(strategy, f, indent=2)
            
        if self.console:
            self.console.print(f"✅ Strategy saved: {strategy_file}")


class CoveredCall(StrategyBuilder):
    """Covered call strategy builder"""
    
    def __init__(self, underlying: str, console: Optional[Console] = None):
        super().__init__(underlying, console)
        self.stock_order = None
        self.call_order = None
        
    def buy_stock(self, shares: int) -> 'CoveredCall':
        """Buy the underlying stock"""
        self.stock_order = OrderBuilder(self.console).buy(self.underlying).shares(shares)
        return self
        
    def at_market(self) -> 'CoveredCall':
        """Execute stock purchase at market"""
        if self.stock_order:
            self.stock_order.market()
        return self
        
    def at_limit(self, price: float) -> 'CoveredCall':
        """Execute stock purchase at limit price"""
        if self.stock_order:
            self.stock_order.limit(price)
        return self
        
    def sell_call(self, call_symbol: str, contracts: int) -> 'CoveredCall':
        """Sell call options"""
        self.call_order = OrderBuilder(self.console).sell_to_open(call_symbol).contracts(contracts)
        return self
        
    def call_limit(self, price: float) -> 'CoveredCall':
        """Set limit price for call"""
        if self.call_order:
            self.call_order.limit(price)
        return self
        
    def build(self) -> List[Dict[str, Any]]:
        """Build the covered call orders"""
        orders = []
        if self.stock_order:
            orders.append(self.stock_order.build())
        if self.call_order:
            orders.append(self.call_order.build())
        return orders


# === UTILITY FUNCTIONS ===

def quick_buy(symbol: str, shares: int, limit_price: Optional[float] = None, 
              console: Optional[Console] = None) -> Dict[str, Any]:
    """Quick utility for simple buy orders"""
    order = OrderBuilder(console).buy(symbol).shares(shares)
    if limit_price:
        order.limit(limit_price)
    else:
        order.market()
    return order.day().build()

def quick_sell(symbol: str, shares: int, limit_price: Optional[float] = None,
               console: Optional[Console] = None) -> Dict[str, Any]:
    """Quick utility for simple sell orders"""
    order = OrderBuilder(console).sell(symbol).shares(shares)
    if limit_price:
        order.limit(limit_price)
    else:
        order.market()
    return order.day().build()


if __name__ == "__main__":
    # Example usage
    console = Console() if RICH_AVAILABLE else None
    
    print("=== Enhanced Schwab Orders Examples ===\n")
    
    # Simple equity order
    print("1. Simple Buy Order:")
    order = OrderBuilder(console).buy('AAPL').shares(100).limit(150.50).day()
    print(f"   {order}")
    print(json.dumps(order.build(), indent=2))
    
    print("\n2. Vertical Call Spread (NET_DEBIT):")
    spread = (OrderBuilder(console)
              .buy_to_open('XYZ   240315P00045000').contracts(2)
              .sell_to_open('XYZ   240315P00043000').contracts(2)
              .net_debit(0.10)
              .vertical_spread()
              .day())
    print(f"   {spread}")
    print(json.dumps(spread.build(), indent=2))
    
    print("\n3. Trailing Stop Order:")
    trailing = (OrderBuilder(console)
                .sell('XYZ').shares(10)
                .trailing_stop(offset=10.0, offset_type="VALUE", basis="BID")
                .day())
    print(f"   {trailing}")
    print(json.dumps(trailing.build(), indent=2))
    
    print("\n4. One Triggers Another:")
    # Buy order that triggers a sell order when filled
    sell_order = (OrderBuilder(console)
                  .sell('XYZ').shares(10)
                  .limit(42.03)
                  .day())
    
    trigger_order = (OrderBuilder(console)
                     .buy('XYZ').shares(10)
                     .limit(34.97)
                     .day()
                     .one_triggers_other(sell_order))
    print(f"   {trigger_order}")
    print(json.dumps(trigger_order.build(), indent=2))
    
    print("\n5. One Cancels Other (OCO):")
    # Two orders where if one fills, the other is cancelled
    stop_order = (OrderBuilder(console)
                  .sell('XYZ').shares(2)
                  .stop_limit(37.03, 37.00)
                  .day())
    
    oco_order = (OrderBuilder(console)
                 .sell('XYZ').shares(2)
                 .limit(45.97)
                 .day()
                 .one_cancels_other(stop_order))
    print(f"   {oco_order}")
    print(json.dumps(oco_order.build(), indent=2))
