# CLI Trading Interface Architecture

## Overview

The CLI (Command Line Interface) provides a powerful alternative to the REST API for trading operations. It offers both interactive and non-interactive modes, real-time monitoring, and direct access to all trading functionality.

## Design Principles

1. **Shared Business Logic**: CLI uses the same services layer as the API
2. **User-Friendly**: Intuitive commands with comprehensive help
3. **Real-Time Capable**: WebSocket support for live data streaming
4. **Secure**: Encrypted credential storage and secure authentication
5. **Flexible**: Supports both one-off commands and interactive sessions

## Architecture

```
┌─────────────────────────────────────────────────┐
│              User Interfaces                     │
├─────────────────┬────────────────────────────────┤
│   REST API      │        CLI Application         │
│  (FastAPI)      │         (Typer/Click)          │
├─────────────────┴────────────────────────────────┤
│              Services Layer                      │
│  (Shared Business Logic & Orchestration)         │
├──────────────────────────────────────────────────┤
│            Connectors Layer                      │
│      (DEX-specific Implementations)              │
├──────────────────────────────────────────────────┤
│           Database & Cache                       │
└──────────────────────────────────────────────────┘
```

## CLI Module Structure

```
cli/
├── __init__.py
├── main.py                 # CLI entry point
├── config.py              # CLI configuration management
├── auth.py                # Authentication & credential management
├── commands/
│   ├── __init__.py
│   ├── account.py         # Account management commands
│   ├── trade.py           # Trading commands
│   ├── market.py          # Market data commands
│   ├── position.py        # Position management
│   ├── monitor.py         # Real-time monitoring
│   └── config_cmd.py      # Configuration commands
├── formatters/
│   ├── __init__.py
│   ├── tables.py          # Table formatting
│   ├── charts.py          # Chart/graph display
│   └── colors.py          # Color schemes
├── interactive/
│   ├── __init__.py
│   ├── shell.py           # Interactive shell
│   ├── prompts.py         # User prompts
│   └── completions.py     # Auto-completions
└── utils/
    ├── __init__.py
    ├── validators.py      # Input validation
    ├── cache.py          # Local caching
    └── websocket.py      # WebSocket client
```

## Core CLI Commands

### 1. Account Management
```bash
# Login/authenticate
perp-dex auth login --dex hyperliquid --name main-account

# List accounts
perp-dex account list

# Show account balance
perp-dex account balance --dex hyperliquid --account main-account

# Add new DEX account
perp-dex account add --dex vest --name vest-trading
```

### 2. Trading Commands
```bash
# Place a limit order
perp-dex trade place --symbol BTC-PERP --side buy --size 0.1 --price 50000 --dex hyperliquid

# Place a market order
perp-dex trade market --symbol ETH-PERP --side sell --size 1.0 --dex lighter

# Cancel an order
perp-dex trade cancel --order-id abc123 --dex hyperliquid

# Cancel all orders
perp-dex trade cancel-all --symbol BTC-PERP --dex hyperliquid
```

### 3. Position Management
```bash
# List all positions
perp-dex position list

# Show position details
perp-dex position show --symbol BTC-PERP --dex hyperliquid

# Close a position
perp-dex position close --symbol ETH-PERP --size 0.5 --dex lighter

# Set stop loss / take profit
perp-dex position set-sl --symbol BTC-PERP --price 48000 --dex hyperliquid
perp-dex position set-tp --symbol BTC-PERP --price 55000 --dex hyperliquid
```

### 4. Market Data
```bash
# Show market summary
perp-dex market summary --dex hyperliquid

# Get order book
perp-dex market book --symbol BTC-PERP --dex hyperliquid --depth 20

# Show recent trades
perp-dex market trades --symbol ETH-PERP --dex lighter --limit 50

# Get funding rates
perp-dex market funding --symbol BTC-PERP --dex extended
```

### 5. Real-Time Monitoring
```bash
# Watch positions in real-time
perp-dex monitor positions --refresh 1

# Stream order book
perp-dex monitor book --symbol BTC-PERP --dex hyperliquid

# Watch account P&L
perp-dex monitor pnl --account all

# Multi-pane dashboard
perp-dex monitor dashboard
```

### 6. Interactive Mode
```bash
# Start interactive shell
perp-dex shell

# Interactive mode commands
> use hyperliquid main-account
> buy 0.1 BTC-PERP @ 50000
> sell 0.05 ETH-PERP @ market
> positions
> balance
> orders
> cancel all
> exit
```

## Configuration Management

### Configuration File (`~/.perp-dex/config.yaml`)
```yaml
default_dex: hyperliquid
default_account: main-account

accounts:
  hyperliquid:
    - name: main-account
      api_key: ${HYPERLIQUID_API_KEY}
      api_secret: ${HYPERLIQUID_API_SECRET}
      wallet: "0x..."
    - name: secondary
      api_key: ${HYPERLIQUID_API_KEY_2}
      api_secret: ${HYPERLIQUID_API_SECRET_2}
  
  lighter:
    - name: main
      api_key: ${LIGHTER_API_KEY}

display:
  colors: true
  table_style: fancy
  decimal_places: 4
  show_timestamps: true

monitoring:
  refresh_interval: 1000  # ms
  max_rows: 100
  
trading:
  confirm_orders: true
  default_leverage: 10
  max_position_size: 100000  # USD
  
websocket:
  reconnect_attempts: 5
  timeout: 30000  # ms
```

### Credential Storage
- Encrypted storage using system keyring
- Environment variable support
- Secure prompt for sensitive data
- Session-based authentication tokens

## Implementation Technologies

### Core Framework
- **Typer**: Modern CLI framework based on Python type hints
- **Rich**: Beautiful terminal formatting and display
- **Prompt Toolkit**: Interactive shell capabilities

### Display & Formatting
- **Rich Tables**: Formatted table output
- **Rich Live**: Real-time data updates
- **Plotext**: Terminal-based charts
- **Colorama**: Cross-platform colors

### Real-Time Features
- **Asyncio**: Async/await support
- **WebSockets**: Real-time data streaming
- **Threading**: Background monitoring

## CLI Features

### 1. Smart Order Parsing
```bash
# Natural language-like syntax
perp-dex trade "buy 0.1 BTC @ 50000 on hyperliquid"
perp-dex trade "sell 1 ETH at market on lighter"
```

### 2. Output Formats
```bash
# JSON output
perp-dex position list --output json

# CSV export
perp-dex trade history --output csv > trades.csv

# Pretty tables (default)
perp-dex account balance --output table
```

### 3. Scripting Support
```bash
# Batch operations
perp-dex batch < orders.txt

# Script mode (no confirmations)
perp-dex trade place --no-confirm --symbol BTC-PERP --side buy --size 0.1

# Watch mode
watch -n 1 'perp-dex position list --no-header'
```

### 4. Advanced Features
```bash
# Multi-DEX operations
perp-dex trade arbitrage --symbol BTC-PERP --size 1.0

# Risk analysis
perp-dex risk analyze --account all

# Performance report
perp-dex report performance --from 2024-01-01 --to 2024-01-31
```

## Error Handling

### User-Friendly Errors
```
❌ Order failed: Insufficient balance
   Required: 5000 USDC
   Available: 3000 USDC
   
   Try: perp-dex account deposit --amount 2000 --dex hyperliquid
```

### Verbose Mode
```bash
# Show detailed errors and debug info
perp-dex --verbose trade place ...

# Debug mode with full stack traces
perp-dex --debug trade place ...
```

## Testing Strategy

### CLI-Specific Tests
1. Command parsing tests
2. Output formatting tests
3. Interactive mode tests
4. Configuration management tests
5. Integration tests with services

### Test Commands
```bash
# Dry run mode (no actual trades)
perp-dex --dry-run trade place ...

# Test connection
perp-dex test connection --dex hyperliquid

# Validate configuration
perp-dex config validate
```

## Security Considerations

1. **Credential Management**
   - Never log sensitive data
   - Use system keyring for storage
   - Support hardware wallet signing

2. **Confirmation Prompts**
   - Require confirmation for large trades
   - Show risk warnings
   - Double-check critical operations

3. **Audit Trail**
   - Log all commands to audit file
   - Track command history
   - Export activity reports

## Performance Optimization

1. **Caching**
   - Cache market data locally
   - Store frequently used data
   - Intelligent cache invalidation

2. **Async Operations**
   - Non-blocking command execution
   - Parallel API calls
   - Background data fetching

3. **Efficient Display**
   - Incremental updates
   - Pagination for large datasets
   - Lazy loading

## User Experience

### Help System
```bash
# General help
perp-dex --help

# Command-specific help
perp-dex trade place --help

# Interactive help
perp-dex shell
> help
> help trade
```

### Auto-Completion
```bash
# Bash completion
perp-dex --install-completion bash

# Zsh completion
perp-dex --install-completion zsh

# Fish completion
perp-dex --install-completion fish
```

### Progress Indicators
- Loading spinners for long operations
- Progress bars for batch operations
- Real-time status updates

## Integration with Services

The CLI uses the same services layer as the API:

```python
# cli/commands/trade.py
from services.order_executor import OrderExecutor
from services.account_manager import AccountManager

@app.command()
async def place(
    symbol: str,
    side: str,
    size: float,
    price: Optional[float] = None,
    dex: str = None
):
    # Use shared service layer
    account = await account_manager.get_active_account(dex)
    order = await order_executor.place_order(
        account=account,
        symbol=symbol,
        side=side,
        size=size,
        price=price
    )
    # Format and display result
    display_order(order)
```

## Development Workflow

1. **Phase 2**: Implement core services (shared by API and CLI)
2. **Phase 3**: Build CLI framework and basic commands
3. **Phase 4**: Add first DEX connector
4. **Phase 5**: Implement API routes
6. **Phase 6**: Add interactive mode and monitoring
7. **Phase 7**: Polish UX and add advanced features

## Benefits of CLI Interface

1. **Power Users**: Faster for experienced traders
2. **Automation**: Easy to script and automate
3. **Low Latency**: Direct execution without HTTP overhead
4. **Flexibility**: Works in any terminal environment
5. **Integration**: Easy to integrate with other tools
6. **Monitoring**: Better for real-time monitoring
7. **Batch Operations**: Efficient for multiple operations