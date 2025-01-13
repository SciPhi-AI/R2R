import configparser
from pathlib import Path

import asyncclick as click
from rich.box import ROUNDED
from rich.console import Console
from rich.table import Table

console = Console()


def get_config_dir():
    """Create and return the config directory path."""
    config_dir = Path.home() / ".fuse"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_config_file():
    """Get the config file path."""
    return get_config_dir() / "config.ini"


class Config:
    _instance = None
    _config = configparser.ConfigParser()
    _config_file = get_config_file()

    @classmethod
    def load(cls):
        """Load the configuration file."""
        if cls._config_file.exists():
            cls._config.read(cls._config_file)

    @classmethod
    def save(cls):
        """Save the configuration to file."""
        with open(cls._config_file, "w") as f:
            cls._config.write(f)

    @classmethod
    def get_credentials(cls, service):
        """Get credentials for a specific service."""
        cls.load()  # Ensure we have latest config
        return dict(cls._config[service]) if service in cls._config else {}

    @classmethod
    def set_credentials(cls, service, credentials):
        """Set credentials for a specific service."""
        cls.load()  # Ensure we have latest config
        if service not in cls._config:
            cls._config[service] = {}
        cls._config[service].update(credentials)
        cls.save()


@click.group()
def configure():
    """Configuration management commands."""
    pass


@configure.command()
@click.confirmation_option(
    prompt="Are you sure you want to reset all settings?"
)
async def reset():
    """Reset all configuration to defaults."""
    if Config._config_file.exists():
        Config._config_file.unlink()  # Delete the config file
    Config._config = configparser.ConfigParser()  # Reset the config in memory

    # Set default values
    Config.set_credentials("Base URL", {"base_url": "http://localhost:7272"})

    console.print(
        "[green]Successfully reset configuration to defaults[/green]"
    )


@configure.command()
@click.option(
    "--api-key",
    prompt="SciPhi API Key",
    hide_input=True,
    help="API key for SciPhi cloud",
)
async def key(api_key):
    """Configure SciPhi cloud API credentials."""
    Config.set_credentials("SciPhi", {"api_key": api_key})
    console.print(
        "[green]Successfully configured SciPhi cloud credentials[/green]"
    )


@configure.command()
@click.option(
    "--base-url",
    prompt="FUSE Base URL",
    default="https://api.cloud.sciphi.ai",
    hide_input=False,
    help="Host URL for FUSE",
)
async def host(host):
    """Configure FUSE host URL."""
    Config.set_credentials("Host", {"FUSE_HOST": host})
    console.print("[green]Successfully configured FUSE host URL[/green]")


@configure.command()
async def view():
    """View current configuration."""
    Config.load()

    table = Table(
        title="[bold blue]FUSE Settings[/bold blue]",
        show_header=True,
        header_style="bold white on blue",
        border_style="blue",
        box=ROUNDED,
        pad_edge=False,
        collapse_padding=True,
    )

    table.add_column(
        "Section", justify="left", style="bright_yellow", no_wrap=True
    )
    table.add_column(
        "Key", justify="left", style="bright_magenta", no_wrap=True
    )
    table.add_column(
        "Value", justify="left", style="bright_green", no_wrap=True
    )

    # Group related configurations together
    config_groups = {
        "API Credentials": ["SciPhi"],
        "Server Settings": ["Base URL", "Port"],
    }

    for group_name, sections in config_groups.items():
        has_items = any(section in Config._config for section in sections)
        if has_items:
            table.add_row(
                f"[bold]{group_name}[/bold]", "", "", style="bright_blue"
            )

            for section in sections:
                if section in Config._config:
                    for key, value in Config._config[section].items():
                        # Mask API keys for security
                        displayed_value = (
                            f"****{value[-4:]}"
                            if "api_key" in key.lower()
                            else value
                        )
                        table.add_row(
                            f"  {section}", key.lower(), displayed_value
                        )

    console.print("\n")
    console.print(table)
    console.print("\n")
