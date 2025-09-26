# Pacifica DEX API & SDK Documentation

## Overview
Pacifica is a perpetual futures DEX that provides both REST and WebSocket APIs for trading operations, market data, and account management.

## Resources
- **API Documentation**: https://docs.pacifica.fi/api-documentation/api
- **Python SDK**: https://github.com/pacifica-fi/python-sdk
- **Support**: Discord API channel

## Python SDK

### Installation
```bash
pip3 install -r requirements.txt
```

### Repository Structure
- `rest/` - REST API examples
- `ws/` - WebSocket API examples  
- `common/` - Shared utilities

### Usage Examples

#### REST API
```python
# Modify PRIVATE_KEY in example files
python3 -m rest.create_order
```

#### WebSocket API
```python
# Modify PRIVATE_KEY in example files
python3 -m ws.create_order
```

## Authentication

### Methods
- **Private Key**: Required for authenticated endpoints
- **API Agent Keys**: Supported for programmatic access
- **Hardware Wallet**: Compatible with hardware wallet signing
- **Signing**: Custom signing implementation required

### Configuration
- Set `PRIVATE_KEY` in SDK example files
- Authentication headers required for protected endpoints

## REST API Endpoints

### Categories

#### Markets
- Market information
- Available trading pairs
- Contract specifications

#### Prices & Market Data
- Current prices
- Kline/Candle data
- 24h statistics
- Funding rates

#### Order Book
- Order book depth
- Best bid/ask
- Market depth analysis

#### Trades
- Recent trades
- Trade history
- Market trades feed

#### Account Management
- Account info retrieval
- Balance information
- Subaccount management
- API key management

#### Positions
- Open positions
- Position history
- P&L calculations
- Leverage management

#### Orders
- Place orders (market, limit, stop)
- Cancel orders
- Modify orders
- Batch order operations
- Order status
- Order history

#### Trading Operations
- **Order Types**:
  - Market orders
  - Limit orders
  - Stop orders
  - Take-profit/Stop-loss orders
- **Position Management**:
  - Set leverage
  - Update margin mode
  - Close positions
- **Advanced Features**:
  - Batch order processing
  - Position TP/SL management

## WebSocket API

### Subscriptions Available
- **Market Data**:
  - Real-time prices
  - Order book updates
  - Trade feed
  - Market statistics

- **Account Data** (Authenticated):
  - Account balance updates
  - Position changes
  - Order status updates
  - Fill notifications

### Connection Management
- Persistent WebSocket connections
- Automatic reconnection support
- Heartbeat/ping-pong mechanism

## Rate Limits
- Configurable API rate limits
- Rate limit multiplier available
- Different limits for REST vs WebSocket
- Account-specific rate limiting

## Error Handling

### Error Codes
- Comprehensive error code documentation
- Detailed error messages
- Error handling guidelines

### Common Errors
- Authentication failures
- Insufficient balance
- Invalid order parameters
- Rate limit exceeded
- Market closed

## Unique Features

1. **Subaccount System**
   - Create and manage multiple subaccounts
   - Isolated margin per subaccount
   - Transfer between subaccounts

2. **Advanced Order Management**
   - Batch order operations
   - Position-based TP/SL
   - Order modification without cancellation

3. **Flexible Authentication**
   - Multiple authentication methods
   - Hardware wallet support
   - API agent keys for automated trading

4. **Comprehensive Market Data**
   - Deep order book access
   - Historical trade data
   - Funding rate history
   - Detailed kline/candle data

## Implementation Notes

### SDK Capabilities
- Obtain market data
- Monitor account information  
- Place and cancel orders
- Support for both REST and WebSocket APIs

### Integration Considerations
1. **Authentication Setup**
   - Configure private key securely
   - Implement proper signing mechanism
   - Handle API keys appropriately

2. **WebSocket Management**
   - Maintain persistent connections
   - Handle reconnection logic
   - Process real-time updates efficiently

3. **Error Recovery**
   - Implement retry logic
   - Handle network interruptions
   - Process error codes appropriately

4. **Rate Limit Management**
   - Track API usage
   - Implement backoff strategies
   - Use WebSocket for real-time data when possible

## Getting Started

### Basic Setup
1. Install Python SDK dependencies
2. Configure authentication credentials
3. Choose REST or WebSocket based on use case
4. Implement error handling
5. Test with small amounts first

### Example Workflow
1. Connect to API
2. Authenticate with private key
3. Fetch market data
4. Check account balance
5. Place order
6. Monitor order status
7. Manage positions

## Support & Resources
- **Documentation**: https://docs.pacifica.fi/api-documentation/api
- **GitHub**: https://github.com/pacifica-fi/python-sdk
- **Discord**: Join their Discord for API support
- **Examples**: Check `rest/` and `ws/` folders in SDK

## Notes
- Always test on testnet first if available
- Keep private keys secure and never commit to version control
- Monitor rate limits to avoid throttling
- Use WebSocket for real-time data to reduce API load
- Refer to official documentation for latest updates