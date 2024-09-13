import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from textwrap import dedent

import yaml
from rich.console import Console

from workstation.utils import NoPortFree, check_socket

console = Console()


@dataclass
class WorkstationConfig:
    """A class to represent a Workstation's configuration.

    Attributes
    ----------
    name : str
        The name of the workstation.
    location : str
        The location where the workstation is deployed.
    cluster : str
        The cluster associated with the workstation.
    config : str
        The specific configuration settings of the workstation.
    project : str
        The project associated with the workstation.

    Methods
    -------
    generate_workstation_yml() -> Path
        Generates a YAML configuration file for the workstation and saves it to the current directory.
    """

    name: str
    location: str
    cluster: str
    config: str
    project: str

    def generate_workstation_yml(self) -> Path:
        """Generate a YAML configuration file for the workstation.

        Returns
        -------
        Path
            The path to the generated YAML file.
        """
        write_path = Path(".", f"{self.name}.yml")
        with open(write_path, "w") as file:
            yaml.dump(asdict(self), file, sort_keys=False)

        return write_path


class ConfigManager:
    """A class to manage Workstation configurations.

    Attributes
    ----------
    workstation_data_dir : Path
        The directory where workstation data is stored.
    workstation_configs : Path
        The directory where individual workstation configurations are stored.

    Methods
    -------
    check_if_config_exists(name: str) -> bool
        Checks if a configuration file with the given name exists.
    write_configuration(project: str, name: str, location: str, cluster: str, config: str) -> Path
        Writes the configuration to a YAML file and returns the path to it.
    read_configuration(name: str) -> dict
        Reads the configuration for the given name and returns it as a dictionary.
    delete_configuration(name: str) -> None
        Deletes the configuration file and its corresponding YAML file for the given name.
    write_ssh_config(name: str, user: str, project: str, cluster: str, config: str, region: str)
        Writes the SSH configuration for the workstation.
    """

    def __init__(self):
        self.workstation_data_dir = Path.home() / ".workstations"
        self.workstation_configs = self.workstation_data_dir / "configs"

    def check_if_config_exists(self, name: str) -> bool:
        """Check if a configuration file with the given name exists.

        Parameters
        ----------
        name : str
            The name of the configuration to check.

        Returns
        -------
        bool
            True if the configuration exists, False otherwise.
        """
        return (self.workstation_configs / (name + ".yml")).exists()

    def write_configuration(
        self, project: str, name: str, location: str, cluster: str, config: str
    ) -> Path:
        """Write the configuration to a YAML file.

        Parameters
        ----------
        project : str
            The project name.
        name : str
            The name of the workstation.
        location : str
            The location of the workstation.
        cluster : str
            The cluster associated with the workstation.
        config : str
            The specific configuration settings.

        Returns
        -------
        Path
            The path to the written YAML file.

        Raises
        ------
        Exception
            If any error occurs during the writing process.
        """
        self.workstation_configs.mkdir(parents=True, exist_ok=True)

        current_dir = Path.cwd()
        os.chdir(self.workstation_configs)
        try:
            workstation = WorkstationConfig(
                project=project,
                name=name,
                location=location,
                cluster=cluster,
                config=config,
            )

            workstation_path = workstation.generate_workstation_yml()
            return self.workstation_configs / workstation_path
        except Exception as e:
            os.chdir(current_dir)
            raise e

    def read_configuration(self, name: str) -> dict:
        """Read the configuration for the given name.

        Parameters
        ----------
        name : str
            The name of the configuration to read.

        Returns
        -------
        dict
            The contents of the configuration file as a dictionary.

        Raises
        ------
        FileNotFoundError
            If the configuration file does not exist.
        KeyError
            If required keys are missing from the configuration file.
        """
        workstation_config = self.workstation_configs / (name + ".yml")

        if not workstation_config.exists():
            raise FileNotFoundError(
                f"Configuration {name} not found, please check if {workstation_config} exists."
            )

        with open(workstation_config, "r") as file:
            contents = yaml.safe_load(file)

        # check that project, name, location, cluster, and config are in the file
        # For the error say what keys are missing
        if not all(
            key in contents
            for key in ["project", "name", "location", "cluster", "config"]
        ):
            missing_keys = [
                key
                for key in ["project", "name", "location", "cluster", "config"]
                if key not in contents
            ]
            raise KeyError(f"Configuration file {name} is missing keys {missing_keys}")

        return contents

    def delete_configuration(self, name: str) -> None:
        """Delete the configuration file and its corresponding YAML file.

        Parameters
        ----------
        name : str
            The name of the configuration to delete.

        Raises
        ------
        FileNotFoundError
            If the configuration file does not exist.
        """
        workstation_yml = self.workstation_configs / (name + ".yml")
        workstation_config = self.workstation_configs / (name + ".config")

        if not workstation_config.exists():
            raise FileNotFoundError(f"Configuration {name} not found")
        if not workstation_yml.exists():
            raise FileNotFoundError(f"Configuration {name} not found")

        workstation_config.unlink()
        workstation_yml.unlink()

    def write_ssh_config(
        self,
        name: str,
        user: str,
        project: str,
        cluster: str,
        config: str,
        region: str,
    ):
        """Write the SSH configuration for the workstation.

        Parameters
        ----------
        name : str
            The name of the workstation.
        user : str
            The user for SSH connection.
        project : str
            The project name.
        cluster : str
            The cluster associated with the workstation.
        config : str
            The specific configuration settings.
        region : str
            The region where the workstation is deployed.

        Raises
        ------
        NoPortFree
            If no free port is found after checking 20 ports.
        """
        workstation_config = self.workstation_configs / (name + ".config")

        # get all of the ports that are currently in use from the config files
        ports = []
        for config_file in self.workstation_configs.glob("*.config"):
            with open(config_file, "r") as file:
                contents = file.read()
                # Check if the match is not None before calling group
                match = re.search(r"\n\s*Port\s+(\d+)", contents)
                if match is not None:
                    port = int(match.group(1))
                    ports.append(port)

        if len(ports) == 0:
            port = 6000
        else:
            port = max(ports) + 1

        for _ in range(20):
            if check_socket("localhost", port):
                break
            port += 1
        else:
            raise NoPortFree("Could not find a free port after checking 20 ports.")

        proxy_command = (
            "sh -c '"
            "cleanup() { pkill -P $$; }; "
            "trap cleanup EXIT; "
            "gcloud workstations start-tcp-tunnel "
            f"--project={project} "
            f"--cluster={cluster} "
            f"--config={config} "
            f"--region={region} "
            "--local-host-port=localhost:%p %h 22 & "
            "timeout=10; "
            "while ! nc -z localhost %p; do "
            "sleep 1; "
            "timeout=$((timeout - 1)); "
            "if [ $timeout -le 0 ]; then "
            "exit 1; "
            "fi; "
            "done; "
            "nc localhost %p'"
        )

        config_content = dedent(
            f"""
            Host {name}
                HostName {name}
                Port {port}
                User {user}
                StrictHostKeyChecking no
                UserKnownHostsFile /dev/null
                ControlMaster auto
                ControlPersist 30m
                ControlPath ~/.ssh/cm/%r@%h:%p
                ProxyCommand {proxy_command}
                """
        ).strip()

        with open(workstation_config, "w") as file:
            file.write(config_content)
