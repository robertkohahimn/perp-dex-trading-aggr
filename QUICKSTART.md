# 🚀 Quick Start Guide

## Running the Server

### Method 1: Using the startup script (Recommended)
```bash
./run_server.sh
```

### Method 2: Manual startup
```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Set environment variables
unset DATABASE_URL
export ENCRYPTION_KEY="your-32-byte-encryption-key-here"

# 3. Run the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Method 3: Using make
```bash
source venv/bin/activate
make dev
```

## Access Points

Once running, you can access:

- **API**: http://localhost:8000
- **Interactive API Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Database Info

- **Database**: perp_dex_db
- **User**: perp_user
- **Password**: perp_password123
- **Host**: localhost
- **Port**: 5432

## Testing the API

Test if the server is running:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
    "status": "healthy",
    "timestamp": 1234567890.123
}
```

## Troubleshooting

### If you get "No module named uvicorn"
Make sure your virtual environment is activated:
```bash
source venv/bin/activate
```

### If you get database connection errors
1. Check PostgreSQL is running:
```bash
pg_ctl status
```

2. Verify database exists:
```bash
psql -U perp_user -d perp_dex_db -c "\dt"
```

### If you get environment variable errors
Make sure to unset any conflicting DATABASE_URL:
```bash
unset DATABASE_URL
```

## Using the CLI

The backend includes a powerful command-line interface for trading operations.

### Basic CLI Usage
```bash
# Make CLI executable
chmod +x perp-dex

# Show help
./perp-dex --help

# Show version
./perp-dex version
```

### Account Management
```bash
# List accounts
./perp-dex account list

# Add a new account (interactive)
./perp-dex account add --dex mock --name test-account

# Check balance
./perp-dex account balance --dex mock --account test-account
```

### Trading Commands
```bash
# Place limit order
./perp-dex trade place BTC-PERP buy 0.1 --price 50000 --dex mock --account test-account

# Place market order
./perp-dex trade market ETH-PERP sell 1.0 --dex mock --account test-account

# List orders
./perp-dex trade list --dex mock

# Cancel order
./perp-dex trade cancel <order-id> --dex mock
```

### Position Management
```bash
# List positions
./perp-dex position list --dex mock

# List all positions across all accounts
./perp-dex position list --all
```

### Interactive Shell
```bash
# Start interactive trading shell
./perp-dex shell

# In shell:
> use mock test-account
> buy 0.1 BTC-PERP @ 50000
> positions
> balance
> exit
```

### Configuration
```bash
# Show configuration
./perp-dex config show

# Set default DEX
./perp-dex config set default_dex mock

# Validate configuration
./perp-dex config validate
```

## Next Steps

1. Check API documentation at http://localhost:8000/docs
2. Try the CLI with mock connector: `./perp-dex test mock`
3. Start implementing real DEX connectors in `connectors/` directory
4. Add API routes in `app/api/v1/routes/`
5. Implement services in `services/` directory

## Development Tips

- The server auto-reloads when you change code (in `--reload` mode)
- Logs are structured and color-coded in development mode
- All database tables are created automatically on startup
- Request IDs are added to all requests for tracking