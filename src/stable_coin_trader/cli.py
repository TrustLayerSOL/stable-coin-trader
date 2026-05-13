from pathlib import Path

from rich.console import Console
import typer

from stable_coin_trader.config import load_config
from stable_coin_trader.engine import run_once

app = typer.Typer(
    help="Risk-aware stablecoin paper trading bot.",
    invoke_without_command=True,
)
console = Console()


@app.callback(no_args_is_help=False)
def main(ctx: typer.Context) -> None:
    """Stable Coin Trader command line interface."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("run-once")
def run_once_command(
    config: Path = typer.Option(..., "--config", help="Path to paper config JSON."),
) -> None:
    bot_config = load_config(config)
    result = run_once(bot_config)
    console.print(
        "paper run complete "
        f"opportunities={result.opportunities_seen} "
        f"approved={result.approved_trades} "
        f"rejected={result.rejected_trades} "
        f"fills={result.paper_fills}"
    )
