"""
Configuration CLI commands.
"""
import typer
from rich.console import Console
from rich.syntax import Syntax
import yaml
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.config import load_config, save_config, get_config_file

app = typer.Typer(help="Configuration commands")
console = Console()


@app.command("show")
def show_config():
    """Show current configuration."""
    config = load_config()
    config_dict = config.model_dump()
    
    # Convert to YAML for display
    yaml_str = yaml.dump(config_dict, default_flow_style=False)
    syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
    
    console.print("\n[bold cyan]Current Configuration:[/bold cyan]")
    console.print(syntax)


@app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key (e.g., default_dex)"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a configuration value."""
    config = load_config()
    
    # Parse the key path
    keys = key.split(".")
    
    # Navigate to the correct location
    obj = config
    for k in keys[:-1]:
        if hasattr(obj, k):
            obj = getattr(obj, k)
        else:
            console.print(f"[red]Invalid configuration key: {key}[/red]")
            return
    
    # Set the value
    final_key = keys[-1]
    if hasattr(obj, final_key):
        # Convert value to appropriate type
        current_value = getattr(obj, final_key)
        if isinstance(current_value, bool):
            value = value.lower() in ["true", "yes", "1"]
        elif isinstance(current_value, int):
            value = int(value)
        elif isinstance(current_value, float):
            value = float(value)
        
        setattr(obj, final_key, value)
        save_config(config)
        console.print(f"[green]✓ Set {key} = {value}[/green]")
    else:
        console.print(f"[red]Invalid configuration key: {key}[/red]")


@app.command("validate")
def validate_config():
    """Validate configuration file."""
    try:
        config = load_config()
        console.print("[green]✓ Configuration is valid[/green]")
        
        # Check for configured accounts
        if not config.accounts:
            console.print("[yellow]⚠ No accounts configured[/yellow]")
        else:
            for dex, accounts in config.accounts.items():
                console.print(f"  {dex}: {len(accounts)} account(s)")
        
        # Check defaults
        if config.default_dex:
            console.print(f"  Default DEX: {config.default_dex}")
        if config.default_account:
            console.print(f"  Default account: {config.default_account}")
            
    except Exception as e:
        console.print(f"[red]✗ Configuration error: {str(e)}[/red]")


@app.command("path")
def show_config_path():
    """Show configuration file path."""
    config_file = get_config_file()
    console.print(f"Configuration file: [cyan]{config_file}[/cyan]")
    
    if config_file.exists():
        console.print("[green]✓ File exists[/green]")
    else:
        console.print("[yellow]⚠ File does not exist (will be created on first save)[/yellow]")