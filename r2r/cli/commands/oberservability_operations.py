import json
import uuid
from typing import Any, Dict

import click

from r2r.cli.command_group import cli
from r2r.cli.utils.param_types import JSON
from r2r.cli.utils.timer import timer


@cli.command()
@click.option("--filters", type=JSON, help="Filters for analytics as JSON")
@click.option("--analysis-types", type=JSON, help="Analysis types as JSON")
@click.pass_obj
def analytics(obj, filters: Dict[str, Any], analysis_types: Dict[str, Any]):
    """Retrieve analytics data."""
    with timer():
        response = obj.analytics(filters, analysis_types)

    click.echo(response)


@cli.command()
@click.pass_obj
def app_settings(obj):
    """Retrieve application settings."""
    with timer():
        response = obj.app_settings()

    click.echo(response)


@cli.command()
@click.option("--log-type-filter", help="Filter for log types")
@click.option(
    "--max-runs", default=100, help="Maximum number of runs to fetch"
)
@click.pass_obj
def logs(obj, log_type_filter, max_runs):
    """Retrieve logs with optional type filter."""
    with timer():
        response = obj.logs(log_type_filter, max_runs)

    for log in response:
        click.echo(f"Run ID: {log['run_id']}")
        click.echo(f"Run Type: {log['run_type']}")
        if "timestamp" in log:
            click.echo(f"Timestamp: {log['timestamp']}")
        else:
            click.echo("Timestamp: Not available")
        if "user_id" in log:
            click.echo(f"User ID: {log['user_id']}")
        else:
            click.echo("User ID: Not available")
        click.echo("Entries:")
        for entry in log["entries"]:
            if entry["key"] == "completion_record":
                completion_record = json.loads(entry["value"])
                click.echo("  CompletionRecord:")
                click.echo(
                    f"    Message ID: {completion_record['message_id']}"
                )
                click.echo(
                    f"    Message Type: {completion_record['message_type']}"
                )
                click.echo(
                    f"    Search Query: {completion_record['search_query']}"
                )
                click.echo(
                    f"    Completion Start Time: {completion_record['completion_start_time']}"
                )
                click.echo(
                    f"    Completion End Time: {completion_record['completion_end_time']}"
                )
                click.echo(
                    f"    LLM Response: {completion_record['llm_response']}"
                )
            else:
                click.echo(f"  - {entry['key']}: {entry['value'][:100]}")
        click.echo("---")

    click.echo(f"Total runs: {len(response)}")


@cli.command()
@click.option("--user-ids", multiple=True, help="User IDs to overview")
@click.pass_obj
def users_overview(obj, user_ids):
    """Get an overview of users."""
    user_ids = (
        [uuid.UUID(user_id) for user_id in user_ids] if user_ids else None
    )

    with timer():
        response = obj.users_overview(user_ids)

    for user in response:
        click.echo(user)
