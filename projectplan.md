# Perp DEX Trading Backend - Project Plan

## Executive Summary

This document outlines the comprehensive plan for building a modular Python backend for Vamient's perpetual DEX trading terminal. The backend will support multiple perpetual DEX platforms (Hyperliquid, Lighter, Extended, EdgeX, Vest, Pacifica) with a unified API interface for the trading terminal.

## Core Requirements

1. **Modular Architecture**: Easy plug-and-play support for new DEX platforms
2. **Multi-Account Support**: Manage multiple accounts per DEX and across different DEXes
3. **Dual Interface**: Both REST API and CLI for maximum flexibility
4. **Standardized API**: Consistent REST/WebSocket API for the trading terminal
5. **Powerful CLI**: Command-line interface for power users and automation
6. **High Performance**: Async operations for concurrent trading activities
7. **Production Ready**: Robust error handling, logging, and monitoring

## Technology Stack

### Core Technologies
- **Language**: Python 3.11+
- **Web Framework**: FastAPI (async support, auto-documentation)
- **Async Runtime**: asyncio with aiohttp for concurrent operations
- **Database**: PostgreSQL (production) / SQLite (development)
- **Caching**: Redis for order queue and real-time data
- **Message Queue**: Redis Pub/Sub for event broadcasting
- **WebSockets**: FastAPI WebSocket support for real-time updates

### Libraries & Dependencies
- **pydantic**: Data validation and settings management
- **sqlalchemy**: ORM for database operations
- **alembic**: Database migrations
- **python-dotenv**: Environment configuration
- **uvicorn**: ASGI server
- **pytest**: Testing framework
- **httpx**: Async HTTP client
- **websockets**: WebSocket client
- **cryptography**: For secure API key storage

### DEX-Specific SDKs
- **Hyperliquid**: hyperliquid-python-sdk
- **Lighter**: lighter-python
- **Extended**: x10xchange python_sdk
- **EdgeX**: Custom REST implementation
- **Vest**: Custom REST implementation
- **Pacifica**: pacifica-python-sdk

## Architecture Overview

### Dual-Interface Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    External Clients                      │
├──────────────────┬───────────────────────────────────────┤
│ Trading Terminal │         Command Line Users            │
│       UI         │          & Automation Scripts         │
└──────────────────┴───────────────────────────────────────┘
         ↕                            ↕
┌─────────────────────────────────────────────────────────┐
│                   User Interfaces                        │
├──────────────────────────┬───────────────────────────────┤
│     FastAPI REST API     │      CLI Application          │
│   WebSocket Endpoints    │    (Interactive & Batch)      │
└──────────────────────────┴───────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                 Shared Service Layer                     │
│  (Order Management, Position Tracking, Account Mgmt)     │
│         (Risk Management, Market Data Aggregation)       │
└─────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│                  Connector Layer                         │
│     (Unified interface for all DEX integrations)         │
└─────────────────────────────────────────────────────────┘
                            ↕
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│Hyperliquid│ Lighter │ Extended │  EdgeX   │   Vest   │ Pacifica │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
                            ↕
┌─────────────────────────────────────────────────────────┐
│              Database & Cache (PostgreSQL/Redis)         │
└─────────────────────────────────────────────────────────┘
```

## Detailed Project Structure

```
perp-dex-backend/
├── cli/
│   ├── __init__.py
│   ├── main.py                    # CLI application entry point
│   ├── config.py                  # CLI configuration management
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── account.py            # Account management commands
│   │   ├── trade.py              # Trading commands
│   │   ├── position.py           # Position management commands
│   │   ├── market.py             # Market data commands
│   │   ├── monitor.py            # Real-time monitoring commands
│   │   └── config_cmd.py         # Configuration commands
│   └── interactive/
│       ├── __init__.py
│       └── shell.py              # Interactive shell mode
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Configuration management
│   ├── dependencies.py            # Dependency injection
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py               # Authentication middleware
│   │   ├── logging.py            # Request/response logging
│   │   └── rate_limiting.py     # Rate limiting middleware
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── trading.py   # Order placement/cancellation
│   │   │   │   ├── positions.py # Position management
│   │   │   │   ├── accounts.py  # Account management
│   │   │   │   ├── markets.py   # Market data endpoints
│   │   │   │   └── websocket.py # WebSocket connections
│   │   │   └── schemas/
│   │   │       ├── __init__.py
│   │   │       ├── trading.py   # Trading-related models
│   │   │       ├── positions.py # Position models
│   │   │       ├── accounts.py  # Account models
│   │   │       └── markets.py   # Market data models
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── responses.py     # Standardized responses
│   │       └── validators.py    # Request validators
│   └── core/
│       ├── __init__.py
│       ├── exceptions.py        # Custom exceptions
│       ├── security.py          # Security utilities
│       └── logging.py           # Logging configuration
├── connectors/
│   ├── __init__.py
│   ├── base.py                  # Abstract base connector
│   ├── factory.py               # Connector factory
│   ├── hyperliquid/
│   │   ├── __init__.py
│   │   ├── connector.py        # Hyperliquid implementation
│   │   ├── client.py           # API client wrapper
│   │   └── models.py           # Hyperliquid-specific models
│   ├── lighter/
│   │   ├── __init__.py
│   │   ├── connector.py
│   │   ├── client.py
│   │   └── models.py
│   ├── extended/
│   │   ├── __init__.py
│   │   ├── connector.py
│   │   ├── client.py
│   │   └── models.py
│   ├── edgex/
│   │   ├── __init__.py
│   │   ├── connector.py
│   │   ├── client.py
│   │   └── models.py
│   ├── vest/
│   │   ├── __init__.py
│   │   ├── connector.py
│   │   ├── client.py
│   │   └── models.py
│   └── pacifica/
│       ├── __init__.py
│       ├── connector.py
│       ├── client.py
│       └── models.py
├── models/
│   ├── __init__.py
│   ├── base.py                 # Base SQLAlchemy models
│   ├── accounts.py             # Account database models
│   ├── orders.py               # Order database models
│   ├── positions.py            # Position database models
│   └── audit.py                # Audit/logging models
├── services/
│   ├── __init__.py
│   ├── account_manager.py      # Account management service
│   ├── order_executor.py       # Order execution service
│   ├── position_tracker.py     # Position tracking service
│   ├── market_data.py         # Market data aggregation
│   ├── risk_manager.py        # Risk management service
│   └── notification.py        # Event notification service
├── database/
│   ├── __init__.py
│   ├── session.py              # Database session management
│   └── migrations/             # Alembic migrations
│       └── alembic.ini
├── utils/
│   ├── __init__.py
│   ├── crypto.py               # Encryption utilities
│   ├── decorators.py           # Utility decorators
│   └── helpers.py              # General helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest configuration
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
│   ├── setup.py                # Initial setup script
│   └── migrate.py              # Database migration script
├── docs/
│   ├── api/                    # API documentation
│   └── connectors/             # Connector-specific docs
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── Makefile
```

## Core Components Design

### 1. Base Connector Interface

```python
class BaseConnector(ABC):
    """Abstract base class for all DEX connectors"""
    
    @abstractmethod
    async def authenticate(self, credentials: Dict) -> bool:
        """Authenticate with the DEX"""
        
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a new order"""
        
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        
    @abstractmethod
    async def modify_order(self, order_id: str, modifications: Dict) -> OrderResponse:
        """Modify an existing order"""
        
    @abstractmethod
    async def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """Get orders with optional status filter"""
        
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """Get account information including balances"""
        
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get market data for a symbol"""
        
    @abstractmethod
    async def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book for a symbol"""
        
    @abstractmethod
    async def subscribe_to_updates(self, channels: List[str]) -> AsyncIterator[Dict]:
        """Subscribe to real-time updates"""
```

### 2. Account Management

- **Multi-Account Architecture**: Each user can have multiple accounts per DEX
- **Account Isolation**: Complete isolation between accounts
- **Credential Security**: Encrypted storage of API keys
- **Session Management**: Maintain active sessions per account
- **Load Balancing**: Distribute orders across accounts if needed

### 3. Order Management

- **Unified Order Format**: Standardized order structure across all DEXes
- **Order Routing**: Smart routing to appropriate DEX/account
- **Order Tracking**: Comprehensive order lifecycle tracking
- **Retry Logic**: Automatic retry with exponential backoff
- **Order History**: Complete audit trail of all orders

### 4. Position Tracking

- **Real-time Updates**: WebSocket-based position updates
- **P&L Calculation**: Real-time P&L across all positions
- **Risk Metrics**: Calculate exposure, margin usage, etc.
- **Position Aggregation**: Aggregate positions across accounts/DEXes

### 5. Market Data Service

- **Data Normalization**: Normalize data formats across DEXes
- **Caching Strategy**: Redis caching for frequently accessed data
- **Rate Limit Management**: Respect each DEX's rate limits
- **Failover Logic**: Automatic failover to backup data sources

## API Design

### RESTful Endpoints

#### Trading Endpoints
- `POST /api/v1/orders` - Place new order
- `DELETE /api/v1/orders/{order_id}` - Cancel order
- `PATCH /api/v1/orders/{order_id}` - Modify order
- `GET /api/v1/orders` - List orders
- `GET /api/v1/orders/{order_id}` - Get specific order

#### Position Endpoints
- `GET /api/v1/positions` - Get all positions
- `GET /api/v1/positions/{symbol}` - Get position for symbol
- `POST /api/v1/positions/{position_id}/close` - Close position

#### Account Endpoints
- `GET /api/v1/accounts` - List all accounts
- `POST /api/v1/accounts` - Add new account
- `GET /api/v1/accounts/{account_id}` - Get account details
- `DELETE /api/v1/accounts/{account_id}` - Remove account
- `GET /api/v1/accounts/{account_id}/balance` - Get account balance

#### Market Data Endpoints
- `GET /api/v1/markets` - List available markets
- `GET /api/v1/markets/{symbol}` - Get market details
- `GET /api/v1/markets/{symbol}/orderbook` - Get order book
- `GET /api/v1/markets/{symbol}/trades` - Get recent trades
- `GET /api/v1/markets/{symbol}/funding` - Get funding rate

### WebSocket Channels

- `/ws/v1/orders` - Real-time order updates
- `/ws/v1/positions` - Real-time position updates
- `/ws/v1/markets` - Real-time market data
- `/ws/v1/account` - Account balance updates

## CLI Design

### Command Structure

The CLI provides a powerful interface for traders and automation scripts with both interactive and batch modes.

#### Main Commands
- `perp-dex` - Main CLI entry point
- `perp-dex interactive` - Launch interactive shell with auto-completion
- `perp-dex --help` - Display comprehensive help

#### Account Management Commands
- `perp-dex account list` - List all configured accounts
- `perp-dex account add --dex <dex_name>` - Add new account
- `perp-dex account remove <account_id>` - Remove account
- `perp-dex account info <account_id>` - Display account details
- `perp-dex account balance <account_id>` - Get account balance
- `perp-dex account switch <account_id>` - Set default account

#### Trading Commands
- `perp-dex trade buy <symbol> <amount> --price <price>` - Place buy order
- `perp-dex trade sell <symbol> <amount> --price <price>` - Place sell order
- `perp-dex trade cancel <order_id>` - Cancel order
- `perp-dex trade modify <order_id> --price <new_price>` - Modify order
- `perp-dex trade orders [--status <status>]` - List orders
- `perp-dex trade history [--days <n>]` - Trading history

#### Position Management Commands
- `perp-dex position list [--dex <dex_name>]` - List all positions
- `perp-dex position info <symbol>` - Detailed position info
- `perp-dex position close <position_id> [--percent <n>]` - Close position
- `perp-dex position pnl [--unrealized]` - Show P&L
- `perp-dex position risk` - Display risk metrics

#### Market Data Commands
- `perp-dex market list` - List available markets
- `perp-dex market info <symbol>` - Market details
- `perp-dex market orderbook <symbol> [--depth <n>]` - Order book
- `perp-dex market trades <symbol> [--limit <n>]` - Recent trades
- `perp-dex market funding <symbol>` - Funding rates
- `perp-dex market watch <symbols...>` - Real-time price monitoring

#### Monitoring Commands
- `perp-dex monitor orders` - Real-time order monitoring
- `perp-dex monitor positions` - Real-time position monitoring
- `perp-dex monitor account` - Real-time account monitoring
- `perp-dex monitor market <symbol>` - Real-time market monitoring

#### Configuration Commands
- `perp-dex config show` - Display current configuration
- `perp-dex config set <key> <value>` - Set configuration value
- `perp-dex config api-key <dex> --add` - Add API key securely
- `perp-dex config export [--file <path>]` - Export configuration
- `perp-dex config import <file>` - Import configuration

### Interactive Shell Features

#### Auto-completion
- Command completion
- Symbol completion from available markets
- Account ID completion
- Order ID completion from recent orders

#### Command History
- Persistent command history
- Search through history (Ctrl+R)
- History export capability

#### Real-time Updates
- Live position updates in status bar
- P&L tracking display
- Alert notifications for order fills

#### Shortcuts
- Quick buy/sell aliases
- Favorite symbol shortcuts
- Custom command macros

### CLI Configuration

#### Configuration File (~/.perp-dex/config.yaml)
```yaml
default_account: "hyperliquid_main"
default_dex: "hyperliquid"
display:
  colors: true
  table_style: "rounded"
  decimal_places: 2
  show_timestamps: true
shortcuts:
  b: "trade buy"
  s: "trade sell"
  p: "position list"
  o: "trade orders"
alerts:
  order_filled: true
  position_liquidation: true
  price_alerts: []
```

#### Secure Credential Storage
- API keys stored in system keyring
- Encryption for sensitive data
- Support for hardware security modules
- Session-based authentication caching

### Automation Support

#### Batch Mode
- Execute commands from scripts
- JSON output format for parsing
- Exit codes for automation
- Quiet mode for cron jobs

#### Script Examples
```bash
# Place order and wait for fill
perp-dex trade buy BTC-PERP 0.1 --price 45000 --wait-fill

# Monitor position and close at target
perp-dex position watch BTC-PERP --close-at-profit 10%

# Export daily trading report
perp-dex trade history --format csv > report.csv
```

#### Integration Features
- Webhook support for events
- Export to common formats (CSV, JSON, XLSX)
- Integration with trading bots
- API for programmatic access

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
1. Set up project structure and dependencies
2. Implement base connector interface
3. Create database models and migrations
4. Set up configuration management
5. Implement basic logging and error handling

### Phase 2: Core Services (Week 2-3)
1. Implement account management service
2. Build order execution service
3. Create position tracking service
4. Implement authentication and security
5. Set up Redis for caching/queuing

### Phase 3: First DEX Integration (Week 3-4)
1. Implement Hyperliquid connector
2. Test all standard operations
3. Add WebSocket support
4. Create integration tests
5. Document connector implementation

### Phase 4: Additional DEX Integrations (Week 4-6)
1. Implement Lighter connector
2. Implement Extended connector
3. Implement EdgeX connector
4. Implement Vest connector
5. Implement Pacifica connector
6. Ensure feature parity across connectors

### Phase 5: API & CLI Layer (Week 6-7)
1. Implement all REST endpoints
2. Add WebSocket endpoints
3. Implement CLI command structure
4. Add interactive shell mode
5. Implement rate limiting
6. Add request validation
7. Generate API and CLI documentation

### Phase 6: Advanced Features (Week 7-8)
1. Implement risk management service
2. Add notification system
3. Create admin dashboard endpoints
4. Implement order routing logic
5. Add performance monitoring

### Phase 7: Testing & Documentation (Week 8-9)
1. Write comprehensive unit tests
2. Create integration tests
3. Perform load testing
4. Write user documentation
5. Create deployment guides

### Phase 8: Production Readiness (Week 9-10)
1. Docker containerization
2. CI/CD pipeline setup
3. Production configuration
4. Security audit
5. Performance optimization

## Security Considerations

### API Security
- JWT-based authentication
- API key management with rotation
- Rate limiting per user/IP
- Request signing for sensitive operations
- SSL/TLS encryption for all communications

### Data Security
- Encrypted storage of credentials
- Secure key management (HashiCorp Vault)
- Audit logging for all operations
- Data anonymization in logs
- Regular security audits

### Operational Security
- Environment-based configuration
- Secrets management
- Container security scanning
- Dependency vulnerability scanning
- Access control and permissions

## Performance Requirements

### Latency Targets
- Order placement: < 100ms
- Order cancellation: < 100ms
- Position updates: < 50ms
- Market data updates: < 20ms

### Throughput Targets
- 1000 orders/second per connector
- 10,000 concurrent WebSocket connections
- 100,000 market data updates/second

### Reliability Targets
- 99.9% uptime
- Automatic failover
- Graceful degradation
- Circuit breaker pattern

## Monitoring & Observability

### Metrics
- Order execution latency
- API response times
- WebSocket message latency
- Error rates by endpoint
- DEX connector health

### Logging
- Structured logging (JSON format)
- Log aggregation (ELK stack)
- Distributed tracing
- Error tracking (Sentry)

### Alerting
- Critical error alerts
- Performance degradation alerts
- Security incident alerts
- Business metric alerts

## Testing Strategy

### Unit Testing
- 90% code coverage target
- Mock external dependencies
- Test all edge cases
- Parameterized tests for connectors
- CLI command parsing tests
- Interactive shell behavior tests

### Integration Testing
- Test DEX connector integrations (all 6 DEXes)
- Database integration tests
- Redis integration tests
- End-to-end API tests

### Performance Testing
- Load testing with k6/Locust
- Stress testing
- Spike testing
- Endurance testing

## Deployment Strategy

### Development Environment
- Docker Compose setup
- Local PostgreSQL and Redis
- Mock DEX endpoints for testing

### Staging Environment
- Kubernetes deployment
- Testnet connections for DEXes
- Full monitoring stack
- Automated testing

### Production Environment
- Multi-region deployment
- Auto-scaling configuration
- Database replication
- Disaster recovery plan

## Risk Mitigation

### Technical Risks
- **DEX API Changes**: Version pinning, change detection
- **Rate Limiting**: Intelligent request queuing
- **Network Issues**: Retry logic, circuit breakers
- **Data Inconsistency**: Transaction management, reconciliation

### Operational Risks
- **Key Compromise**: Regular rotation, HSM usage
- **Service Outages**: Multi-region failover
- **Data Loss**: Regular backups, replication
- **Performance Degradation**: Auto-scaling, caching

## Success Metrics

### Technical Metrics
- API uptime > 99.9%
- Average latency < 100ms
- Zero data inconsistencies
- < 0.01% error rate

### Business Metrics
- Number of supported DEXes (target: 6 initially)
- Total trading volume processed
- Number of active accounts
- CLI adoption rate
- User satisfaction score

## Maintenance & Support

### Regular Maintenance
- Weekly dependency updates
- Monthly security patches
- Quarterly performance reviews
- Annual architecture reviews

### Support Structure
- 24/7 monitoring
- On-call rotation
- Incident response procedures
- Documentation maintenance

## Future Enhancements

### Short-term (3-6 months)
- Additional DEX integrations beyond initial 6
- Advanced order types
- Trading algorithms/bots
- Mobile API support

### Long-term (6-12 months)
- Cross-DEX arbitrage
- ML-based trading signals
- Decentralized order routing
- Layer 2 integrations

## Conclusion

This project plan provides a comprehensive roadmap for building a production-ready perpetual DEX trading backend. The modular architecture ensures easy extensibility, while the standardized API provides a consistent interface for the trading terminal. With proper implementation of the phases outlined above, the system will be capable of handling high-frequency trading across multiple DEX platforms with enterprise-grade reliability and performance.