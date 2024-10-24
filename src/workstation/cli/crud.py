"""
crud module provides command-line interface (CLI) commands for managing workstations.

Include functionalities to create, delete, list, start, and stop workstations,
as well as manage workstation configurations.

Functions
---------
get_gcloud_config(project: Optional[str], location: Optional[str]) -> tuple
    Retrieve GCP configuration details including project, location, and account.
common_options(func: callable) -> callable
    Apply common CLI options to commands.
create(context: click.Context, cluster: Optional[str], config: str, location: Optional[str], name: str, project: Optional[str], proxy: Optional[str], no_proxy: Optional[str], **kwargs)
    Create a workstation.
list_configs(context: click.Context, project: Optional[str], location: Optional[str], **kwargs)
    List workstation configurations.
list(context: click.Context, project: Optional[str], location: Optional[str], all: bool, user: str, export_json: bool, cluster: Optional[str], **kwargs)
    List workstations.
start(context: click.Context, name: str, code: bool, browser: bool, **kwargs)
    Start workstation and optionally open it either locally with VSCode or through VSCode in a browser.
stop(context: click.Context, name: str, **kwargs)
    Stop workstation.
delete(context: click.Context, name: str, **kwargs)
    Delete workstation.
sync(context: click.Context, name: str, **kwargs)
    Sync files to workstation.
logs(name: str, project: str, **kwargs)
    Open logs for the workstation.

"""

import getpass
import json
import sys
import webbrowser
from typing import Optional

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.traceback import install
from rich.tree import Tree

from workstation.config import ConfigManager
from workstation.core import (
    create_workstation,
    delete_workstation,
    list_workstation_configs,
    list_workstations,
    start_workstation,
    stop_workstation,
)
from workstation.utils import (
    check_gcloud_auth,
    config_tree,
    get_instance_assignment,
    read_gcloud_config,
    sync_files_workstation,
)

try:
    from block.clitools.clock import command
except ImportError:
    from click import command

config_manager = ConfigManager()
console = Console()
install()


def get_gcloud_config(project: Optional[str], location: Optional[str]):  # noqa: D103
    """
    Retrieve GCP configuration details including project, location, and account.

    Parameters
    ----------
    project : str, optional
        GCP project name.
    location : str, optional
        GCP location.

    Returns
    -------
    tuple
        A tuple containing project, location, and account details.
    """
    config_project, config_location, account = read_gcloud_config()

    if project is None:
        if config_project is not None:
            project = config_project
        else:
            raise ValueError(
                "Project not found in gcloud config and was not passed in."
            )

    if location is None:
        if config_location is not None:
            location = config_location
        else:
            raise ValueError(
                "Location not found in gcloud config and was not passed in."
            )

    if account is None:
        raise ValueError("Account not found in gcloud config.")

    return project, location, account


_common_options = [
    click.option(
        "--config",
        "-c",
        help="Name of workstation config",
        type=str,
        metavar="<str>",
    ),
    click.option(
        "--project",
        "-p",
        help="GCP Project name, if not provided will use the default project in gcloud config.",
        type=str,
        metavar="<str>",
    ),
    click.option(
        "--location",
        "-l",
        help="Workstation location, if not provided will use the default location in gcloud config.",
        default="us-central1",
        type=str,
        metavar="<str>",
    ),
    click.option(
        "--cluster",
        default="cluster-public",
        help="Cluster used for workstations.",  # NOQA
        type=str,
        metavar="<str>",
    ),
]


def common_options(func):  # noqa: D103
    """
    Apply common CLI options to commands.

    Parameters
    ----------
    func : callable
        The function to apply the options to.

    Returns
    -------
    callable
        The function with common options applied.
    """
    for option in reversed(_common_options):
        func = option(func)
    return func


@command()
@common_options
@click.option(
    "--name",
    help="Name of the workstation to create.",
    type=str,
    metavar="<str>",
)
@click.option(
    "--proxy",
    help="proxy setting.",
    type=str,
    metavar="<str>",
)
@click.option(
    "--no-proxy",
    help="No proxy setting.",
    type=str,
    metavar="<str>",
)
@click.pass_context
def create(
    context: click.Context,
    cluster: Optional[str],
    config: str,
    location: Optional[str],
    name: str,
    project: Optional[str],
    proxy: Optional[str],
    no_proxy: Optional[str],
    **kwargs,
):
    """Create a workstation."""
    # Make sure the user is authenticated
    check_gcloud_auth()

    project, location, account = get_gcloud_config(project=project, location=location)

    # Ensure USER is set on laptop
    user = getpass.getuser()

    try:
        from block.mlds.proxy.block import Proxy

        proxies = Proxy(project=project, name=name)
        proxy = proxies.proxy
        no_proxy = proxies.no_proxy
    except ImportError:
        pass

    if config_manager.check_if_config_exists(name):
        console.print(f"Workstation config for {name} already exists.")
        overwrite = Confirm.ask("Overwrite config?")
        if not overwrite:
            console.print(f"Exiting without creating workstation {name}.")
            sys.exit(0)

    _ = create_workstation(
        cluster=cluster,
        config=config,
        name=name,
        user=user,
        account=account,
        project=project,
        location=location,
        proxy=proxy,
        no_proxy=no_proxy,
    )

    config_manager.write_ssh_config(
        name=name,
        user=user,
        cluster=cluster,
        region=location,
        project=project,
        config=config,
    )

    console.print(f"Workstation {name} created.")


@command()
@common_options
@click.pass_context
def list_configs(
    context: click.Context,
    project: Optional[str],
    location: Optional[str],
    **kwargs,
):
    """List workstation configurations."""
    # Make sure the user is authenticated
    check_gcloud_auth()

    project, location, account = get_gcloud_config(project=project, location=location)
    configs = list_workstation_configs(
        cluster=kwargs["cluster"],
        project=project,
        location=location,
    )

    console.print(config_tree(configs))


@command()
@common_options
@click.option(
    "--json",
    "export_json",
    default=False,
    is_flag=True,
    help="print json output",
)
@click.option(
    "-u",
    "--user",
    default=getpass.getuser(),
    help="Lists workstations only from a given user.",
)
@click.option(
    "-a", "--all", is_flag=True, default=False, help="List workstations from all users."
)
@click.pass_context
def list(
    context: click.Context,
    project: Optional[str],
    location: Optional[str],
    all: bool,
    user: str,
    export_json: bool,
    cluster: Optional[str],
    **kwargs,
):
    """List workstations."""
    # Make sure the user is authenticated
    check_gcloud_auth()

    project, location, account = get_gcloud_config(project=project, location=location)

    workstations = list_workstations(
        cluster=cluster,
        project=project,
        location=location,
    )

    if not export_json:
        tree = Tree("Workstations", style="bold blue")

        for workstation in workstations:
            if not all and workstation.get("env", {}).get("LDAP") != user:
                continue

            if workstation["state"].name == "STATE_RUNNING":
                status = ":play_button: Running"
            elif workstation["state"].name == "STATE_STOPPED":
                status = ":stop_sign: Stopped"
            elif workstation["state"].name == "STATE_STARTING":
                status = ":hourglass: Starting"
            elif workstation["state"].name == "STATE_STOPPING":
                status = ":hourglass: Stopping"
            else:
                status = ":question: State unknown"

            config_branch = tree.add(
                f"Workstation: {workstation['name'].split('/')[-1]}"
            )
            config_branch.add(f"{status}", style="white")
            config_branch.add(f"User: {workstation['env']['LDAP']}", style="white")
            config_branch.add(f":minidisc: Image: {workstation['config']['image']}")
            config_branch.add(
                f":computer: Machine Type: {workstation['config']['machine_type']}"
            )
            config_branch.add(
                f":hourglass_flowing_sand: Idle Timeout (s): {str(workstation['config']['idle_timeout'])}"
            )
            config_branch.add(
                f":hourglass_flowing_sand: Max Runtime (s): {str(workstation['config']['max_runtime'])}"
            )

        console.print(tree)
        console.print("Total Workstations: ", len(tree.children))
    else:
        results = []
        for workstation in workstations:
            if not all and workstation.get("env", {}).get("LDAP") != user:
                continue

            result = {}
            result["name"] = workstation["name"].split("/")[-1]
            result["user"] = workstation["env"]["LDAP"]
            result["user"] = workstation["env"]["LDAP"]
            result["project"] = workstation["project"]
            result["location"] = workstation["location"]
            result["config"] = workstation["config"]["name"].split("/")[-1]
            result["cluster"] = workstation["cluster"]
            result["state"] = workstation["state"].name
            result["idle_timeout"] = workstation["config"]["idle_timeout"]
            result["max_runtime"] = workstation["config"]["max_runtime"]
            result["type"] = workstation["config"]["machine_type"]
            result["image"] = workstation["config"]["image"]
            results.append(result)

        json_data = json.dumps(results, indent=4)
        console.print(json_data)


@command()
@click.option(
    "-n",
    "--name",
    help="Name of the workstation to start.",
    type=str,
    metavar="<str>",
    required=True,
)
@click.option(
    "--code",
    help="Open workstation in VSCode locally. "
    "This requires setup illustrated in "
    "https://workstation.mlds.cash/#connect-to-a-workstation-with-local-vs-code",
    is_flag=True,
    default=False,
)
@click.option(
    "--browser",
    help="Open workstation with a remote VSCode session in a web browser.",
    is_flag=True,
    default=False,
)
@click.pass_context
def start(context: click.Context, name: str, code: bool, browser: bool, **kwargs):
    """Start workstation and optionally open it either locally with VSCode or through VSCode in a browser."""
    # Make sure the user is authenticated
    check_gcloud_auth()

    if code and browser:
        raise ValueError(
            "Select either local VSCode (--code) or remote VSCode in web browser (--browser)."
        )

    workstation_details = config_manager.read_configuration(name)

    response = start_workstation(**workstation_details)
    url = f"https://80-{response.host}"
    if not code and not browser:
        console.print(
            "Use --browser or --code to open the workstation in browser or vs code directly."
        )
        console.print(url)
    elif code:
        url = f"vscode://vscode-remote/ssh-remote+{name}/home/{getpass.getuser()}"
        console.print("Opening workstation in VSCode...")
        webbrowser.open(url)
    elif browser:
        console.print(f"Opening workstation at {url}...")
        webbrowser.open(url)


@command()
@click.option(
    "--name",
    help="Name of the workstation to stop.",
    type=str,
    metavar="<str>",
)
@click.pass_context
def stop(context: click.Context, **kwargs):
    """Stop workstation."""
    # Make sure the user is authenticated
    check_gcloud_auth()

    workstation_details = config_manager.read_configuration(kwargs["name"])
    response = stop_workstation(**workstation_details)
    console.print(response.name, response.state)


@command()
@click.option(
    "--name",
    help="Name of the workstation to delete.",
    type=str,
    metavar="<str>",
)
@click.pass_context
def delete(context: click.Context, **kwargs):
    """Delete workstation."""
    # Make sure the user is authenticated
    check_gcloud_auth()

    workstation_details = config_manager.read_configuration(kwargs["name"])

    response = delete_workstation(**workstation_details)
    config_manager.delete_configuration(kwargs["name"])
    if response.state.value == 0:
        console.print(f"Workstation {kwargs['name']} deleted.")


@command()
@click.option(
    "--name",
    help="Name of the workstation to sync.",
    type=str,
    metavar="<str>",
)
@click.pass_context
def sync(
    context: click.Context,
    name: str,
    **kwargs,
):
    """Sync files to workstation."""
    # Make sure the user is authenticated
    check_gcloud_auth()

    # TDOO: Add source and destination options
    source = "~/remote-machines/workstation/"
    destination = "~/"

    workstation_details = config_manager.read_configuration(name)

    result = sync_files_workstation(
        source=source,
        destination=destination,
        **workstation_details,
    )

    for line in result.stdout.split("\n"):
        console.print(line)
    if result.returncode != 0:
        console.print(result.args)
        console.print(result.stderr)


@command()
@click.argument(
    "name",
    type=str,
)
@click.option(
    "--project",
    help="Name of the workstation GCP project.",
    type=str,
    metavar="<str>",
)
def logs(name: str, project: str, **kwargs):
    """Open logs for the workstation."""
    check_gcloud_auth()
    instances = get_instance_assignment(project=project, name=name)
    instance = instances.get(name, None)
    if instances is None:
        console.print(f"Workstation {name} not found.")
        return
    console.print(f"Logs for instance: {instance.get('instance_name')} opening")
    webbrowser.open(instance.get("logs_url"))
