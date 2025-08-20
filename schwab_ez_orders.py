"""
EZ Schwab Orders - Simplified Interface for Schwab Trading

This is the main interface that makes Schwab order creation simple and safe.
Import this module and use the high-level functions for easy trading.

Example usage:
    from schwab_ez_orders import EZOrders
    
    ez = EZOrders()
    
    # Simple orders
    order = ez.buy('AAPL', 100, limit=150.50)
    order = ez.sell('AAPL', 50, stop_loss=140.00)
    
    # Options strategies
    strategy = ez.covered_call('AAPL')
    strategy.buy_stock(100).at_limit(150.00)
    strategy.sell_call('AAPL240315C00160000', 1).at_limit(3.50)
    
    # Execute orders
    ez.submit_order(order)
    ez.submit_strategy(strategy)
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable
from dataclasses import dataclass
from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

# Import our custom modules
from schwab_order_builder import OrderBuilder, ValidationError, quick_buy, quick_sell
from schwab_strategies import (
    StrategyFactory, CoveredCall, ProtectivePut, BullCallSpread, 
    BearPutSpread, IronCondor, Straddle, Strangle
)


@dataclass
class EZConfig:
    """Configuration for EZ Orders"""
    default_time_in_force: str = "DAY"
    require_confirmation: bool = True
    max_order_value: float = 10000.0  # Safety limit
    enable_warnings: bool = True
    save_order_history: bool = True
    templates_dir: str = "order_templates"
    strategies_dir: str = "strategies"
    history_dir: str = "order_history"


class EZOrders:
    """
    Main interface for easy Schwab order creation and management.
    
    This class provides a simplified interface for creating orders and strategies,
    with built-in safety features, validation, and template management.
    """
    
    def __init__(self, config: Optional[EZConfig] = None, 
                 console: Optional[Console] = None,
                 client_submit_func: Optional[Callable] = None):
        """
        Initialize EZ Orders
        
        Args:
            config: Configuration object (uses defaults if None)
            console: Rich console for output (creates one if None and Rich available)
            client_submit_func: Function to actually submit orders to Schwab
        """
        self.config = config or EZConfig()
        self.console = console or (Console() if RICH_AVAILABLE else None)
        self.client_submit_func = client_submit_func
        self.order_history: List[Dict] = []
        
        # Create directories
        for dir_name in [self.config.templates_dir, self.config.strategies_dir, 
                        self.config.history_dir]:
            Path(dir_name).mkdir(exist_ok=True)
        
        # Load order history
        self._load_history()
    
    # === SIMPLE ORDER METHODS ===
    
    def buy(self, symbol: str, quantity: int, limit: Optional[float] = None, 
            stop_loss: Optional[float] = None, time_in_force: Optional[str] = None) -> OrderBuilder:
        """
        Create a buy order with optional stop loss
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            limit: Limit price (if None, creates market order)
            stop_loss: Stop loss price
            time_in_force: Order duration (DAY, GTC, etc.)
        """
        order = OrderBuilder(self.console).buy(symbol).shares(quantity)
        
        if limit:
            order.limit(limit)
        else:
            order.market()
            
        tif = time_in_force or self.config.default_time_in_force
        if tif == "GTC":
            order.gtc()
        elif tif == "IOC":
            order.ioc()
        elif tif == "FOK":
            order.fok()
        else:
            order.day()
            
        if self.config.require_confirmation:
            order.require_confirmation()
            
        # Add stop loss as a separate order if specified
        if stop_loss:
            self._add_warning(f"Stop loss at ${stop_loss} - remember to place as separate order")
            
        return order
    
    def sell(self, symbol: str, quantity: int, limit: Optional[float] = None,
             time_in_force: Optional[str] = None) -> OrderBuilder:
        """Create a sell order"""
        order = OrderBuilder(self.console).sell(symbol).shares(quantity)
        
        if limit:
            order.limit(limit)
        else:
            order.market()
            
        tif = time_in_force or self.config.default_time_in_force
        if tif == "GTC":
            order.gtc()
        elif tif == "IOC":
            order.ioc()
        elif tif == "FOK":
            order.fok()
        else:
            order.day()
            
        if self.config.require_confirmation:
            order.require_confirmation()
            
        return order
    
    def stop_loss(self, symbol: str, quantity: int, stop_price: float,
                  limit_price: Optional[float] = None) -> OrderBuilder:
        """Create a stop loss order"""
        order = OrderBuilder(self.console).sell(symbol).shares(quantity)
        
        if limit_price:
            order.stop_limit(stop_price, limit_price)
        else:
            order.stop(stop_price)
            
        order.gtc()  # Stop losses usually GTC
        
        if self.config.require_confirmation:
            order.require_confirmation()
            
        return order
    
    def trailing_stop_loss(self, symbol: str, quantity: int, trail_amount: float,
                          trail_type: str = "VALUE") -> OrderBuilder:
        """Create a trailing stop loss order"""
        order = (OrderBuilder(self.console)
                .sell(symbol)
                .shares(quantity)
                .trailing_stop(trail_amount, trail_type, "BID")
                .gtc())
        
        if self.config.require_confirmation:
            order.require_confirmation()
            
        return order
    
    def bracket_order(self, symbol: str, quantity: int, entry_price: float,
                     profit_target: float, stop_loss: float) -> OrderBuilder:
        """Create a bracket order (buy with automatic profit/stop orders)"""
        # Create the profit target order
        profit_order = (OrderBuilder(self.console)
                       .sell(symbol)
                       .shares(quantity)
                       .limit(profit_target)
                       .gtc())
        
        # Create the stop loss order  
        stop_order = (OrderBuilder(self.console)
                     .sell(symbol)
                     .shares(quantity)
                     .stop(stop_loss)
                     .gtc())
        
        # Create OCO order for profit/stop
        oco_order = profit_order.one_cancels_other(stop_order)
        
        # Create main buy order that triggers the OCO
        main_order = (OrderBuilder(self.console)
                     .buy(symbol)
                     .shares(quantity)
                     .limit(entry_price)
                     .day()
                     .one_triggers_other(oco_order))
        
        if self.config.require_confirmation:
            main_order.require_confirmation()
            
        return main_order
    
    # === OPTIONS METHODS ===
    
    def buy_call(self, symbol: str, contracts: int, limit: Optional[float] = None) -> OrderBuilder:
        """Buy call options"""
        order = OrderBuilder(self.console).buy_to_open(symbol).contracts(contracts)
        if limit:
            order.limit(limit)
        else:
            order.market()
        return order.day()
    
    def sell_call(self, symbol: str, contracts: int, limit: Optional[float] = None) -> OrderBuilder:
        """Sell call options"""
        order = OrderBuilder(self.console).sell_to_close(symbol).contracts(contracts)
        if limit:
            order.limit(limit)
        else:
            order.market()
        return order.day()
    
    def buy_put(self, symbol: str, contracts: int, limit: Optional[float] = None) -> OrderBuilder:
        """Buy put options"""
        order = OrderBuilder(self.console).buy_to_open(symbol).contracts(contracts)
        if limit:
            order.limit(limit)
        else:
            order.market()
        return order.day()
    
    def sell_put(self, symbol: str, contracts: int, limit: Optional[float] = None) -> OrderBuilder:
        """Sell put options"""
        order = OrderBuilder(self.console).sell_to_close(symbol).contracts(contracts)
        if limit:
            order.limit(limit)
        else:
            order.market()
        return order.day()
    
    # === ADVANCED ORDER TYPES ===
    
    def vertical_spread(self, long_symbol: str, short_symbol: str, contracts: int,
                       net_price: float, order_type: str = "NET_DEBIT") -> OrderBuilder:
        """Create a vertical spread as a single order"""
        if "CALL" in long_symbol.upper():
            long_action = OrderAction.BUY_TO_OPEN
            short_action = OrderAction.SELL_TO_OPEN
        else:  # Put spread
            long_action = OrderAction.BUY_TO_OPEN  
            short_action = OrderAction.SELL_TO_OPEN
            
        order = (OrderBuilder(self.console)
                .with_leg(long_action, long_symbol, contracts, "OPTION")
                .with_leg(short_action, short_symbol, contracts, "OPTION")
                .vertical_spread()
                .day())
        
        if order_type == "NET_DEBIT":
            order.net_debit(net_price)
        elif order_type == "NET_CREDIT":
            order.net_credit(net_price)
        else:
            order.limit(net_price)
            
        return order
    
    def iron_condor_order(self, put_spread_long: str, put_spread_short: str,
                         call_spread_short: str, call_spread_long: str,
                         contracts: int, net_credit: float) -> OrderBuilder:
        """Create an iron condor as a single order"""
        order = (OrderBuilder(self.console)
                .with_leg(OrderAction.SELL_TO_OPEN, put_spread_short, contracts, "OPTION")
                .with_leg(OrderAction.BUY_TO_OPEN, put_spread_long, contracts, "OPTION") 
                .with_leg(OrderAction.SELL_TO_OPEN, call_spread_short, contracts, "OPTION")
                .with_leg(OrderAction.BUY_TO_OPEN, call_spread_long, contracts, "OPTION")
                .iron_condor_strategy()
                .net_credit(net_credit)
                .day())
        
        return order
    
    # === STRATEGY METHODS ===
    
    def covered_call(self, underlying: str) -> CoveredCall:
        """Create a covered call strategy"""
        return CoveredCall(underlying, self.console)
    
    def protective_put(self, underlying: str) -> ProtectivePut:
        """Create a protective put strategy"""
        return ProtectivePut(underlying, self.console)
    
    def bull_call_spread(self, underlying: str) -> BullCallSpread:
        """Create a bull call spread strategy"""
        return BullCallSpread(underlying, self.console)
    
    def bear_put_spread(self, underlying: str) -> BearPutSpread:
        """Create a bear put spread strategy"""
        return BearPutSpread(underlying, self.console)
    
    def iron_condor(self, underlying: str) -> IronCondor:
        """Create an iron condor strategy"""
        return IronCondor(underlying, self.console)
    
    def straddle(self, underlying: str) -> Straddle:
        """Create a straddle strategy"""
        return Straddle(underlying, self.console)
    
    def strangle(self, underlying: str) -> Strangle:
        """Create a strangle strategy"""
        return Strangle(underlying, self.console)
    
    def strategy(self, name: str, underlying: str):
        """Create a strategy by name"""
        return StrategyFactory.create(name, underlying, self.console)
    
    # === ORDER EXECUTION ===
    
    def submit_order(self, order: OrderBuilder, dry_run: bool = False,
                    validate_first: bool = True) -> Optional[Dict]:
        """
        Submit an order to Schwab (or simulate if dry_run=True)
        
        Args:
            order: OrderBuilder instance
            dry_run: If True, just validate and show order without submitting
            validate_first: If True, use Schwab preview endpoint for validation
            
        Returns:
            Order response from Schwab API or None if dry run
        """
        try:
            order_json = order.build()
            
            # Enhanced validation using Schwab preview endpoint
            if validate_first and hasattr(self, '_enhanced_validate'):
                validation_result = self._enhanced_validate(order_json)
                if not validation_result.get('valid', True):
                    self._print("❌ Order failed enhanced validation", style="red")
                    return None
            
            if dry_run:
                self._show_order_preview(order_json)
                return None
                
            # Validate order value
            self._validate_order_value(order_json)
            
            # Submit to Schwab if client function provided
            if self.client_submit_func:
                response = self.client_submit_func(order_json)
                self._save_to_history('order', order_json, response)
                return response
            else:
                self._print("⚠️  No client submit function - order not actually submitted")
                self._show_order_preview(order_json)
                return order_json
                
        except ValidationError as e:
            self._print(f"❌ Order validation failed: {e}", style="red")
            return None
        except Exception as e:
            self._print(f"❌ Error submitting order: {e}", style="red")
            return None
    
    def smart_submit(self, order: OrderBuilder, max_cost: Optional[float] = None,
                    require_preview: bool = True) -> Optional[Dict]:
        """
        Smart order submission with enhanced validation and cost checking
        
        Args:
            order: OrderBuilder instance
            max_cost: Maximum acceptable total cost (commission + fees)
            require_preview: Require successful preview before submitting
            
        Returns:
            Order response or None if rejected
        """
        try:
            # Step 1: Build and validate order locally
            order_json = order.build()
            
            # Step 2: Get Schwab preview/validation if available
            if require_preview and hasattr(self, '_get_preview'):
                preview = self._get_preview(order_json)
                
                if preview.get('status') == 'error':
                    self._print(f"❌ Preview failed: {preview.get('message')}", style="red")
                    return None
                
                # Check for rejections
                validation_result = preview.get('orderValidationResult', {})
                rejects = validation_result.get('rejects', [])
                if rejects:
                    self._print("❌ Order rejected by Schwab:", style="red")
                    for reject in rejects:
                        self._print(f"  • {reject.get('message', 'Unknown error')}", style="red")
                    return None
                
                # Check cost limits
                if max_cost:
                    order_balance = preview.get('orderStrategy', {}).get('orderBalance', {})
                    commission = order_balance.get('projectedCommission', 0)
                    
                    commission_fee = preview.get('commissionAndFee', {})
                    total_fees = self._calculate_total_fees(commission_fee)
                    
                    total_cost = commission + total_fees
                    
                    if total_cost > max_cost:
                        self._print(f"❌ Order cost ${total_cost:.2f} exceeds limit ${max_cost:.2f}", 
                                  style="red")
                        return None
                
                # Show warnings
                warns = validation_result.get('warns', [])
                if warns:
                    self._print("⚠️  Order warnings:", style="yellow")
                    for warn in warns:
                        self._print(f"  • {warn.get('message', 'Unknown warning')}", style="yellow")
            
            # Step 3: Submit the order
            return self.submit_order(order, validate_first=False)
            
        except Exception as e:
            self._print(f"❌ Smart submit error: {e}", style="red")
            return None
    
    def batch_submit(self, orders: List[OrderBuilder], 
                    pause_between: float = 1.0,
                    stop_on_error: bool = True) -> List[Dict]:
        """
        Submit multiple orders with optional pauses and error handling
        
        Args:
            orders: List of OrderBuilder instances
            pause_between: Seconds to pause between submissions
            stop_on_error: Stop submitting if an order fails
            
        Returns:
            List of order responses
        """
        responses = []
        
        for i, order in enumerate(orders):
            try:
                self._print(f"📤 Submitting order {i+1}/{len(orders)}")
                
                response = self.submit_order(order)
                responses.append(response)
                
                if response is None or response.get('status') == 'error':
                    if stop_on_error:
                        self._print(f"❌ Stopping batch submit due to error on order {i+1}")
                        break
                    else:
                        self._print(f"⚠️  Order {i+1} failed, continuing...")
                
                # Pause between orders (except last one)
                if i < len(orders) - 1 and pause_between > 0:
                    import time
                    time.sleep(pause_between)
                    
            except Exception as e:
                self._print(f"❌ Error submitting order {i+1}: {e}", style="red")
                if stop_on_error:
                    break
                    
        return responses
    
    def submit_strategy(self, strategy, dry_run: bool = False) -> Optional[List[Dict]]:
        """Submit all orders in a strategy"""
        try:
            orders = strategy.build_all()
            
            if dry_run:
                for i, order in enumerate(orders):
                    self._print(f"\n--- Strategy Order {i+1} ---")
                    self._show_order_preview(order)
                return None
                
            responses = []
            for order in orders:
                response = self.submit_order(OrderBuilder().reset(), dry_run=False)
                if response:
                    responses.append(response)
                    
            return responses
            
        except Exception as e:
            self._print(f"❌ Error submitting strategy: {e}", style="red")
            return None
    
    # === TEMPLATE MANAGEMENT ===
    
    def save_template(self, order: OrderBuilder, name: str, description: str = ""):
        """Save an order as a template"""
        order.save_template(name, description)
    
    def load_template(self, name: str) -> OrderBuilder:
        """Load an order template"""
        return OrderBuilder.load_template(name, self.console)
    
    def list_templates(self) -> List[str]:
        """List available order templates"""
        return OrderBuilder.list_templates()
    
    def delete_template(self, name: str):
        """Delete an order template"""
        template_file = Path(self.config.templates_dir) / f"{name}.json"
        if template_file.exists():
            template_file.unlink()
            self._print(f"✅ Template deleted: {name}")
        else:
            self._print(f"❌ Template not found: {name}")
    
    # === PORTFOLIO HELPERS ===
    
    def quick_portfolio_adjustment(self, symbol: str, current_shares: int, 
                                 target_shares: int, limit_price: Optional[float] = None) -> OrderBuilder:
        """Quickly adjust position to target"""
        difference = target_shares - current_shares
        
        if difference > 0:
            return self.buy(symbol, difference, limit_price)
        elif difference < 0:
            return self.sell(symbol, abs(difference), limit_price)
        else:
            self._print(f"No adjustment needed for {symbol}")
            return None
    
    def dollar_cost_average(self, symbol: str, dollar_amount: float, 
                           current_price: float) -> OrderBuilder:
        """Create order to invest specific dollar amount"""
        shares = int(dollar_amount / current_price)
        if shares == 0:
            raise ValueError(f"Dollar amount ${dollar_amount} too small for {symbol} at ${current_price}")
            
        return self.buy(symbol, shares, limit=current_price * 1.01)  # 1% above current price
    
    # === UTILITIES ===
    
    def show_order_history(self, limit: int = 10):
        """Show recent order history"""
        if not self.order_history:
            self._print("No order history found")
            return
            
        if self.console:
            table = Table(title=f"Recent Orders (last {limit})")
            table.add_column("Date", style="cyan")
            table.add_column("Type", style="white")
            table.add_column("Symbol", style="green")
            table.add_column("Action", style="yellow")
            table.add_column("Quantity", style="white")
            table.add_column("Price", style="white")
            
            for entry in self.order_history[-limit:]:
                order = entry.get('order', {})
                legs = order.get('orderLegCollection', [])
                if legs:
                    leg = legs[0]
                    instrument = leg.get('instrument', {})
                    
                    table.add_row(
                        entry['timestamp'][:10],  # Just date
                        order.get('orderType', 'N/A'),
                        instrument.get('symbol', 'N/A'),
                        leg.get('instruction', 'N/A'),
                        str(leg.get('quantity', 'N/A')),
                        order.get('price', 'Market')
                    )
            
            self.console.print(table)
        else:
            for entry in self.order_history[-limit:]:
                print(f"{entry['timestamp']}: {entry.get('type', 'order')}")
    
    def estimate_commission(self, order: OrderBuilder) -> float:
        """Estimate commission for an order (rough approximation)"""
        # This is a rough estimate - actual commissions vary
        order_json = order.build()
        legs = order_json.get('orderLegCollection', [])
        
        commission = 0.0
        for leg in legs:
            asset_type = leg.get('instrument', {}).get('assetType', 'EQUITY')
            if asset_type == 'OPTION':
                commission += 0.65  # Typical options commission per contract
            # Schwab typically has $0 stock commissions
                
        return commission
    
    # === PRIVATE METHODS ===
    
    def _validate_order_value(self, order_json: Dict):
        """Validate order doesn't exceed safety limits"""
        legs = order_json.get('orderLegCollection', [])
        price = float(order_json.get('price', 0))
        
        if price == 0:  # Market order
            return  # Can't validate market orders
            
        total_value = 0
        for leg in legs:
            quantity = leg.get('quantity', 0)
            if leg.get('instruction') in ['BUY', 'BUY_TO_OPEN']:
                total_value += quantity * price
                
        if total_value > self.config.max_order_value:
            raise ValidationError(
                f"Order value ${total_value:,.2f} exceeds safety limit "
                f"${self.config.max_order_value:,.2f}"
            )
    
    def _show_order_preview(self, order_json: Dict):
        """Show order preview"""
        if self.console:
            panel = Panel(
                json.dumps(order_json, indent=2),
                title="Order Preview",
                border_style="green"
            )
            self.console.print(panel)
        else:
            print("Order Preview:")
            print(json.dumps(order_json, indent=2))
    
    def _save_to_history(self, order_type: str, order_json: Dict, response: Dict = None):
        """Save order to history"""
        if not self.config.save_order_history:
            return
            
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': order_type,
            'order': order_json,
            'response': response
        }
        
        self.order_history.append(entry)
        
        # Save to file
        history_file = Path(self.config.history_dir) / "order_history.json"
        with open(history_file, 'w') as f:
            json.dump(self.order_history, f, indent=2)
    
    def _load_history(self):
        """Load order history from file"""
        history_file = Path(self.config.history_dir) / "order_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    self.order_history = json.load(f)
            except Exception:
                self.order_history = []
    
    def _print(self, message: str, style: str = "white"):
        """Print message using console if available"""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)
    
    def _calculate_total_fees(self, commission_fee: Dict) -> float:
        """Calculate total fees from commission_fee structure"""
        total_fees = 0.0
        
        fee_data = commission_fee.get('fee', {})
        fee_legs = fee_data.get('feeLegs', [])
        
        for leg in fee_legs:
            fee_values = leg.get('feeValues', [])
            for fee_val in fee_values:
                total_fees += fee_val.get('value', 0.0)
                
        return total_fees
    
    def set_preview_function(self, preview_func: Callable[[Dict], Dict]):
        """Set function to call Schwab preview endpoint"""
        self._get_preview = preview_func
        
    def set_enhanced_validation(self, validation_func: Callable[[Dict], Dict]):
        """Set function for enhanced order validation"""
        self._enhanced_validate = validation_func
        
    def _add_warning(self, message: str):
        """Add a warning message"""
        if self.config.enable_warnings:
            self._print(f"⚠️  {message}", style="yellow")


# === EXAMPLE USAGE ===

def demo_ez_orders():
    """Demonstrate EZ Orders functionality"""
    
    # Initialize
    config = EZConfig(require_confirmation=False)  # Skip confirmation for demo
    ez = EZOrders(config)
    
    print("=== EZ Schwab Orders Demo ===\n")
    
    # Simple equity orders
    print("1. Simple Buy Order:")
    buy_order = ez.buy('AAPL', 100, limit=150.50)
    print(f"   {buy_order}")
    
    print("\n2. Trailing Stop Loss:")
    trailing_stop = ez.trailing_stop_loss('AAPL', 100, trail_amount=10.0)
    print(f"   {trailing_stop}")
    
    print("\n3. Bracket Order (Entry + Profit Target + Stop Loss):")
    bracket = ez.bracket_order('AAPL', 100, entry_price=150.00, 
                              profit_target=160.00, stop_loss=140.00)
    print(f"   {bracket}")
    
    # Options strategies
    print("\n4. Vertical Spread (Single Order):")
    spread = ez.vertical_spread('AAPL240315C00150000', 'AAPL240315C00160000', 
                               contracts=1, net_price=3.00, order_type="NET_DEBIT")
    print(f"   {spread}")
    
    print("\n5. Iron Condor (Single Order):")
    ic = ez.iron_condor_order(
        put_spread_long='SPY240315P00395000',
        put_spread_short='SPY240315P00400000', 
        call_spread_short='SPY240315C00420000',
        call_spread_long='SPY240315C00425000',
        contracts=1, 
        net_credit=2.00
    )
    print(f"   {ic}")
    
    # Show JSON output for one order
    print("\n6. Sample JSON Output (Vertical Spread):")
    print(json.dumps(spread.build(), indent=2))
    
    # Portfolio helper
    print("\n7. Portfolio Adjustment:")
    adjustment = ez.quick_portfolio_adjustment('TSLA', current_shares=50, target_shares=75, limit_price=200.00)
    if adjustment:
        print(f"   {adjustment}")


if __name__ == "__main__":
    demo_ez_orders()
