import typer

app = typer.Typer(help="Risk-aware stablecoin paper trading bot.")


@app.callback()
def main() -> None:
    """Stable Coin Trader command line interface."""
