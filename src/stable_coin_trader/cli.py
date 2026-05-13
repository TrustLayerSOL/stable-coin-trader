import typer

app = typer.Typer(
    help="Risk-aware stablecoin paper trading bot.",
    invoke_without_command=True,
)


@app.callback(no_args_is_help=False)
def main(ctx: typer.Context) -> None:
    """Stable Coin Trader command line interface."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
