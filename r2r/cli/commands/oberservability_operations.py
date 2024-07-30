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
@click.pass_obj
def logs(obj, log_type_filter):
    """Retrieve logs with optional type filter."""
    with timer():
        response = obj.logs(log_type_filter)

    click.echo(response)


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
