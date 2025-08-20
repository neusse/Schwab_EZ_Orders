"""
Quick Start Guide for EZ Schwab Orders

This guide shows you how to get started with the enhanced Schwab order system
from basic setup to advanced trading strategies with validation.

Installation:
    pip install schwab-py rich

Setup Steps:
    1. Get Schwab API credentials
    2. Run the setup process
    3. Start trading with simple commands
"""

# Try to import our modules, handle gracefully if not available
try:
    from schwab_ez_orders import EZOrders, EZConfig
    EZ_ORDERS_AVAILABLE = True
except ImportError as e:
    print(f"❌ EZ Orders not available: {e}")
    EZ_ORDERS_AVAILABLE = False

try:
    from schwab_integration_example import SchwabEZTrader, setup_schwab_config
    INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Integration module not fully available: {e}")
    INTEGRATION_AVAILABLE = False

def quick_setup():
    """Quick setup process for new users"""
    print("🚀 EZ Schwab Orders - Quick Setup")
    print("=" * 40)
    
    if not INTEGRATION_AVAILABLE:
        print("❌ Integration module not available")
        print("   Make sure all files are in the same directory:")
        print("   - schwab_order_builder.py")
        print("   - schwab_ez_orders.py") 
        print("   - schwab_integration_example.py")
        return None
    
    # Import here to avoid issues if module not available
    from schwab_integration_example import (
        check_env_setup, create_trader_from_env, 
        setup_env_vars_interactively, setup_schwab_config
    )
    
    # Step 1: Check environment variables first
    print("\nStep 1: Checking environment variables...")
    env_status = check_env_setup()
    
    required_vars = ['SCHWAB_API_KEY', 'SCHWAB_APP_SECRET', 'SCHWAB_TOKEN_PATH']
    all_required_set = all(env_status[var] for var in required_vars)
    
    if all_required_set:
        print("✅ Environment variables are set!")
        try:
            trader = create_trader_from_env()
            print("✅ Connected successfully using environment variables")
            return trader
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return None
    else:
        print("⚠️  Environment variables not set")
        print("\nChoose setup method:")
        print("1. Environment variables (recommended)")
        print("2. Config file (legacy)")
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            print("\nSetting up environment variables...")
            setup_env_vars_interactively()
            print("\n💡 After setting environment variables, restart and run:")
            print("   from schwab_integration_example import create_trader_from_env")
            print("   trader = create_trader_from_env()")
            return None
        else:
            print("\nUsing config file setup...")
            try:
                config = setup_schwab_config()
                print("✅ Credentials configured in file")
                return None  # Would need real credentials to actually connect
            except Exception as e:
                print(f"❌ Setup failed: {e}")
                return None

def basic_examples():
    """Show basic order examples"""
    print("\n📚 Basic Order Examples")
    print("=" * 30)
    
    if not EZ_ORDERS_AVAILABLE:
        print("❌ EZ Orders module not available")
        return
    
    # Create EZ Orders instance
    ez = EZOrders(EZConfig(require_confirmation=False))
    
    # Simple stock orders
    print("\n1. Simple Stock Orders:")
    
    # Buy order
    buy_order = ez.buy('AAPL', 1, limit=150.50)
    print(f"   Buy: {buy_order}")
    print(f"   JSON keys: {list(buy_order.build().keys())}\n")
    
    # Stop loss
    stop_order = ez.stop_loss('AAPL', 1, stop_price=140.00)
    print(f"   Stop Loss: {stop_order}")
    
    # Trailing stop
    trail_order = ez.trailing_stop_loss('AAPL', 1, trail_amount=5.00)
    print(f"   Trailing Stop: {trail_order}")
    
    print("\n2. Options Orders:")
    
    # Buy call
    call_order = ez.buy_call('AAPL240315C00160000', 1, limit=3.50)
    print(f"   Buy Call: {call_order}")
    
    # Vertical spread
    spread_order = ez.vertical_spread(
        'AAPL240315C00150000',
        'AAPL240315C00160000',
        contracts=1,
        net_price=3.00
    )
    print(f"   Vertical Spread: {spread_order}")

def strategy_examples():
    """Show strategy examples"""
    print("\n🎯 Strategy Examples")
    print("=" * 25)
    
    if not EZ_ORDERS_AVAILABLE:
        print("❌ EZ Orders module not available")
        return
    
    ez = EZOrders(EZConfig(require_confirmation=False))
    
    # Covered call
    print("\n1. Covered Call Strategy:")
    cc_strategy = ez.covered_call('AAPL')
    cc_strategy.buy_stock(100).at_limit(150.00)
    cc_strategy.sell_call('AAPL240315C00160000', 1).at_limit(3.50)
    
    orders = cc_strategy.build_all()
    print(f"   Orders generated: {len(orders)}")
    for i, order in enumerate(orders):
        print(f"   Order {i+1}: {order.get('orderType')} - {order.get('orderLegCollection', [{}])[0].get('instruction')}")
    
    # Iron Condor
    print("\n2. Iron Condor (Single Order):")
    ic_order = ez.iron_condor_order(
        put_spread_long='SPY240315P00395000',
        put_spread_short='SPY240315P00400000',
        call_spread_short='SPY240315C00420000', 
        call_spread_long='SPY240315C00425000',
        contracts=1,
        net_credit=2.00
    )
    print(f"   Iron Condor: {ic_order}")
    
    # Bracket order
    print("\n3. Bracket Order (Entry + Profit + Stop):")
    bracket_order = ez.bracket_order(
        'AAPL', 100,
        entry_price=150.00,
        profit_target=160.00,
        stop_loss=140.00
    )
    print(f"   Bracket Order: {bracket_order}")

def advanced_features():
    """Show advanced features"""
    print("\n🔥 Advanced Features")
    print("=" * 25)
    
    if not EZ_ORDERS_AVAILABLE:
        print("❌ EZ Orders module not available")
        return
    
    # Template system
    print("\n1. Template System:")
    ez = EZOrders()
    
    # Create and save template
    template_order = ez.buy('SPY', 10, limit=400.00)
    ez.save_template(template_order, "spy_dca", "SPY Dollar Cost Averaging")
    print("   ✅ Template saved: spy_dca")
    
    # List and load templates
    templates = ez.list_templates()
    print(f"   Available templates: {templates}")
    
    if templates:
        loaded = ez.load_template(templates[0])
        print(f"   Loaded template: {loaded}")
    
    # Batch operations
    print("\n2. Batch Operations:")
    orders = [
        ez.buy('AAPL', 50),
        ez.buy('MSFT', 25), 
        ez.buy('GOOGL', 5)
    ]
    print(f"   Created {len(orders)} orders for batch submission")
    
    # Portfolio helpers
    print("\n3. Portfolio Helpers:")
    adjustment = ez.quick_portfolio_adjustment(
        'AAPL', 
        current_shares=75,
        target_shares=100,
        limit_price=150.00
    )
    if adjustment:
        print(f"   Portfolio adjustment: {adjustment}")
    
    dca_order = ez.dollar_cost_average('VTI', 1000, 220.50)
    print(f"   DCA order: {dca_order}")

def paper_trading_demo():
    """Show paper trading capabilities"""
    print("\n📝 Paper Trading Demo")
    print("=" * 25)
    
    # This would work with real credentials
    print("\nWith real credentials, you could:")
    print("1. Enable paper trading mode:")
    print("   trader.paper_trade_mode(True)")
    print("   # All orders now use preview endpoint")
    
    print("\n2. Validate orders before submission:")
    print("   preview = trader.validate_order(order)")
    print("   costs = trader.estimate_costs(order)")
    
    print("\n3. Smart submission with limits:")
    print("   trader.ez.smart_submit(order, max_cost=10.00)")
    
    print("\n4. Enhanced validation:")
    print("   if trader.smart_order_validation(order):")
    print("       trader.submit_order(order)")

def main():
    """Main quick start function"""
    print("🎉 Welcome to EZ Schwab Orders!")
    print("A simplified, safe way to trade with Schwab")
    print("=" * 50)
    
    # Check if modules are available
    if not EZ_ORDERS_AVAILABLE:
        print("❌ Core modules not available. Please ensure all files are present:")
        print("   - schwab_order_builder.py")
        print("   - schwab_ez_orders.py")
        print("   - schwab_strategies.py")
        return
    
    # Setup
    trader = None
    if INTEGRATION_AVAILABLE:
        trader = quick_setup()
    else:
        print("\n⚠️  Integration example not available - showing basic functionality only")
    
    # Examples
    basic_examples()
    strategy_examples()
    advanced_features()
    paper_trading_demo()
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 Key Benefits:")
    print("✅ Simple fluent API instead of complex JSON")
    print("✅ Built-in safety features and validation")
    print("✅ Pre-built options strategies")
    print("✅ Paper trading with real Schwab validation")
    print("✅ Template system for reusable orders")
    print("✅ Batch operations and portfolio helpers")
    print("✅ Rich console output for better UX")
    
    print("\n🚀 Next Steps:")
    print("1. Set up your Schwab API credentials")
    print("2. Try paper trading mode to test strategies")
    print("3. Use templates for common orders")
    print("4. Leverage the preview endpoint for validation")
    print("5. Build complex strategies with simple code")
    
    print("\n📖 Documentation:")
    print("- schwab_order_builder.py - Core order building")
    print("- schwab_strategies.py - Pre-built strategies") 
    print("- schwab_ez_orders.py - Main interface")
    print("- schwab_integration_example.py - Live trading")
    
    print("\n🛠️  Helper Scripts:")
    print("- test_installation.py - Test all functionality")
    print("- setup_env_example.py - Set up environment variables")
    print("- quick_start_guide.py - This guide with examples")
    
    if trader:
        print(f"\n✅ You're connected and ready to trade!")
    else:
        print(f"\n⚠️  Set up credentials to start live/paper trading")
        if INTEGRATION_AVAILABLE:
            print("   Run: python setup_env_example.py")
        
    # Show module status
    print(f"\n📊 Module Status:")
    print(f"   EZ Orders: {'✅' if EZ_ORDERS_AVAILABLE else '❌'}")
    print(f"   Integration: {'✅' if INTEGRATION_AVAILABLE else '❌'}")
    
    if not all([EZ_ORDERS_AVAILABLE, INTEGRATION_AVAILABLE]):
        print(f"\n💡 To fix import issues:")
        print(f"   1. Make sure all .py files are in the same directory")
        print(f"   2. Install dependencies: pip install rich")
        print(f"   3. For full functionality: pip install schwab-py")
        print(f"   4. Test setup: python test_installation.py")

if __name__ == "__main__":
    main()
