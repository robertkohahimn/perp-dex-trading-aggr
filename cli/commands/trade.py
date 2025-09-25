"""
Trading CLI commands.
"""
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.config import load_config, get_account_credentials
from services.order_executor import OrderExecutor
from connectors.factory import ConnectorFactory
from connectors.base import OrderRequest, OrderType as BaseOrderType, OrderSide as BaseOrderSide

app = typer.Typer(help="Trading commands")
console = Console()


@app.command("place")
def place_order(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., BTC-PERP)"),
    side: str = typer.Argument(..., help="Order side (buy/sell)"),
    size: float = typer.Argument(..., help="Order size"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Limit price (market order if not specified)"),
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
    leverage: Optional[int] = typer.Option(None, "--leverage", "-l", help="Leverage to use"),
    reduce_only: bool = typer.Option(False, "--reduce-only", help="Reduce only order"),
    post_only: bool = typer.Option(False, "--post-only", help="Post only order"),
    ioc: bool = typer.Option(False, "--ioc", help="Immediate or cancel"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip confirmation"),
):
    """Place a new order."""
    config = load_config()
    
    # Determine DEX and account
    dex = dex or config.default_dex
    account = account or config.default_account
    
    if not dex or not account:
        console.print("[red]Please specify --dex and --account or set defaults in config[/red]")
        return
    
    # Parse side
    side = side.lower()
    if side not in ["buy", "sell"]:
        console.print(f"[red]Invalid side: {side}. Must be 'buy' or 'sell'[/red]")
        return
    
    # Determine order type
    order_type = "market" if price is None else "limit"
    
    # Confirmation
    if not no_confirm and config.trading.confirm_orders:
        console.print(f"\n[cyan]Order Summary:[/cyan]")
        console.print(f"  Symbol: {symbol}")
        console.print(f"  Side: {side}")
        console.print(f"  Size: {size}")
        console.print(f"  Type: {order_type}")
        if price:
            console.print(f"  Price: {price}")
        if leverage:
            console.print(f"  Leverage: {leverage}x")
        console.print(f"  DEX: {dex}")
        console.print(f"  Account: {account}")
        
        if not Confirm.ask("\nPlace this order?", default=True):
            console.print("[yellow]Order cancelled[/yellow]")
            return
    
    async def place():
        try:
            # Check for dry run mode
            ctx = typer.Context.get_current()
            if ctx and ctx.obj and ctx.obj.get("dry_run"):
                console.print("[yellow]DRY RUN: Order would be placed but not executed[/yellow]")
                return
            
            # Get credentials
            credentials = get_account_credentials(dex, account)
            
            # Create connector
            connector = await ConnectorFactory.create(dex, credentials)
            
            # Authenticate
            if not await connector.authenticate(credentials):
                console.print("[red]Authentication failed[/red]")
                return
            
            # Create order request
            order_request = OrderRequest(
                symbol=symbol,
                side=BaseOrderSide.BUY if side == "buy" else BaseOrderSide.SELL,
                order_type=BaseOrderType.MARKET if order_type == "market" else BaseOrderType.LIMIT,
                size=size,
                price=price,
                leverage=leverage,
                reduce_only=reduce_only,
                post_only=post_only,
                time_in_force="IOC" if ioc else None,
            )
            
            # Place order
            with console.status(f"Placing {side} order..."):
                response = await connector.place_order(order_request)
            
            if response.success:
                console.print(f"[green]✓ Order placed successfully[/green]")
                console.print(f"Order ID: {response.order_id}")
                if response.filled_size:
                    console.print(f"Filled: {response.filled_size} @ {response.average_price}")
            else:
                console.print(f"[red]✗ Order failed: {response.message}[/red]")
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
    
    asyncio.run(place())


@app.command("market")
def place_market_order(
    symbol: str = typer.Argument(..., help="Trading symbol"),
    side: str = typer.Argument(..., help="Order side (buy/sell)"),
    size: float = typer.Argument(..., help="Order size"),
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip confirmation"),
):
    """Place a market order."""
    place_order(
        symbol=symbol,
        side=side,
        size=size,
        price=None,  # Market order
        dex=dex,
        account=account,
        no_confirm=no_confirm,
    )


@app.command("cancel")
def cancel_order(
    order_id: str = typer.Argument(..., help="Order ID to cancel"),
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
):
    """Cancel an order."""
    config = load_config()
    
    dex = dex or config.default_dex
    account = account or config.default_account
    
    if not dex or not account:
        console.print("[red]Please specify --dex and --account or set defaults in config[/red]")
        return
    
    async def cancel():
        try:
            # Get credentials
            credentials = get_account_credentials(dex, account)
            
            # Create connector
            connector = await ConnectorFactory.create(dex, credentials)
            
            # Authenticate
            if not await connector.authenticate(credentials):
                console.print("[red]Authentication failed[/red]")
                return
            
            # Cancel order
            with console.status(f"Cancelling order {order_id}..."):
                success = await connector.cancel_order(order_id)
            
            if success:
                console.print(f"[green]✓ Order {order_id} cancelled[/green]")
            else:
                console.print(f"[red]✗ Failed to cancel order {order_id}[/red]")
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
    
    asyncio.run(cancel())


@app.command("cancel-all")
def cancel_all_orders(
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Cancel orders for specific symbol only"),
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Cancel all open orders."""
    config = load_config()
    
    dex = dex or config.default_dex
    account = account or config.default_account
    
    if not dex or not account:
        console.print("[red]Please specify --dex and --account or set defaults in config[/red]")
        return
    
    if not force:
        msg = f"Cancel all orders"
        if symbol:
            msg += f" for {symbol}"
        msg += f" on {dex}?"
        
        if not Confirm.ask(msg, default=False):
            console.print("[yellow]Cancelled[/yellow]")
            return
    
    async def cancel_all():
        try:
            # Get credentials
            credentials = get_account_credentials(dex, account)
            
            # Create connector
            connector = await ConnectorFactory.create(dex, credentials)
            
            # Authenticate
            if not await connector.authenticate(credentials):
                console.print("[red]Authentication failed[/red]")
                return
            
            # Get open orders
            with console.status("Fetching open orders..."):
                orders = await connector.get_orders(status="open")
            
            if symbol:
                orders = [o for o in orders if o.symbol == symbol]
            
            if not orders:
                console.print("[yellow]No open orders to cancel[/yellow]")
                return
            
            console.print(f"[cyan]Cancelling {len(orders)} orders...[/cyan]")
            
            # Cancel each order
            cancelled = 0
            failed = 0
            
            for order in orders:
                try:
                    success = await connector.cancel_order(order.order_id)
                    if success:
                        cancelled += 1
                        console.print(f"  [green]✓[/green] Cancelled {order.order_id}")
                    else:
                        failed += 1
                        console.print(f"  [red]✗[/red] Failed {order.order_id}")
                except Exception as e:
                    failed += 1
                    console.print(f"  [red]✗[/red] Error cancelling {order.order_id}: {str(e)}")
            
            console.print(f"\n[cyan]Results:[/cyan]")
            console.print(f"  Cancelled: [green]{cancelled}[/green]")
            if failed:
                console.print(f"  Failed: [red]{failed}[/red]")
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
    
    asyncio.run(cancel_all())


@app.command("list")
def list_orders(
    status: Optional[str] = typer.Option("open", "--status", "-s", help="Order status (open/closed/all)"),
    symbol: Optional[str] = typer.Option(None, "--symbol", help="Filter by symbol"),
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of orders to show"),
):
    """List orders."""
    config = load_config()
    
    dex = dex or config.default_dex
    account = account or config.default_account
    
    if not dex or not account:
        console.print("[red]Please specify --dex and --account or set defaults in config[/red]")
        return
    
    async def list_all():
        try:
            # Get credentials
            credentials = get_account_credentials(dex, account)
            
            # Create connector
            connector = await ConnectorFactory.create(dex, credentials)
            
            # Authenticate
            if not await connector.authenticate(credentials):
                console.print("[red]Authentication failed[/red]")
                return
            
            # Get orders
            with console.status("Fetching orders..."):
                if status == "all":
                    orders = await connector.get_orders()
                else:
                    orders = await connector.get_orders(status=status)
            
            if symbol:
                orders = [o for o in orders if o.symbol == symbol]
            
            # Limit results
            orders = orders[:limit]
            
            if not orders:
                console.print(f"[yellow]No {status} orders found[/yellow]")
                return
            
            # Display orders
            table = Table(title=f"{status.title()} Orders")
            table.add_column("Order ID", style="cyan")
            table.add_column("Symbol", style="yellow")
            table.add_column("Side", style="green")
            table.add_column("Type")
            table.add_column("Size")
            table.add_column("Price")
            table.add_column("Filled")
            table.add_column("Status")
            table.add_column("Time", style="dim")
            
            for order in orders:
                side_style = "green" if order.side == BaseOrderSide.BUY else "red"
                status_style = "green" if order.status == "filled" else "yellow" if order.status == "open" else "dim"
                
                table.add_row(
                    order.order_id[:8] + "...",
                    order.symbol,
                    f"[{side_style}]{order.side.value}[/{side_style}]",
                    order.order_type.value,
                    f"{order.size:.4f}",
                    f"{order.price:.2f}" if order.price else "Market",
                    f"{order.filled_size:.4f}" if order.filled_size else "0",
                    f"[{status_style}]{order.status}[/{status_style}]",
                    order.timestamp.strftime("%H:%M:%S") if order.timestamp else "",
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
    
    asyncio.run(list_all())


@app.command("history")
def order_history(
    days: int = typer.Option(7, "--days", "-d", help="Number of days of history"),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Filter by symbol"),
    dex: Optional[str] = typer.Option(None, "--dex", help="DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export to CSV file"),
):
    """Show order history."""
    config = load_config()
    
    dex = dex or config.default_dex
    account = account or config.default_account
    
    if not dex or not account:
        console.print("[red]Please specify --dex and --account or set defaults in config[/red]")
        return
    
    # For now, just use list_orders with status="all"
    # In a full implementation, this would fetch historical data
    list_orders(status="all", symbol=symbol, dex=dex, account=account, limit=100)