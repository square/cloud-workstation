import configparser
import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from subprocess import CalledProcessError

import google.auth
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.auth.transport.requests import Request
from google.cloud import logging as cloud_logging  # Google Cloud Logging client
from rich.console import Console
from rich.tree import Tree

console = Console()


def default_serializer(obj):
    """
    Handle specific object types that are not serializable by default.

    Parameters
    ----------
    obj : Any
        The object to serialize.

    Returns
    -------
    Any
        Serialized object (e.g., dictionary).

    Raises
    ------
    TypeError
        If the object type is not serializable.
    """
    # Handle protobuf ScalarMapContainer
    if hasattr(obj, "MapContainer") or "google._upb._message.ScalarMapContainer" in str(
        type(obj)
    ):
        # Convert and filter out non-essential attributes
        return {
            key: value for key, value in obj.__dict__.items() if key != "MapContainer"
        }
    raise TypeError(f"Type {type(obj)} not serializable")


def read_gcloud_config():
    """
    Read the default Google Cloud configuration.

    Returns
    -------
    Tuple[str, str, str]
        Default project ID, location, and account from gcloud configuration.
    """
    config_path = os.path.expanduser("~/.config/gcloud/configurations/config_default")
    config = configparser.ConfigParser()
    config.read(config_path)

    # Assuming the default settings are under the 'core' section
    default_project = config.get("core", "project", fallback=None)
    default_location = config.get("compute", "region", fallback=None)
    account = config.get("core", "account", fallback=None)

    return default_project, default_location, account


def config_tree(configs: list) -> Tree:
    """
    Generate a tree structure for displaying workstation configurations using Rich library.

    Parameters
    ----------
    configs : list
        A list of workstation configurations.

    Returns
    -------
    Tree
        A Rich Tree object representing the configurations.
    """
    tree = Tree("Configs", style="bold blue")

    for config in configs:
        config_branch = tree.add(f"Config: {config['name'].split('/')[-1]}")
        config_branch.add(f":minidisc: Image: {config['image']}")
        config_branch.add(f":computer: Machine Type: {config['machine_type']}")
        config_branch.add(f":computer: Machine Specs: {config['machine_specs']}")
        config_branch.add(
            f":hourglass_flowing_sand: Idle Timeout (s): {str(config['idle_timeout'])}"
        )
        config_branch.add(
            f":hourglass_flowing_sand: Max Runtime (s): {str(config['max_runtime'])}"
        )

    return tree


def check_socket(host, port):
    """
    Check if a socket on the given host and port is available.

    Parameters
    ----------
    host : str
        The hostname or IP address.
    port : int
        The port number.

    Returns
    -------
    bool
        True if the socket is available, False otherwise.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except socket.error:
        return False
    finally:
        s.close()


def sync_files_workstation(
    project: str,
    name: str,
    location: str,
    cluster: str,
    config: str,
    source: str,
    destination: str,
):
    """
    Synchronize files from the local system to the workstation using rsync over an SSH tunnel.

    Parameters
    ----------
    project : str
        The Google Cloud project ID.
    name : str
        The name of the workstation.
    location : str
        The Google Cloud location.
    cluster : str
        The workstation cluster name.
    config : str
        The workstation configuration name.
    source : str
        The source directory on the local system.
    destination : str
        The destination directory on the workstation.

    Returns
    -------
    subprocess.CompletedProcess
        The result of the rsync command.
    """
    port = 61000
    for _ in range(20):
        if check_socket("localhost", port):
            break
        port += 1
    else:
        raise NoPortFree("Could not find a free port after checking 20 ports.")

    process = subprocess.Popen(
        [
            "gcloud",
            "workstations",
            "start-tcp-tunnel",
            f"--project={project}",
            f"--cluster={cluster}",
            f"--config={config}",
            f"--region={location}",
            f"--region={location}",
            f"{name}",
            "22",
            f"--local-host-port=:{port}",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.poll() is not None:
        if process.returncode != 0:
            raise CalledProcessError(process.stderr.read())

    # use rsync to sync files from local to workstation
    source_path = os.path.expanduser(source)
    destination_path = f"localhost:{destination}"

    command = [
        "rsync",
        "-av",
        "--exclude=.venv",
        "--exclude=.git",
        "--exclude=.DS_Store",
        "-e",
        f"ssh -p {port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        source_path,
        destination_path,
    ]
    counter = 0
    while check_socket("localhost", port):
        if counter >= 10:
            break
        time.sleep(1)
        counter += 1

    result = subprocess.run(command, capture_output=True, text=True)
    process.kill()
    return result


class NoPortFree(Exception):
    """Exception raised when no free port is available for the SSH tunnel."""

    pass


def check_gcloud_auth():
    """
    Check if the current gcloud CLI is authenticated and refresh if necessary.

    Returns
    -------
    bool
        True if authentication is successful, False otherwise.

    Raises
    ------
    SystemExit
        If reauthentication is needed.
    """
    from google.auth import default

    try:
        credentials, project = google.auth.default()

        # Check if the credentials are valid and refresh if necessary
        if credentials.requires_scopes:
            credentials = credentials.with_scopes(
                ["https://www.googleapis.com/auth/cloud-platform"]
            )

        credentials.refresh(Request())
        return True

    except (DefaultCredentialsError, RefreshError):
        console.print(
            "Reauthentication is needed. Please run [bold blue]gcloud auth login & gcloud auth application-default login[/bold blue]."
        )
        sys.exit(1)


def get_instance_assignment(project: str, name: str):
    """
    Get the instance assignment log entries for a specific workstation.

    Parameters
    ----------
    project : str
        The Google Cloud project ID.
    name : str
        The name of the workstation.

    Returns
    -------
    Dict
        A dictionary of log entries related to the instance assignment.
    """
    check_gcloud_auth()
    client = cloud_logging.Client(project=project)

    timestamp = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    filter_str = (
        f'logName="projects/{project}/logs/workstations.googleapis.com%2Fvm_assignments" '
        f'AND timestamp >= "{timestamp}"'
    )

    entries = client.list_entries(filter_=filter_str)

    log_entries_dict = {}

    for entry in entries:
        try:
            workstation_id, log_entry = process_entry(entry, project)
            log_entries_dict[workstation_id] = log_entry
            if workstation_id == name:
                return log_entries_dict
        except Exception as exc:
            print(f"Entry {entry} generated an exception: {exc}")

    return log_entries_dict


def process_entry(entry, project):
    """
    Process a log entry to extract workstation information.

    Parameters
    ----------
    entry
        A log entry object.
    project : str
        The Google Cloud project ID.

    Returns
    -------
    Tuple[str, Dict]
        Workstation ID and a dictionary with instance information.
    """
    workstation_id = entry.resource.labels.get("workstation_id")
    instance_name = entry.labels.get("instance_name")
    instance_id = entry.labels.get("instance_id")

    resource_type = "gce_instance"
    base_url = f"https://console.cloud.google.com/logs/query;query=resource.type%3D%22{resource_type}%22%0Aresource.labels.instance_id%3D%22"
    url = f"{base_url}{instance_id}%22?project={project}"

    log_entry = {
        "instance_name": instance_name,
        "instance_id": instance_id,
        "logs_url": url,
    }

    return workstation_id, log_entry


def get_logger():
    """
    Set log level from LOG_LEVEL environment variable, default to INFO.

    This is useful for debugging purpose.
    The value of LOG_LEVEL should be one of these: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    # Avoid adding multiple handlers
    if not logger.handlers:
        handler = logging.StreamHandler()  # Log to console
        handler.setLevel(log_level)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


if __name__ == "__main__":
    pass
