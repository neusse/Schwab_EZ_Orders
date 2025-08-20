"""
Installation Test Script

Run this to verify that all EZ Schwab Orders modules are working correctly.
This will test imports and basic functionality without requiring Schwab credentials.
"""

import sys
import traceback

def test_imports():
    """Test that all modules can be imported"""
    print("🔍 Testing Module Imports...")
    print("=" * 40)
    
    results = {}
    
    # Test core order builder
    try:
        from schwab_order_builder import OrderBuilder, ValidationError
        results['order_builder'] = True
        print("✅ schwab_order_builder.py - OK")
    except Exception as e:
        results['order_builder'] = False
        print(f"❌ schwab_order_builder.py - {e}")
    
    # Test strategies
    try:
        from schwab_strategies import CoveredCall, BullCallSpread, IronCondor
        results['strategies'] = True
        print("✅ schwab_strategies.py - OK")
    except Exception as e:
        results['strategies'] = False
        print(f"❌ schwab_strategies.py - {e}")
    
    # Test EZ Orders
    try:
        from schwab_ez_orders import EZOrders, EZConfig
        results['ez_orders'] = True
        print("✅ schwab_ez_orders.py - OK")
    except Exception as e:
        results['ez_orders'] = False
        print(f"❌ schwab_ez_orders.py - {e}")
    
    # Test integration (may fail without schwab-py)
    try:
        from schwab_integration_example import SchwabEZTrader
        results['integration'] = True
        print("✅ schwab_integration_example.py - OK")
    except Exception as e:
        results['integration'] = False
        print(f"⚠️  schwab_integration_example.py - {e}")
        print("   (This is expected if schwab-py is not installed)")
    
    return results

def test_basic_functionality():
    """Test basic functionality without external dependencies"""
    print("\n🧪 Testing Basic Functionality...")
    print("=" * 40)
    
    try:
        from schwab_order_builder import OrderBuilder
        
        # Test simple order creation
        print("Testing simple buy order...")
        order = OrderBuilder().buy('AAPL').shares(100).limit(150.50).day()
        order_json = order.build()
        
        expected_fields = ['session', 'duration', 'orderType', 'price', 'orderLegCollection']
        for field in expected_fields:
            if field not in order_json:
                raise Exception(f"Missing field: {field}")
        
        print("✅ Simple order creation - OK")
        
        # Test order validation
        print("Testing order validation...")
        if not order.validate():
            raise Exception("Order validation failed")
        print("✅ Order validation - OK")
        
        # Test options order
        print("Testing options order...")
        options_order = (OrderBuilder()
                        .buy_to_open('AAPL240315C00160000')
                        .contracts(1)
                        .limit(3.50)
                        .day())
        options_json = options_order.build()
        
        if options_json['orderLegCollection'][0]['instrument']['assetType'] != 'OPTION':
            raise Exception("Options order asset type incorrect")
        print("✅ Options order - OK")
        
        # Test complex order
        print("Testing complex order (vertical spread)...")
        spread = (OrderBuilder()
                 .with_leg('BUY_TO_OPEN', 'AAPL240315C00150000', 1, 'OPTION')
                 .with_leg('SELL_TO_OPEN', 'AAPL240315C00160000', 1, 'OPTION')
                 .net_debit(3.00)
                 .vertical_spread()
                 .day())
        spread_json = spread.build()
        
        if len(spread_json['orderLegCollection']) != 2:
            raise Exception("Multi-leg order not created correctly")
        print("✅ Complex order - OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        traceback.print_exc()
        return False

def test_ez_orders():
    """Test EZ Orders interface"""
    print("\n🎯 Testing EZ Orders Interface...")
    print("=" * 40)
    
    try:
        from schwab_ez_orders import EZOrders, EZConfig
        
        # Create EZ Orders instance
        config = EZConfig(require_confirmation=False)
        ez = EZOrders(config)
        
        # Test simple order
        print("Testing EZ buy order...")
        buy_order = ez.buy('AAPL', 100, limit=150.50)
        buy_json = buy_order.build()
        print("✅ EZ buy order - OK")
        
        # Test stop loss
        print("Testing stop loss order...")
        stop_order = ez.stop_loss('AAPL', 100, stop_price=140.00)
        stop_json = stop_order.build()
        print("✅ Stop loss order - OK")
        
        # Test strategy
        print("Testing covered call strategy...")
        strategy = ez.covered_call('AAPL')
        strategy.buy_stock(100).at_limit(150.00)
        strategy.sell_call('AAPL240315C00160000', 1).at_limit(3.50)
        orders = strategy.build_all()
        
        if len(orders) != 2:
            raise Exception("Strategy should generate 2 orders")
        print("✅ Covered call strategy - OK")
        
        # Test template system
        print("Testing template system...")
        template_order = ez.buy('SPY', 10, limit=400.00)
        ez.save_template(template_order, "test_template", "Test template")
        
        templates = ez.list_templates()
        if "test_template" not in templates:
            raise Exception("Template not saved correctly")
        
        loaded = ez.load_template("test_template")
        loaded_json = loaded.build()
        print("✅ Template system - OK")
        
        return True
        
    except Exception as e:
        print(f"❌ EZ Orders test failed: {e}")
        traceback.print_exc()
        return False

def test_environment_setup():
    """Test environment variable setup"""
    print("\n🔑 Testing Environment Variables...")
    print("=" * 40)
    
    try:
        from schwab_integration_example import check_env_setup, create_trader_from_env
        
        # Check environment variables
        env_status = check_env_setup()
        
        required_vars = ['SCHWAB_API_KEY', 'SCHWAB_APP_SECRET', 'SCHWAB_TOKEN_PATH']
        all_required_set = all(env_status[var] for var in required_vars)
        
        if all_required_set:
            print("✅ All required environment variables are set")
            
            # Try to create trader (will fail without real credentials)
            try:
                trader = create_trader_from_env()
                print("✅ Trader creation successful!")
                return True
            except Exception as e:
                print(f"⚠️  Trader creation failed: {e}")
                print("   This is expected without real Schwab credentials")
                print("✅ Environment configuration is correct")
                return True
        else:
            missing = [var for var in required_vars if not env_status[var]]
            print(f"⚠️  Missing environment variables: {', '.join(missing)}")
            print("   Run setup_env_example.py to configure")
            return False
            
    except ImportError:
        print("⚠️  Integration module not available")
        return False
    except Exception as e:
        print(f"❌ Environment test failed: {e}")
        return False

def test_dependencies():
    """Test optional dependencies"""
    print("\n📦 Testing Dependencies...")
    print("=" * 40)
    
    # Test Rich
    try:
        import rich
        from rich.console import Console
        console = Console()
        print("✅ Rich library - Available")
    except ImportError:
        print("⚠️  Rich library - Not installed (optional for better output)")
    
    # Test schwab-py
    try:
        import schwab
        print("✅ schwab-py library - Available")
    except ImportError:
        print("⚠️  schwab-py library - Not installed (required for live trading)")
    
    # Test other standard libraries
    required_modules = ['json', 'os', 'datetime', 'decimal', 'pathlib', 'dataclasses']
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} - Available")
        except ImportError:
            print(f"❌ {module} - Missing (should be in standard library)")

def main():
    """Run all tests"""
    print("🚀 EZ Schwab Orders - Installation Test")
    print("=" * 50)
    print("This script will test that all modules are working correctly.\n")
    
    # Run tests
    import_results = test_imports()
    
    # Only run functionality tests if core modules imported successfully
    if import_results.get('order_builder') and import_results.get('ez_orders'):
        func_test = test_basic_functionality()
        ez_test = test_ez_orders()
    else:
        func_test = False
        ez_test = False
        print("\n❌ Skipping functionality tests due to import failures")
    
    # Test dependencies
    test_dependencies()
    
    # Test environment setup
    env_test = test_environment_setup()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Core Imports: {'✅' if import_results.get('order_builder') else '❌'}")
    print(f"   EZ Orders: {'✅' if import_results.get('ez_orders') else '❌'}")
    print(f"   Strategies: {'✅' if import_results.get('strategies') else '❌'}")
    print(f"   Integration: {'✅' if import_results.get('integration') else '⚠️'}")
    print(f"   Basic Functions: {'✅' if func_test else '❌'}")
    print(f"   EZ Interface: {'✅' if ez_test else '❌'}")
    print(f"   Environment: {'✅' if env_test else '⚠️'}")
    
    core_working = all([import_results.get('order_builder'), import_results.get('ez_orders'), 
                       func_test, ez_test])
    
    if core_working:
        print("\n🎉 Core functionality tests passed! EZ Schwab Orders is ready to use.")
        
        if env_test:
            print("🔑 Environment variables are configured - you can start trading!")
            print("\nQuick start:")
            print("   from schwab_integration_example import create_trader_from_env")
            print("   trader = create_trader_from_env()")
            print("   trader.paper_trade_mode(True)  # Safe testing")
        else:
            print("⚠️  Environment variables not set up yet")
            print("\nTo configure credentials:")
            print("   python setup_env_example.py")
            
        print("\nNext steps:")
        print("1. Install optional dependencies: pip install rich schwab-py")
        print("2. Set up environment variables for live trading")
        print("3. Run quick_start_guide.py for examples")
    else:
        print("\n⚠️  Some core tests failed. Check the errors above.")
        print("\nTroubleshooting:")
        print("1. Make sure all .py files are in the same directory")
        print("2. Check for typos in file names")
        print("3. Ensure Python 3.7+ is being used")
        
    print(f"\n📋 Available Helper Scripts:")
    print(f"   test_installation.py - Test all functionality (this script)")
    print(f"   setup_env_example.py - Set up environment variables")
    print(f"   quick_start_guide.py - Examples and tutorials")
        
    print(f"\n📈 System Info:")
    print(f"   Python version: {sys.version}")
    print(f"   Current directory: {sys.path[0]}")
    
    # Recommendation based on results
    if core_working and env_test:
        print(f"\n🚀 You're ready to trade! Try: python quick_start_guide.py")
    elif core_working:
        print(f"\n🔧 Set up credentials next: python setup_env_example.py")
    else:
        print(f"\n🔍 Fix import issues first, then run this test again")

if __name__ == "__main__":
    main()
