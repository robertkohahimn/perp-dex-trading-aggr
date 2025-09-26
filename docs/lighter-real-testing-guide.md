# Lighter Connector - Real Credentials Testing Guide

## ⚠️ IMPORTANT SAFETY NOTICE
This guide is for testing with REAL credentials and REAL funds. Please read all safety precautions before proceeding.

## Prerequisites

### 1. Get Your Private Key
- You need an Ethereum private key that has access to Lighter
- The key should start with "0x" followed by 64 hexadecimal characters
- **NEVER share or commit your private key**

### 2. Fund Your Account (for Mainnet)
- Ensure you have USDC in your Lighter account
- Start with a small amount (e.g., $50-100) for testing
- For testnet, get test USDC from a faucet

### 3. Set Up Environment

#### Option A: Environment Variable (Recommended)
```bash
export LIGHTER_PRIVATE_KEY='0x_your_private_key_here'
python3 test_lighter_real.py
```

#### Option B: Manual Entry (More Secure)
```bash
python3 test_lighter_real.py
# Enter key when prompted (hidden input)
```

## Test Script Features

### Safety Limits
The script includes built-in safety features:
- **MAX_ORDER_SIZE**: 0.001 (very small)
- **MAX_LOSS_USDC**: $10
- **PRICE_DEVIATION**: 50% from market (orders far from market price)
- **REQUIRE_CONFIRMATION**: All orders need explicit confirmation

### Test Flow

1. **Connection Test**
   - Connects to Lighter mainnet or testnet
   - Loads market symbols
   - Verifies API connectivity

2. **Authentication Test**
   - Authenticates with your private key
   - Displays your wallet address
   - Verifies account access

3. **Account Information**
   - Total balance
   - Available balance
   - Margin balance
   - Unrealized & realized P&L
   - Margin ratio

4. **Position Check**
   - Lists all open positions
   - Shows P&L for each position
   - Displays leverage

5. **Open Orders Check**
   - Lists all open orders
   - Shows order details and status

6. **Market Data Test**
   - Gets current ETH-PERP price
   - Shows 24h volume
   - Displays bid/ask spread

7. **Interactive Tests** (Optional)
   - Order placement with safety checks
   - Leverage adjustment

## Running the Tests

### 1. Basic Test (Read-Only)
```bash
# Set your private key
export LIGHTER_PRIVATE_KEY='0x...'

# Run the test
python3 test_lighter_real.py

# Choose network (2 for testnet is safer)
# Choose option 3 to skip interactive tests
```

### 2. Full Test with Order Placement
```bash
# Run the test
python3 test_lighter_real.py

# Follow prompts:
1. Choose network (start with testnet)
2. Confirm authentication
3. Review account info
4. Choose "1" for order placement test
5. Select buy or sell
6. Confirm order details
7. Order will be placed far from market
8. Can immediately cancel if desired
```

## Example Output

```
============================================================
  Testing Connection
============================================================
✅ Connected to https://mainnet.zklighter.elliot.ai
ℹ️  Loaded 172 market symbols

============================================================
  Testing Authentication
============================================================
✅ Authenticated successfully
ℹ️  Address: 0x123...abc

============================================================
  Account Information
============================================================
ℹ️  Account ID: 0x123...abc
ℹ️  Total Balance: $1000.00 USDC
ℹ️  Available Balance: $800.00 USDC
ℹ️  Margin Balance: $200.00 USDC
ℹ️  Unrealized PnL: $50.00
ℹ️  Realized PnL: $25.00
```

## Safety Checklist

### Before Testing
- [ ] Using testnet first? (Recommended)
- [ ] Have small test amount only?
- [ ] Understand the risks?
- [ ] Private key secure and not logged?

### During Testing
- [ ] Review all prompts carefully
- [ ] Check order prices before confirming
- [ ] Start with smallest possible size
- [ ] Cancel test orders after placement

### After Testing
- [ ] Orders cancelled or filled as expected?
- [ ] Account balance verified?
- [ ] Private key still secure?
- [ ] Test results saved?

## Troubleshooting

### Authentication Failed
- Verify private key format (0x + 64 hex chars)
- Check network selection (mainnet vs testnet)
- Ensure account exists on selected network

### Order Placement Failed
- Check account balance
- Verify market is open
- Ensure order size meets minimum requirements
- Check leverage settings

### Connection Issues
- Verify internet connection
- Check if Lighter API is accessible
- Try switching between mainnet/testnet

## Test Results

The script automatically exports results to a JSON file:
```
lighter_real_test_YYYYMMDD_HHMMSS.json
```

This includes:
- Timestamp
- Network used
- Test results (pass/fail)
- Account balance snapshot
- Number of open orders

## Best Practices

1. **Start Small**: Always test with minimal amounts
2. **Use Testnet First**: Validate everything on testnet
3. **Monitor Orders**: Watch order status in real-time
4. **Cancel Test Orders**: Remove test orders promptly
5. **Document Results**: Keep test logs for reference
6. **Secure Keys**: Never share or expose private keys

## Advanced Testing

### Custom Order Parameters
Edit `SafetyConfig` in the script:
```python
class SafetyConfig:
    MAX_ORDER_SIZE = Decimal("0.01")  # Increase size
    PRICE_DEVIATION = Decimal("0.3")  # Closer to market
```

### Test Specific Symbols
Modify the `test_market_data` call:
```python
await test_market_data(connector, "BTC-PERP")
```

### Automated Testing
Create a test configuration file and loop through test cases.

## Security Notes

1. **Never commit private keys** to version control
2. **Use environment variables** or secure key management
3. **Test on testnet first** before mainnet
4. **Monitor all transactions** carefully
5. **Keep test amounts small** to limit risk

## Support

If you encounter issues:
1. Check Lighter's API status
2. Verify account permissions
3. Review error messages in detail
4. Test with public endpoints first
5. Contact Lighter support for API issues