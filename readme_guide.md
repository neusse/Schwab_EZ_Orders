# EZ Schwab Orders

A simplified, user-friendly wrapper for the Schwab API that makes order creation 10x easier while maintaining full compatibility with schwab-py.

## 🚀 Quick Start

### 1. Installation

```bash
# Required for live trading
pip install schwab-py

# Optional for better console output  
pip install rich
```

### 2. File Setup

Make sure all these files are in the same directory:
- `schwab_order_builder.py` - Core order building
- `schwab_strategies.py` - Pre-built strategies
- `schwab_ez_orders.py` - Main interface
- `schwab_integration_example.py` - Live trading integration
- `quick_start_guide.py` - Examples and tutorials
- `test_installation.py` - Test script

### 3. Test Installation

```bash
python test_installation.py
```

This will verify all modules are working correctly.

### 4. Run Examples

```bash
python quick_start_guide.py
```

## 🎯 Key Features

### ✅ **Simple Fluent API**
```python
# Before (complex)
from schwab.orders.generic import OrderBuilder
from schwab.orders.common import OrderType, Session, Duration

order = OrderBuilder()
order.set_session(Session.NORMAL)
order.set_duration(Duration.DAY) 
order.set_order_type(OrderType.LIMIT)
order.set_price("150.50")
order.add_equity_leg(EquityInstruction.BUY, "AAPL", 100)

# After (simple)
order = OrderBuilder().buy('AAPL').shares(100).limit(150.50).day()
```

### ✅ **Pre-built Strategies**
```python
# Covered Call
strategy = ez.covered_call('AAPL')
strategy.buy_stock(100).at_limit(150.00)
strategy.sell_call('AAPL240315C00160000', 1).at_limit(3.50)

# Iron Condor (single order)
ic = ez.iron_condor_order(
    put_spread_long='SPY240315P00395000',
    put_spread_short='SPY240315P00400000',
    call_spread_short='SPY240315C00420000',
    call_spread_long='SPY240315C00425000',
    contracts=1, net_credit=2.00
)
```

### ✅ **Paper Trading with Real Validation**
```python
trader = SchwabEZTrader(token_file="...", api_key="...", app_secret="...")
trader.paper_trade_mode(True)  # Use Schwab's preview endpoint

# All orders now validated but not executed
preview = trader.validate_order(order)
costs = trader.estimate_costs(order)
trader.submit_order(order)  # Shows validation results
```

### ✅ **Advanced Order Types**
```python
# Trailing Stop
trailing = ez.trailing_stop_loss('AAPL', 100, trail_amount=10.0)

# Bracket Order (Entry + Profit + Stop)
bracket = ez.bracket_order('AAPL', 100, 
                          entry_price=150.00,
                          profit_target=160.00, 
                          stop_loss=140.00)

# Vertical Spread (NET_DEBIT)
spread = ez.vertical_spread('AAPL240315C00150000', 'AAPL240315C00160000',
                           contracts=1, net_price=3.00)
```

### ✅ **Safety Features**
```python
# Smart submission with cost limits
trader.ez.smart_submit(order, max_cost=10.00)

# Enhanced validation
if trader.smart_order_validation(order):
    trader.submit_order(order)

# Batch operations with error handling
responses = trader.ez.batch_submit(orders, pause_between=2.0, stop_on_error=True)
```

## 📁 Module Overview

| File | Purpose |
|------|---------|
| `schwab_order_builder.py` | Core fluent API for building orders |
| `schwab_strategies.py` | Pre-built options strategies |
| `schwab_ez_orders.py` | Main interface with safety features |
| `schwab_integration_example.py` | Live trading with schwab-py |
| `quick_start_guide.py` | Examples and tutorials |
| `test_installation.py` | Verify installation |

## 🔧 Setup for Live Trading

### 1. Get Schwab API Credentials
- Register at Schwab Developer Portal
- Get API Key and App Secret
- Generate token file

### 2. Configure Connection (Environment Variables - Recommended)

**Option A: Environment Variables (Recommended)**
```bash
# Set environment variables (add to ~/.bashrc, ~/.zshrc, etc.)
export SCHWAB_API_KEY='your_api_key_here'
export SCHWAB_APP_SECRET='your_app_secret_here'
export SCHWAB_TOKEN_PATH='schwab_token.json'
export SCHWAB_CALLBACK_URL='https://localhost:8080'  # optional
```

Then use the simple setup:
```python
from schwab_integration_example import create_trader_from_env

# Automatically loads from environment
trader = create_trader_from_env()
```

**Option B: Interactive Setup**
```python
from schwab_integration_example import setup_env_vars_interactively

# Shows you the export commands to run
setup_env_vars_interactively()
```

**Option C: Manual Configuration**
```python
trader = SchwabEZTrader(
    token_file="schwab_token.json",
    api_key="your_api_key",
    app_secret="your_app_secret"
)
```

### 3. Verify Setup
```python
from schwab_integration_example import check_env_setup

# Check which environment variables are set
env_status = check_env_setup()
```

### 4. Start Trading
```python
# Enable paper trading for testing
trader.paper_trade_mode(True)

# Create and submit orders
order = trader.buy('AAPL', 100, limit=150.50)
trader.submit_order(order)

# Switch to live trading (be careful!)
trader.paper_trade_mode(False)
```

## 📚 Examples

### Simple Stock Order
```python
from schwab_ez_orders import EZOrders

ez = EZOrders()
order = ez.buy('AAPL', 100, limit=150.50)
print(order.build())  # Shows Schwab API JSON
```

### Complex Options Strategy
```python
# Bull Call Spread as single NET_DEBIT order
spread = ez.vertical_spread(
    'AAPL240315C00150000',  # Long call
    'AAPL240315C00160000',  # Short call
    contracts=1,
    net_price=3.00,
    order_type="NET_DEBIT"
)
```

### Paper Trading Workflow
```python
# Using environment variables
trader = create_trader_from_env()
trader.paper_trade_mode(True)

# Validate order first
preview = trader.validate_order(order)
validation = preview.get('orderValidationResult', {})

if not validation.get('rejects'):
    costs = trader.estimate_costs(order)
    print(f"Estimated cost: ${costs['total_cost']:.2f}")
    trader.submit_order(order)
```

### Environment Variables Benefits

**✅ Security**: No credentials in source code  
**✅ Flexibility**: Different credentials per environment  
**✅ CI/CD Ready**: Works with GitHub Actions, Docker, etc.  
**✅ Team Friendly**: Each developer uses their own credentials  
**✅ Simple**: One line to create trader: `create_trader_from_env()`

**Environment Variable Reference:**
- `SCHWAB_API_KEY` - Your Schwab API key (required)
- `SCHWAB_APP_SECRET` - Your Schwab app secret (required)  
- `SCHWAB_TOKEN_PATH` - Path to token file (required)
- `SCHWAB_CALLBACK_URL` - OAuth callback URL (optional)

## 🛡️ Safety Features

- **Order validation** using Schwab's preview endpoint
- **Cost estimation** before submission
- **Confirmation prompts** for large orders
- **Value limits** to prevent accidental large trades
- **Paper trading mode** for safe testing
- **Batch error handling** 
- **Order history** tracking

## 🎯 Supported Order Types

- **Market/Limit/Stop orders**
- **Trailing stops** with offset configuration
- **NET_DEBIT/NET_CREDIT** spreads
- **Conditional orders** (OCO, One Triggers Another)
- **Complex strategies** (Vertical, Iron Condor, Straddle, etc.)
- **Multi-leg single orders**

## 🔍 Troubleshooting

### Import Errors
```bash
# Test installation
python test_installation.py

# Common fixes:
# 1. All .py files in same directory
# 2. Install dependencies: pip install rich schwab-py
# 3. Check Python version (3.7+ required)
```

### API Connection Issues
- Verify Schwab API credentials
- Check token file is valid and accessible
- Ensure API key and app secret are correct
- Test with paper trading mode first

### Order Rejections
- Use preview endpoint to see Schwab's validation
- Check order format against Schwab documentation
- Verify account has sufficient buying power
- Confirm options trading permissions if using options

## 📞 Support

- Check `test_installation.py` output for diagnostics
- Review `quick_start_guide.py` for examples
- Ensure all dependencies are installed
- Verify Schwab API credentials are correct

## ⚠️ Important Notes

- **Always test with paper trading mode first**
- **Real orders execute immediately - be careful!**
- **Respect Schwab API rate limits** (up to 120 requests/minute)
- **Options require appropriate account permissions**
- **This is not investment advice**

---

**Ready to simplify your Schwab trading? Start with `python test_installation.py`** 🚀
