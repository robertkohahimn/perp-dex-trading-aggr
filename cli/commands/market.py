"""
Market data CLI commands.
"""
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.config import load_config, get_account_credentials
from connectors.factory import ConnectorFactory

app = typer.Typer(help="Market data commands")
console = Console()


@app.command("summary")
def market_summary(
    dex: str = typer.Argument(..., help="DEX to query"),
):
    """Show market summary."""
    console.print(f"[cyan]Market summary for {dex}[/cyan]")
    console.print("[yellow]Market data commands coming soon...[/yellow]")


@app.command("book")
def order_book(
    symbol: str = typer.Argument(..., help="Trading symbol"),
    dex: str = typer.Option(..., "--dex", "-d", help="DEX to query"),
    depth: int = typer.Option(20, "--depth", help="Order book depth"),
):
    """Show order book."""
    console.print(f"[cyan]Order book for {symbol} on {dex}[/cyan]")
    console.print("[yellow]Order book display coming soon...[/yellow]")