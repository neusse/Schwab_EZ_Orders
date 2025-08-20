"""
Schwab-py Integration Example

This module shows how to integrate the EZ Orders system with the actual schwab-py client.
It includes real-world examples and best practices for live trading.

Requirements:
    pip install schwab-py rich

Setup:
    1. Get Schwab API credentials
    2. Set up token file
    3. Configure the client
    4. Use EZ Orders for simplified order creation
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import schwab
    from schwab.client import Client
    from schwab import auth
    SCHWAB_PY_AVAILABLE = True
except ImportError:
    SCHWAB_PY_AVAILABLE = False
    Client = None

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

# Import our EZ Orders system
from schwab_ez_orders import EZOrders, EZConfig
from schwab_order_builder import OrderBuilder


class SchwabEZTrader:
    """
    Complete trading interface combining schwab-py with EZ Orders
    
    This class provides a simple interface for real Schwab trading with
    built-in safety features and simplified order creation.
    """
    
    def __init__(self, 
                 client: Optional[Client] = None,
                 token_file: Optional[str] = None,
                 api_key: Optional[str] = None,
                 app_secret: Optional[str] = None,
                 config: Optional[EZConfig] = None,
                 auto_load_credentials: bool = True):
        """
        Initialize the trader
        
        Args:
            client: Pre-configured schwab-py client
            token_file: Path to token file (if client not provided)
            api_key: Schwab API key
            app_secret: Schwab app secret
            config: EZ Orders configuration
            auto_load_credentials: If True, try to load from environment first
        """
        
        if not SCHWAB_PY_AVAILABLE:
            raise ImportError("schwab-py not available. Install with: pip install schwab-py")
            
        self.console = Console() if RICH_AVAILABLE else None
        self.config = config or EZConfig()
        
        # Try to get credentials from environment if not provided
        if auto_load_credentials and not client:
            env_credentials = self._load_credentials_from_env()
            
            # Use environment credentials if available and not overridden
            if env_credentials['api_key'] and not api_key:
                api_key = env_credentials['api_key']
            if env_credentials['app_secret'] and not app_secret:
                app_secret = env_credentials['app_secret'] 
            if env_credentials['token_path'] and not token_file:
                token_file = env_credentials['token_path']
        
        # Initialize Schwab client
        if client:
            self.client = client
        elif token_file and api_key and app_secret:
            try:
                self.client = auth.client_from_token_file(token_file, api_key, app_secret)
                if self.console:
                    self.console.print("✅ Connected using provided credentials", style="green")
            except Exception as e:
                if self.console:
                    self.console.print(f"❌ Failed to connect with provided credentials: {e}", style="red")
                raise
        else:
            missing = []
            if not token_file: missing.append("token_file")
            if not api_key: missing.append("api_key") 
            if not app_secret: missing.append("app_secret")
            
            error_msg = f"Missing credentials: {', '.join(missing)}. "
            error_msg += "Set environment variables (SCHWAB_API_KEY, SCHWAB_APP_SECRET, SCHWAB_TOKEN_PATH) "
            error_msg += "or provide them directly."
            raise ValueError(error_msg)
        
        # Initialize EZ Orders with client submit function
        self.ez = EZOrders(
            config=self.config,
            console=self.console,
            client_submit_func=self._submit_to_schwab
        )
        
        # Connect preview functionality to EZ Orders
        self.ez.set_preview_function(self.preview_order)
        self.ez.set_enhanced_validation(self.smart_order_validation)
        
        self.account_hash = None
        self.paper_trading_mode = False
        self._get_account_info()
    
    def _load_credentials_from_env(self) -> Dict[str, Optional[str]]:
        """Load Schwab credentials from environment variables"""
        credentials = {
            'api_key': os.getenv('SCHWAB_API_KEY'),
            'app_secret': os.getenv('SCHWAB_APP_SECRET'),
            'callback_url': os.getenv('SCHWAB_CALLBACK_URL'),
            'token_path': os.getenv('SCHWAB_TOKEN_PATH')
        }
        
        if self.console and any(credentials.values()):
            found = [k for k, v in credentials.items() if v]
            self.console.print(f"🔑 Found environment credentials: {', '.join(found)}", style="cyan")
        
        return credentials
    
    def _get_account_info(self):
        """Get account information"""
        try:
            accounts = self.client.get_account_numbers()
            if accounts.json():
                # Use first account by default
                print(accounts.json())
                self.account_hash = accounts.json()[0]['hashValue']
                if self.console:
                    self.console.print(f"✅ Connected to account: {self.account_hash[:8]}...")
            else:
                raise Exception("No accounts found")
        except Exception as e:
            if self.console:
                self.console.print(f"❌ Failed to get account info: {e}", style="red")
            raise
    
    def preview_order(self, order_json: Dict[str, Any]) -> Dict:
        """
        Preview an order using Schwab's validation endpoint
        
        This provides:
        - Order validation with detailed feedback
        - Commission and fee calculations
        - Paper trading functionality
        - Risk analysis
        
        Args:
            order_json: The order JSON to validate
            
        Returns:
            Preview response with validation results and costs
        """
        try:
            if self.console:
                self.console.print("🔍 Previewing order with Schwab...")
                
            # Call the preview endpoint
            response = self.client.preview_order(self.account_hash, order_json)
            
            if response.status_code == 200:
                preview_data = response.json()
                
                if self.console:
                    self._display_order_preview(preview_data)
                    
                return preview_data
            else:
                error_msg = f"Preview failed with status {response.status_code}"
                if self.console:
                    self.console.print(f"❌ {error_msg}", style="red")
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error previewing order: {e}"
            if self.console:
                self.console.print(f"❌ {error_msg}", style="red")
            return {"status": "error", "message": error_msg}
    
    def _display_order_preview(self, preview_data: Dict):
        """Display order preview results in a nice format"""
        if not self.console:
            print("Order Preview:")
            print(json.dumps(preview_data, indent=2))
            return
            
        # Extract key information
        order_strategy = preview_data.get('orderStrategy', {})
        validation_result = preview_data.get('orderValidationResult', {})
        commission_fee = preview_data.get('commissionAndFee', {})
        
        # Order Summary Table
        table = Table(title="📋 Order Preview", show_header=True, header_style="bold blue")
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        # Basic order info
        table.add_row("Order Type", order_strategy.get('orderType', 'N/A'))
        table.add_row("Strategy", order_strategy.get('orderStrategyType', 'N/A'))
        table.add_row("Duration", order_strategy.get('duration', 'N/A'))
        table.add_row("Session", order_strategy.get('session', 'N/A'))
        
        if order_strategy.get('price'):
            table.add_row("Price", f"${order_strategy['price']}")
        if order_strategy.get('quantity'):
            table.add_row("Quantity", str(order_strategy['quantity']))
            
        # Order value and costs
        order_balance = order_strategy.get('orderBalance', {})
        if order_balance.get('orderValue'):
            table.add_row("Order Value", f"${order_balance['orderValue']:,.2f}")
        if order_balance.get('projectedCommission'):
            table.add_row("Est. Commission", f"${order_balance['projectedCommission']:.2f}")
            
        self.console.print(table)
        
        # Order Legs
        order_legs = order_strategy.get('orderLegs', [])
        if order_legs:
            legs_table = Table(title="📊 Order Legs", show_header=True)
            legs_table.add_column("Leg", style="cyan")
            legs_table.add_column("Action", style="yellow") 
            legs_table.add_column("Symbol", style="green")
            legs_table.add_column("Quantity", style="white")
            legs_table.add_column("Asset Type", style="white")
            
            for i, leg in enumerate(order_legs):
                legs_table.add_row(
                    str(i+1),
                    leg.get('instruction', 'N/A'),
                    leg.get('finalSymbol', 'N/A'),
                    str(leg.get('quantity', 'N/A')),
                    leg.get('assetType', 'N/A')
                )
            
            self.console.print(legs_table)
        
        # Validation Results
        self._display_validation_results(validation_result)
        
        # Commission Breakdown
        self._display_commission_breakdown(commission_fee)
    
    def _display_validation_results(self, validation_result: Dict):
        """Display validation results with appropriate styling"""
        if not validation_result:
            return
            
        # Check for any issues
        rejects = validation_result.get('rejects', [])
        warns = validation_result.get('warns', [])
        reviews = validation_result.get('reviews', [])
        alerts = validation_result.get('alerts', [])
        accepts = validation_result.get('accepts', [])
        
        if rejects:
            self.console.print("\n❌ Order Rejections:", style="red bold")
            for reject in rejects:
                self.console.print(f"  • {reject.get('message', 'Unknown error')}", style="red")
                
        if warns:
            self.console.print("\n⚠️  Order Warnings:", style="yellow bold")
            for warn in warns:
                self.console.print(f"  • {warn.get('message', 'Unknown warning')}", style="yellow")
                
        if reviews:
            self.console.print("\n🔍 Items for Review:", style="blue bold")
            for review in reviews:
                self.console.print(f"  • {review.get('message', 'Review required')}", style="blue")
                
        if alerts:
            self.console.print("\n🔔 Alerts:", style="magenta bold")
            for alert in alerts:
                self.console.print(f"  • {alert.get('message', 'Alert')}", style="magenta")
                
        if accepts and not (rejects or warns or reviews):
            self.console.print("\n✅ Order validation passed!", style="green bold")
    
    def _display_commission_breakdown(self, commission_fee: Dict):
        """Display commission and fee breakdown"""
        if not commission_fee:
            return
            
        commission = commission_fee.get('commission', {})
        fee = commission_fee.get('fee', {})
        
        # Create commission table
        comm_table = Table(title="💰 Cost Breakdown", show_header=True)
        comm_table.add_column("Type", style="cyan")
        comm_table.add_column("Amount", style="white")
        
        total_commission = 0
        total_fees = 0
        
        # Commission legs
        comm_legs = commission.get('commissionLegs', [])
        for leg in comm_legs:
            comm_values = leg.get('commissionValues', [])
            for comm_val in comm_values:
                amount = comm_val.get('value', 0)
                comm_type = comm_val.get('type', 'Commission')
                total_commission += amount
                comm_table.add_row(comm_type, f"${amount:.2f}")
        
        # Fee legs  
        fee_legs = fee.get('feeLegs', [])
        for leg in fee_legs:
            fee_values = leg.get('feeValues', [])
            for fee_val in fee_values:
                amount = fee_val.get('value', 0)
                fee_type = fee_val.get('type', 'Fee')
                total_fees += amount
                comm_table.add_row(fee_type, f"${amount:.2f}")
        
        if total_commission > 0 or total_fees > 0:
            comm_table.add_row("─" * 10, "─" * 10)
            comm_table.add_row("Total Cost", f"${total_commission + total_fees:.2f}")
            self.console.print(comm_table)
    
    def _submit_to_schwab(self, order_json: Dict[str, Any]) -> Dict:
        """Submit order to Schwab via schwab-py client"""
        try:
            # If in paper trading mode, use preview instead
            if self.paper_trading_mode:
                if self.console:
                    self.console.print("📝 Paper trading mode - using preview endpoint", style="yellow")
                return self.preview_order(order_json)
            
            if self.console:
                self.console.print("📤 Submitting order to Schwab...")
                
            response = self.client.place_order(self.account_hash, order_json)
            
            if response.status_code == 201:
                if self.console:
                    self.console.print("✅ Order submitted successfully!", style="green")
                return {"status": "success", "response": response.headers}
            else:
                error_msg = f"Order failed with status {response.status_code}"
                if self.console:
                    self.console.print(f"❌ {error_msg}", style="red")
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error submitting order: {e}"
            if self.console:
                self.console.print(f"❌ {error_msg}", style="red")
            return {"status": "error", "message": error_msg}
    
    # === ACCOUNT METHODS ===
    
    def get_positions(self) -> Dict:
        """Get current positions"""
        try:
            response = self.client.get_account(self.account_hash, fields=['positions'])
            return response.json()
        except Exception as e:
            if self.console:
                self.console.print(f"❌ Error getting positions: {e}", style="red")
            return {}
    
    def get_orders(self, days_back: int = 7) -> Dict:
        """Get recent orders"""
        try:
            from datetime import datetime, timedelta
            
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days_back)
            
            response = self.client.get_orders_by_path(
                self.account_hash,
                from_entered_time=from_date,
                to_entered_time=to_date
            )
            return response.json()
        except Exception as e:
            if self.console:
                self.console.print(f"❌ Error getting orders: {e}", style="red")
            return {}
    
    def show_portfolio_summary(self):
        """Display portfolio summary"""
        try:
            account_data = self.client.get_account(self.account_hash, fields=['positions']).json()
            
            if not self.console:
                print("Portfolio Summary:")
                print(json.dumps(account_data, indent=2))
                return
                
            # Extract key information
            securities_account = account_data.get('securitiesAccount', {})
            positions = securities_account.get('positions', [])
            
            # Create summary table
            table = Table(title="Portfolio Summary")
            table.add_column("Symbol", style="cyan")
            table.add_column("Quantity", style="white")
            table.add_column("Market Value", style="green")
            table.add_column("P&L", style="white")
            
            total_value = 0
            for position in positions:
                instrument = position.get('instrument', {})
                symbol = instrument.get('symbol', 'N/A')
                quantity = position.get('longQuantity', 0) - position.get('shortQuantity', 0)
                market_value = position.get('marketValue', 0)
                unrealized_pl = position.get('unrealizedPL', 0)
                
                if quantity != 0:  # Only show non-zero positions
                    pl_style = "green" if unrealized_pl >= 0 else "red"
                    table.add_row(
                        symbol,
                        f"{quantity:,.0f}",
                        f"${market_value:,.2f}",
                        f"[{pl_style}]${unrealized_pl:,.2f}[/{pl_style}]"
                    )
                    total_value += market_value
            
            self.console.print(table)
            self.console.print(f"\nTotal Portfolio Value: ${total_value:,.2f}")
            
        except Exception as e:
            if self.console:
                self.console.print(f"❌ Error getting portfolio: {e}", style="red")
    
    # === EZ ORDER METHODS (Delegate to EZOrders) ===
    
    def buy(self, symbol: str, quantity: int, limit: Optional[float] = None, **kwargs):
        """Create buy order"""
        return self.ez.buy(symbol, quantity, limit, **kwargs)
    
    def sell(self, symbol: str, quantity: int, limit: Optional[float] = None, **kwargs):
        """Create sell order"""
        return self.ez.sell(symbol, quantity, limit, **kwargs)
    
    def stop_loss(self, symbol: str, quantity: int, stop_price: float, **kwargs):
        """Create stop loss order"""
        return self.ez.stop_loss(symbol, quantity, stop_price, **kwargs)
    
    def covered_call(self, underlying: str):
        """Create covered call strategy"""
        return self.ez.covered_call(underlying)
    
    def protective_put(self, underlying: str):
        """Create protective put strategy"""
        return self.ez.protective_put(underlying)
    
    def strategy(self, name: str, underlying: str):
        """Create strategy by name"""
        return self.ez.strategy(name, underlying)
    
    def submit_order(self, order, dry_run: bool = False):
        """Submit order"""
        return self.ez.submit_order(order, dry_run)
    
    def submit_strategy(self, strategy, dry_run: bool = False):
        """Submit strategy"""
        return self.ez.submit_strategy(strategy, dry_run)
    
    # === TRADING HELPERS ===
    
    def rebalance_position(self, symbol: str, target_percentage: float, 
                          total_portfolio_value: Optional[float] = None):
        """Rebalance a position to target percentage"""
        try:
            positions = self.get_positions()
            securities_account = positions.get('securitiesAccount', {})
            
            if not total_portfolio_value:
                total_portfolio_value = securities_account.get('currentBalances', {}).get('liquidationValue', 0)
            
            target_value = total_portfolio_value * (target_percentage / 100)
            
            # Find current position
            current_value = 0
            current_shares = 0
            
            for position in securities_account.get('positions', []):
                instrument = position.get('instrument', {})
                if instrument.get('symbol') == symbol:
                    current_value = position.get('marketValue', 0)
                    current_shares = position.get('longQuantity', 0) - position.get('shortQuantity', 0)
                    break
            
            # Get current price (simplified - you might want to use real-time quotes)
            current_price = current_value / current_shares if current_shares > 0 else 100  # Fallback
            
            # Calculate required adjustment
            target_shares = int(target_value / current_price)
            adjustment_needed = target_shares - current_shares
            
            if abs(adjustment_needed) > 0:
                if adjustment_needed > 0:
                    order = self.buy(symbol, adjustment_needed)
                else:
                    order = self.sell(symbol, abs(adjustment_needed))
                    
                if self.console:
                    self.console.print(f"Rebalancing {symbol}: {current_shares} -> {target_shares} shares")
                    
                return order
            else:
                if self.console:
                    self.console.print(f"{symbol} already at target allocation")
                return None
                
        except Exception as e:
            if self.console:
                self.console.print(f"❌ Error rebalancing {symbol}: {e}", style="red")
            return None
    
    def paper_trade_mode(self, enabled: bool = True):
        """Toggle paper trading mode (uses preview endpoint instead of placing orders)"""
        self.paper_trading_mode = enabled
        
        if self.console:
            if enabled:
                self.console.print("📝 Paper trading mode ENABLED - orders will be previewed only", 
                                 style="yellow bold")
            else:
                self.console.print("💰 Live trading mode ENABLED - orders will be placed for real!", 
                                 style="red bold")
        
        return self
    
    def validate_order(self, order: OrderBuilder) -> Dict:
        """Validate an order using Schwab's preview endpoint"""
        try:
            order_json = order.build()
            return self.preview_order(order_json)
        except Exception as e:
            if self.console:
                self.console.print(f"❌ Error validating order: {e}", style="red")
            return {"status": "error", "message": str(e)}
    
    def estimate_costs(self, order: OrderBuilder) -> Dict[str, float]:
        """Get detailed cost estimate for an order"""
        try:
            order_json = order.build()
            preview = self.preview_order(order_json)
            
            if preview.get('status') == 'error':
                return {"error": preview.get('message', 'Unknown error')}
            
            costs = {
                "commission": 0.0,
                "fees": 0.0,
                "order_value": 0.0,
                "total_cost": 0.0
            }
            
            # Extract costs from preview
            order_strategy = preview.get('orderStrategy', {})
            order_balance = order_strategy.get('orderBalance', {})
            commission_fee = preview.get('commissionAndFee', {})
            
            costs["order_value"] = order_balance.get('orderValue', 0.0)
            costs["commission"] = order_balance.get('projectedCommission', 0.0)
            
            # Add up detailed fees
            fee_data = commission_fee.get('fee', {})
            fee_legs = fee_data.get('feeLegs', [])
            for leg in fee_legs:
                fee_values = leg.get('feeValues', [])
                for fee_val in fee_values:
                    costs["fees"] += fee_val.get('value', 0.0)
            
            costs["total_cost"] = costs["commission"] + costs["fees"]
            
            return costs
            
        except Exception as e:
            return {"error": str(e)}
    
    def smart_order_validation(self, order: OrderBuilder) -> bool:
        """
        Perform smart validation that checks for common issues
        
        Returns True if order passes all checks, False otherwise
        """
        try:
            # First do local validation
            if not order.validate():
                return False
            
            # Then do Schwab validation via preview
            preview = self.preview_order(order.build())
            
            if preview.get('status') == 'error':
                return False
            
            # Check validation results
            validation_result = preview.get('orderValidationResult', {})
            rejects = validation_result.get('rejects', [])
            
            if rejects:
                if self.console:
                    self.console.print("❌ Order rejected by Schwab:", style="red")
                    for reject in rejects:
                        self.console.print(f"  • {reject.get('message')}", style="red")
                return False
            
            # Check for warnings that might indicate issues
            warns = validation_result.get('warns', [])
            if warns and self.console:
                self.console.print("⚠️  Order warnings:", style="yellow")
                for warn in warns:
                    self.console.print(f"  • {warn.get('message')}", style="yellow")
            
            return True
            
        except Exception as e:
            if self.console:
                self.console.print(f"❌ Validation error: {e}", style="red")
            return False


# === CONVENIENCE FUNCTIONS ===

def create_trader_from_env(config: Optional[EZConfig] = None) -> 'SchwabEZTrader':
    """
    Create trader using only environment variables
    
    Required environment variables:
    - SCHWAB_API_KEY
    - SCHWAB_APP_SECRET
    - SCHWAB_TOKEN_PATH
    
    Optional:
    - SCHWAB_CALLBACK_URL
    """
    return SchwabEZTrader(config=config, auto_load_credentials=True)

def setup_env_vars_interactively():
    """
    Help user set up environment variables interactively
    Shows the export commands they need to run
    """
    console = Console() if RICH_AVAILABLE else None
    
    if console:
        console.print("🔧 Environment Variables Setup", style="bold blue")
        console.print("This will help you create the export commands for your shell.\n")
        
        api_key = Prompt.ask("Enter your Schwab API Key")
        app_secret = Prompt.ask("Enter your Schwab App Secret", password=True)
        token_path = Prompt.ask("Enter token file path", default="schwab_token.json")
        callback_url = Prompt.ask("Enter callback URL", default="https://localhost:8080")
        
        console.print("\n📋 Add these to your shell profile (.bashrc, .zshrc, etc.):", style="green bold")
        console.print(f"export SCHWAB_API_KEY='{api_key}'")
        console.print(f"export SCHWAB_APP_SECRET='{app_secret}'")
        console.print(f"export SCHWAB_TOKEN_PATH='{token_path}'")
        console.print(f"export SCHWAB_CALLBACK_URL='{callback_url}'")
        
        console.print("\n💡 Or run these commands in your current session:", style="yellow")
        console.print(f"export SCHWAB_API_KEY='{api_key}'")
        console.print(f"export SCHWAB_APP_SECRET='{app_secret}'")
        console.print(f"export SCHWAB_TOKEN_PATH='{token_path}'")
        console.print(f"export SCHWAB_CALLBACK_URL='{callback_url}'")
        
        console.print("\n✅ After setting these, you can use:", style="green")
        console.print("from schwab_integration_example import create_trader_from_env")
        console.print("trader = create_trader_from_env()")
        
    else:
        print("Environment Variables Setup")
        print("=" * 30)
        
        api_key = input("Enter your Schwab API Key: ")
        app_secret = input("Enter your Schwab App Secret: ")
        token_path = input("Enter token file path (default: schwab_token.json): ") or "schwab_token.json"
        callback_url = input("Enter callback URL (default: https://localhost:8080): ") or "https://localhost:8080"
        
        print("\nAdd these to your shell profile (.bashrc, .zshrc, etc.):")
        print(f"export SCHWAB_API_KEY='{api_key}'")
        print(f"export SCHWAB_APP_SECRET='{app_secret}'")
        print(f"export SCHWAB_TOKEN_PATH='{token_path}'")
        print(f"export SCHWAB_CALLBACK_URL='{callback_url}'")

def check_env_setup() -> Dict[str, bool]:
    """
    Check which environment variables are set
    
    Returns dict with status of each required variable
    """
    env_status = {
        'SCHWAB_API_KEY': bool(os.getenv('SCHWAB_API_KEY')),
        'SCHWAB_APP_SECRET': bool(os.getenv('SCHWAB_APP_SECRET')),
        'SCHWAB_TOKEN_PATH': bool(os.getenv('SCHWAB_TOKEN_PATH')),
        'SCHWAB_CALLBACK_URL': bool(os.getenv('SCHWAB_CALLBACK_URL'))
    }
    
    if RICH_AVAILABLE:
        console = Console()
        console.print("🔍 Environment Variables Status:", style="bold blue")
        
        for var, is_set in env_status.items():
            status = "✅ Set" if is_set else "❌ Not Set"
            style = "green" if is_set else "red"
            console.print(f"  {var}: {status}", style=style)
            
        required_set = env_status['SCHWAB_API_KEY'] and env_status['SCHWAB_APP_SECRET'] and env_status['SCHWAB_TOKEN_PATH']
        
        if required_set:
            console.print("\n✅ All required variables are set!", style="green bold")
            console.print("You can use: trader = create_trader_from_env()")
        else:
            console.print("\n⚠️  Missing required variables", style="yellow")
            console.print("Run setup_env_vars_interactively() for help")
    else:
        print("Environment Variables Status:")
        for var, is_set in env_status.items():
            status = "Set" if is_set else "Not Set"
            print(f"  {var}: {status}")
    
    return env_status

def setup_schwab_config(config_file: str = "schwab_config.json") -> Dict[str, str]:
    """
    Interactive setup for Schwab configuration
    
    First tries to load from environment variables, then prompts user if needed.
    
    Environment variables:
    - SCHWAB_API_KEY
    - SCHWAB_APP_SECRET  
    - SCHWAB_CALLBACK_URL
    - SCHWAB_TOKEN_PATH
    
    Returns dictionary with configuration values
    """
    
    console = Console() if RICH_AVAILABLE else None
    
    # Try to get credentials from environment first
    api_key = os.getenv('SCHWAB_API_KEY')
    app_secret = os.getenv('SCHWAB_APP_SECRET')
    callback_url = os.getenv('SCHWAB_CALLBACK_URL')
    token_path = os.getenv('SCHWAB_TOKEN_PATH')
    
    if console:
        console.print("🔧 Schwab API Configuration", style="bold blue")
        
        if any([api_key, app_secret, callback_url, token_path]):
            found_vars = []
            if api_key: found_vars.append("SCHWAB_API_KEY")
            if app_secret: found_vars.append("SCHWAB_APP_SECRET") 
            if callback_url: found_vars.append("SCHWAB_CALLBACK_URL")
            if token_path: found_vars.append("SCHWAB_TOKEN_PATH")
            
            console.print(f"🔑 Found environment variables: {', '.join(found_vars)}", style="green")
        else:
            console.print("⚠️  No environment variables found, will prompt for input", style="yellow")
    
    # Prompt for missing values
    if not RICH_AVAILABLE:
        if not api_key:
            api_key = input("Enter Schwab API Key: ")
        if not app_secret:
            app_secret = input("Enter Schwab App Secret: ")
        if not callback_url:
            callback_url = input("Enter Callback URL (optional): ") or "https://localhost:8080"
        if not token_path:
            token_path = input("Enter token file path: ") or "schwab_token.json"
    else:
        if not api_key:
            api_key = Prompt.ask("Enter Schwab API Key")
        if not app_secret:
            app_secret = Prompt.ask("Enter Schwab App Secret", password=True)
        if not callback_url:
            callback_url = Prompt.ask("Enter Callback URL", default="https://localhost:8080")
        if not token_path:
            token_path = Prompt.ask("Enter token file path", default="schwab_token.json")
    
    config = {
        "api_key": api_key,
        "app_secret": app_secret,
        "callback_url": callback_url,
        "token_file": token_path
    }
    
    # Save config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    if console:
        console.print(f"✅ Configuration saved to {config_file}")
        console.print("💡 Tip: Set environment variables to avoid prompts:")
        console.print("   export SCHWAB_API_KEY='your_key'")
        console.print("   export SCHWAB_APP_SECRET='your_secret'")
        console.print("   export SCHWAB_TOKEN_PATH='schwab_token.json'")
    else:
        print(f"Configuration saved to {config_file}")
        print("Tip: Set environment variables SCHWAB_API_KEY, SCHWAB_APP_SECRET, SCHWAB_TOKEN_PATH")
    
    return config


# === EXAMPLE USAGE ===

def demo_live_trading():
    """
    Demonstrate live trading capabilities with preview functionality
    
    NOTE: This is a demo - be very careful with live trading!
    """
    
    console = Console() if RICH_AVAILABLE else None
    
    print("=== Live Trading Demo with Preview ===")
    print("WARNING: This would place real orders if connected to live account!")
    print()
    
    # Load configuration (this would normally be real credentials)
    config_file = "schwab_config.json"
    if not Path(config_file).exists():
        print("No configuration found. Run setup_schwab_config() first.")
        return
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return
    
    # Initialize trader (this would fail without real credentials)
    try:
        trader = SchwabEZTrader(
            token_file=config["token_file"],
            api_key=config["api_key"],
            app_secret=config["app_secret"],
            config=EZConfig(require_confirmation=True)  # Safety first!
        )
        
        # Enable paper trading for demo
        trader.paper_trade_mode(True)
        
        # Show portfolio
        trader.show_portfolio_summary()
        
        print("\n=== Enhanced Order Examples with Preview ===")
        
        # 1. Simple order with preview validation
        print("\n1. Buy Order with Preview Validation:")
        buy_order = trader.buy('AAPL', 10, limit=150.00)
        
        # Preview the order first
        print("   Previewing order...")
        preview = trader.validate_order(buy_order)
        
        # Get cost estimate
        costs = trader.estimate_costs(buy_order)
        if 'error' not in costs:
            print(f"   Estimated total cost: ${costs['total_cost']:.2f}")
            
        # Submit with smart validation
        trader.ez.smart_submit(buy_order, max_cost=10.00)
        
        # 2. Complex strategy with validation
        print("\n2. Vertical Spread with Enhanced Validation:")
        spread = trader.vertical_spread(
            'AAPL240315C00150000',
            'AAPL240315C00160000', 
            contracts=1,
            net_price=3.00,
            order_type="NET_DEBIT"
        )
        
        # Use smart validation
        if trader.smart_order_validation(spread):
            print("   ✅ Strategy passed validation")
            trader.submit_order(spread)
        else:
            print("   ❌ Strategy failed validation")
        
        # 3. Batch order submission
        print("\n3. Batch Order Submission:")
        orders = [
            trader.buy('AAPL', 50, limit=150.00),
            trader.buy('MSFT', 25, limit=400.00),
            trader.buy('GOOGL', 5, limit=2800.00)
        ]
        
        responses = trader.ez.batch_submit(
            orders,
            pause_between=1.0,
            stop_on_error=False
        )
        
        print(f"   Submitted {len([r for r in responses if r])} orders successfully")
        
        # 4. Bracket order with preview
        print("\n4. Bracket Order (Entry + Profit + Stop):")
        bracket = trader.bracket_order(
            'AAPL', 100,
            entry_price=150.00,
            profit_target=160.00,
            stop_loss=140.00
        )
        
        # Preview the complex conditional order
        trader.validate_order(bracket)
        trader.submit_order(bracket)
        
    except Exception as e:
        print(f"Demo failed (expected without real credentials): {e}")
        print("\nThis demonstrates the enhanced functionality:")
        print("✅ Order preview and validation")
        print("✅ Cost estimation") 
        print("✅ Paper trading mode")
        print("✅ Smart order submission")
        print("✅ Batch processing")
        print("✅ Enhanced error handling")


def real_world_examples():
    """Show real-world usage patterns with environment variables"""
    
    print("=== Real-World Usage Examples with Environment Variables ===\n")
    
    # This shows how you would use it in practice
    code_examples = """
# 1. Setup with Environment Variables (Recommended)
# First, set your environment variables:
export SCHWAB_API_KEY='your_api_key_here'
export SCHWAB_APP_SECRET='your_app_secret_here'
export SCHWAB_TOKEN_PATH='schwab_token.json'

# Then use the simple constructor:
from schwab_integration_example import create_trader_from_env

trader = create_trader_from_env()
# Automatically loads credentials from environment

# 2. Check Environment Setup
from schwab_integration_example import check_env_setup

env_status = check_env_setup()
if env_status['SCHWAB_API_KEY'] and env_status['SCHWAB_APP_SECRET']:
    trader = create_trader_from_env()
else:
    print("Please set environment variables first")

# 3. Interactive Environment Setup
from schwab_integration_example import setup_env_vars_interactively

setup_env_vars_interactively()
# Shows you the exact export commands to run

# 4. Enhanced Validation with Environment Credentials
trader = create_trader_from_env()
trader.paper_trade_mode(True)  # Safe testing

# Preview order first to see costs and validation
order = trader.buy('AAPL', 100, limit=150.50)
preview = trader.validate_order(order)
costs = trader.estimate_costs(order)
print(f"Estimated cost: ${costs['total_cost']:.2f}")

# Submit with automatic validation and cost limits
response = trader.ez.smart_submit(order, max_cost=5.00)

# 5. Complex Strategy with Environment Setup
trader = create_trader_from_env()

strategy = trader.vertical_spread(
    'AAPL240315C00150000', 
    'AAPL240315C00160000',
    contracts=1, 
    net_price=3.00,
    order_type="NET_DEBIT"
)

# Validate the complex order
if trader.smart_order_validation(strategy):
    trader.submit_order(strategy)
else:
    print("Strategy failed validation")

# 6. Batch Orders with Environment Credentials
trader = create_trader_from_env()
trader.paper_trade_mode(True)  # Safe mode

orders = [
    trader.buy('AAPL', 50, limit=150.00),
    trader.buy('GOOGL', 10, limit=2800.00),
    trader.buy('MSFT', 25, limit=400.00)
]

# Submit all orders with pauses and validation
responses = trader.ez.batch_submit(
    orders, 
    pause_between=2.0,
    stop_on_error=True
)

# 7. Docker/Container Usage
# In your Dockerfile or docker-compose.yml:
# environment:
#   - SCHWAB_API_KEY=your_key
#   - SCHWAB_APP_SECRET=your_secret
#   - SCHWAB_TOKEN_PATH=/app/tokens/schwab_token.json

# Then in your Python code:
trader = create_trader_from_env()  # Just works!

# 8. CI/CD Pipeline Usage
# In your GitHub Actions, GitLab CI, etc.:
# Set environment variables as secrets
# Then your code just works without hardcoded credentials

def main():
    # Check if environment is set up
    env_status = check_env_setup()
    
    if all(env_status[var] for var in ['SCHWAB_API_KEY', 'SCHWAB_APP_SECRET', 'SCHWAB_TOKEN_PATH']):
        # Environment is ready - start trading
        trader = create_trader_from_env()
        trader.paper_trade_mode(True)
        
        # Your trading logic here
        order = trader.buy('AAPL', 100, limit=150.00)
        trader.submit_order(order)
    else:
        # Environment needs setup
        print("Environment variables not set. Run:")
        print("from schwab_integration_example import setup_env_vars_interactively")
        print("setup_env_vars_interactively()")

# 9. Fallback Pattern (Environment + Manual)
try:
    # Try environment first
    trader = create_trader_from_env()
    print("✅ Connected using environment variables")
except ValueError:
    # Fall back to manual entry
    print("⚠️ Environment variables not found, using manual setup")
    config = setup_schwab_config()
    trader = SchwabEZTrader(
        token_file=config["token_file"],
        api_key=config["api_key"],
        app_secret=config["app_secret"]
    )

# 10. Automated Trading Script Template
import os
import sys

def automated_trading_main():
    # Verify environment
    required_vars = ['SCHWAB_API_KEY', 'SCHWAB_APP_SECRET', 'SCHWAB_TOKEN_PATH']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Connect and trade
    trader = create_trader_from_env()
    trader.paper_trade_mode(False)  # Live trading
    
    # Your automated strategy here
    orders = build_daily_strategy()
    for order in orders:
        if trader.smart_order_validation(order):
            trader.submit_order(order)
            
if __name__ == "__main__":
    automated_trading_main()
"""
    
    print(code_examples)


if __name__ == "__main__":
    print("Schwab-py Integration Example")
    print("=" * 40)
    
    if not SCHWAB_PY_AVAILABLE:
        print("❌ schwab-py not installed")
        print("Install with: pip install schwab-py")
    else:
        print("✅ schwab-py available")
    
    if not RICH_AVAILABLE:
        print("❌ rich not installed")
        print("Install with: pip install rich")
    else:
        print("✅ rich available")
    
    print("\nTo get started:")
    print("1. Set up Schwab API credentials")
    print("2. Run setup_schwab_config()")
    print("3. Initialize SchwabEZTrader")
    print("4. Start trading with the simplified API!")
    
    print("\n" + "=" * 40)
    real_world_examples()
