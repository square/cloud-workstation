import click

from .crud import create, delete, list, list_configs, logs, ssh, start, stop, sync

try:
    from block.clitools.clock import group as base_group

    namespace = "mlds"
except ImportError:
    from click import group as base_group

    namespace = None


def group_wrapper(*args, **kwargs):  # noqa: D103
    if namespace:
        kwargs["namespace"] = namespace
    return base_group(*args, **kwargs)


@group_wrapper(name="workstation")
@click.version_option(package_name="cloud-workstation")
@click.pass_context
def cli(context: click.Context):
    """Create and manage Google Cloud Workstation."""


cli.add_command(create)
cli.add_command(list_configs)
cli.add_command(list)
cli.add_command(start)
cli.add_command(stop)
cli.add_command(delete)
cli.add_command(sync)
cli.add_command(logs)
cli.add_command(ssh)
