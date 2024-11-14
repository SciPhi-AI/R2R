import asyncclick as click
from asyncclick import pass_context

from r2r import R2RAsyncClient
from cli.command_group import cli, deprecated_command
from cli.utils.timer import timer


@cli.command()
@pass_context
@deprecated_command("r2r system status")
async def server_stats(ctx):
    client: R2RAsyncClient = ctx.obj
    """Check the server stats."""
    with timer():
        response = await client.server_stats()

    click.echo(response)


@cli.command()
@click.option(
    "--offset", default=None, help="Pagination offset. Default is None."
)
@click.option(
    "--limit", default=None, help="Pagination limit. Defaults to 100."
)
@click.option("--run-type-filter", help="Filter for log types")
@deprecated_command("r2r system logs")
@pass_context
async def logs(ctx, run_type_filter, offset, limit):
    """Retrieve logs with optional type filter."""
    client: R2RAsyncClient = ctx.obj
    with timer():
        response = await client.logs(
            offset=offset, limit=limit, run_type_filter=run_type_filter
        )

    for log in response["results"]:
        click.echo(f"Run ID: {log['run_id']}")
        click.echo(f"Run Type: {log['run_type']}")
        click.echo(f"Timestamp: {log['timestamp']}")
        click.echo(f"User ID: {log['user_id']}")
        click.echo("Entries:")
        for entry in log["entries"]:
            click.echo(f"  - {entry['key']}: {entry['value'][:100]}")
        click.echo("---")

    click.echo(f"Total runs: {len(response['results'])}")
