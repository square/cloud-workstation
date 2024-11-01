import sys
from typing import Dict, List, Optional, Tuple

from google.api_core.exceptions import AlreadyExists
from google.api_core.operation import Operation
from google.cloud import workstations_v1beta
from google.cloud.workstations_v1beta.types import Workstation
from rich.console import Console

from workstation.config import ConfigManager
from workstation.machines import machine_types
from workstation.utils import get_logger

console = Console()
config_manager = ConfigManager()
logger = get_logger()


def list_workstation_clusters(project: str, location: str) -> List[Dict]:
    """
    List workstation clusters in a specific project and location.

    Parameters
    ----------
    project : str
        The Google Cloud project ID.
    location : str
        The Google Cloud location.

    Returns
    -------
    List[Dict]
        A list of workstation cluster configurations.
    """
    client = workstations_v1beta.WorkstationsClient()

    request = workstations_v1beta.ListWorkstationClustersRequest(
        parent=f"projects/{project}/locations/{location}",
    )
    page_result = client.list_workstation_clusters(request=request)

    configs = []
    for config in page_result:
        configs.append(
            {
                "name": config.name,
                "image": config.subnetwork,
            }
        )
    return configs


def list_workstation_configs(project: str, location: str, cluster: str) -> List[Dict]:
    """
    List usable workstation configurations in a specific project, location, and cluster.

    Parameters
    ----------
    project : str
        The Google Cloud project ID.
    location : str
        The Google Cloud location.
    cluster : str
        The workstation cluster name.

    Returns
    -------
    List[Dict]
        A list of usable workstation configurations.
    """
    client = workstations_v1beta.WorkstationsClient()

    request = workstations_v1beta.ListUsableWorkstationConfigsRequest(
        parent=f"projects/{project}/locations/{location}/workstationClusters/{cluster}",
    )
    page_result = client.list_usable_workstation_configs(request=request)

    configs = []
    for config in page_result:
        if config.host.gce_instance.machine_type not in machine_types:
            logger.debug(
                f"{config.host.gce_instance.machine_type} not exist in machine_types in machines.py"
            )
            continue
        machine_details = machine_types[config.host.gce_instance.machine_type]
        machine_specs = f"machine_specs[{machine_details['vCPUs']} vCPUs, {machine_details['Memory (GB)']} GB]"
        configs.append(
            {
                "name": config.name,
                "image": config.container.image,
                "machine_type": config.host.gce_instance.machine_type,
                "idle_timeout": config.idle_timeout.total_seconds(),
                "max_runtime": config.running_timeout.total_seconds(),
                "machine_specs": machine_specs,
            }
        )
    return configs


def create_workstation(
    project: str,
    location: str,
    cluster: str,
    config: str,
    name: str,
    account: str,
    user: str,
    proxy: Optional[str] = None,
    no_proxy: Optional[str] = None,
    envs: Optional[Tuple[Tuple[str, str]]] = None,
) -> Workstation:
    """
    Create a new workstation with the specified configuration.

    Parameters
    ----------
    project : str
        The Google Cloud project ID.
    location : str
        The Google Cloud location.
    cluster : str
        The workstation cluster name.
    config : str
        The workstation configuration name.
    name : str
        The name of the new workstation.
    account : str
        The account associated with the workstation.
    user : str
        The user associated with the workstation.
    proxy : Optional[str], optional
        Proxy settings, by default None.
    no_proxy : Optional[str], optional
        No-proxy settings, by default None.
    envs : Optional[Tuple[Tuple[str, str]]], optional
        Additional environment variables to set, by default None.

    Returns
    -------
    Workstation
        Response from the workstation creation request.
    """
    client = workstations_v1beta.WorkstationsClient()
    env = {
        "LDAP": user,
        "ACCOUNT": account,
    }

    if proxy:
        env["http_proxy"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["https_proxy"] = proxy
        env["HTTP_PROXY"] = proxy
        env["no_proxy"] = no_proxy
        env["NO_PROXY"] = no_proxy

    if envs:
        user_envs = dict(envs)
        # ensure that no duplicate keys are added to env
        for key, value in user_envs.items():
            if key not in env:
                env[key] = value
            else:
                logger.warning(
                    f"Environment variable {key} already exists in the environment, skipping"
                )

    request = workstations_v1beta.CreateWorkstationRequest(
        parent=f"projects/{project}/locations/{location}/workstationClusters/{cluster}/workstationConfigs/{config}",
        workstation_id=name,
        workstation=Workstation(
            display_name=name,
            env=env,
        ),
    )

    try:
        operation = client.create_workstation(request=request)
        response = operation.result()
    except AlreadyExists:
        console.print(f"Workstation [bold blue]{name}[/bold blue] already exists")
        sys.exit(1)

    config_manager.write_configuration(
        project=project,
        name=name,
        location=location,
        cluster=cluster,
        config=config,
    )

    return response


def start_workstation(
    project: str,
    name: str,
    location: str,
    cluster: str,
    config: str,
) -> Operation:
    """
    Start an existing workstation.

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

    Returns
    -------
    Operation
        Response from the workstation start request.
    """
    client = workstations_v1beta.WorkstationsClient()

    request = workstations_v1beta.StartWorkstationRequest(
        name=f"projects/{project}/locations/{location}/workstationClusters/{cluster}/workstationConfigs/{config}/workstations/{name}",
    )

    operation = client.start_workstation(request=request)
    console.print("Waiting for operation to complete (~3 minutes)...")
    response = operation.result()

    return response


def stop_workstation(
    project: str,
    name: str,
    location: str,
    cluster: str,
    config: str,
) -> Operation:
    """
    Stop an existing workstation.

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

    Returns
    -------
    Operation
        Response from the workstation stop request.
    """
    client = workstations_v1beta.WorkstationsClient()

    request = workstations_v1beta.StopWorkstationRequest(
        name=f"projects/{project}/locations/{location}/workstationClusters/{cluster}/workstationConfigs/{config}/workstations/{name}",
    )

    operation = client.stop_workstation(request=request)
    console.print("Waiting for operation to complete...")
    response = operation.result()

    return response


def delete_workstation(
    project: str,
    name: str,
    location: str,
    cluster: str,
    config: str,
) -> Operation:
    """
    Delete an existing workstation.

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

    Returns
    -------
    Operation
        Response from the workstation deletion request.
    """
    client = workstations_v1beta.WorkstationsClient()

    request = workstations_v1beta.DeleteWorkstationRequest(
        name=f"projects/{project}/locations/{location}/workstationClusters/{cluster}/workstationConfigs/{config}/workstations/{name}",
    )

    operation = client.delete_workstation(request=request)
    console.print("Waiting for operation to complete...")
    response = operation.result()

    return response


def list_workstations(project: str, location: str, cluster: str) -> List[Dict]:
    """
    List all workstations in a specific project, location, and cluster.

    Parameters
    ----------
    project : str
        The Google Cloud project ID.
    location : str
        The Google Cloud location.
    cluster : str
        The workstation cluster name.

    Returns
    -------
    List[Dict]
        A list of workstation configurations.
    """
    configs = list_workstation_configs(
        project=project, location=location, cluster=cluster
    )

    client = workstations_v1beta.WorkstationsClient()
    workstations = []

    for config in configs:
        request = workstations_v1beta.ListWorkstationsRequest(
            parent=config.get("name"),
        )

        page_result = client.list_workstations(request=request)

        for workstation in page_result:
            workstations.append(
                {
                    "name": workstation.name,
                    "state": workstation.state,
                    "env": workstation.env,
                    "config": config,
                    "project": project,
                    "location": location,
                    "cluster": cluster,
                }
            )
    return workstations
