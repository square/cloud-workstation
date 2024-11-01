import os
from pathlib import Path

import pytest

from workstation.config import ConfigManager


@pytest.fixture
def config_manager():
    return ConfigManager()


@pytest.fixture
def temp_workstation_dir(tmp_path):
    original_home = Path.home()
    os.environ["HOME"] = str(tmp_path)
    config_manager = ConfigManager()
    # Create necessary directories
    config_manager.workstation_configs.mkdir(parents=True, exist_ok=True)
    yield config_manager
    os.environ["HOME"] = str(original_home)


def test_write_ssh_config(temp_workstation_dir):
    manager = temp_workstation_dir

    # Test basic functionality
    name = "test_workstation"
    user = "test_user"
    project = "test_project"
    cluster = "test_cluster"
    config = "test_config"
    region = "test_region"

    manager.write_ssh_config(name, user, project, cluster, config, region)

    config_file_path = manager.workstation_configs / f"{name}.config"
    assert config_file_path.exists()

    with open(config_file_path, "r") as f:
        content = f.read()

    assert f"Host {name}" in content
    assert f"User {user}" in content
    assert (
        f"ProxyCommand sh -c 'cleanup() {{ pkill -P $$; }}; trap cleanup EXIT; gcloud workstations start-tcp-tunnel --project={project} --cluster={cluster} --config={config} --region={region} --local-host-port=localhost:%p %h 22 & timeout=10; while ! nc -z localhost %p; do sleep 1; timeout=$((timeout - 1)); if [ $timeout -le 0 ]; then exit 1; fi; done; nc localhost %p'"
        in content
    )

    manager = temp_workstation_dir

    name1 = "workstation1"
    user1 = "user1"
    project1 = "project1"
    cluster1 = "cluster1"
    config1 = "config1"
    region1 = "region1"

    name2 = "workstation2"
    user2 = "user2"
    project2 = "project2"
    cluster2 = "cluster2"
    config2 = "config2"
    region2 = "region2"

    manager.write_ssh_config(name1, user1, project1, cluster1, config1, region1)

    config_file_path1 = manager.workstation_configs / f"{name1}.config"
    with open(config_file_path1, "r") as f:
        content1 = f.read()
    assert user1 in content1

    manager.write_ssh_config(name2, user2, project2, cluster2, config2, region2)

    config_file_path2 = manager.workstation_configs / f"{name2}.config"
    with open(config_file_path2, "r") as f:
        content2 = f.read()
    assert user2 in content2


def test_write_ssh_config_no_existing_configs(temp_workstation_dir):
    manager = temp_workstation_dir

    name = "workstation_no_existing"
    user = "user_no_existing"
    project = "project_no_existing"
    cluster = "cluster_no_existing"
    config = "config_no_existing"
    region = "region_no_existing"

    manager.write_ssh_config(name, user, project, cluster, config, region)

    config_file_path = manager.workstation_configs / f"{name}.config"
    with open(config_file_path, "r") as f:
        content = f.read()

    assert user in content
    assert cluster in content
    assert config in content
    assert region in content
    assert project in content
    assert name in content


def test_read_and_write_configuration(temp_workstation_dir):
    manager = temp_workstation_dir

    name = "test_workstation"
    project = "test_project"
    location = "test_location"
    cluster = "test_cluster"
    config = "test_config"

    manager.write_configuration(project, name, location, cluster, config)

    contents = manager.read_configuration(name)

    assert contents["project"] == project
    assert contents["name"] == name
    assert contents["location"] == location
    assert contents["cluster"] == cluster
    assert contents["config"] == config


def test_delete_configuration(temp_workstation_dir):
    manager = temp_workstation_dir

    name = "test_workstation"
    project = "test_project"
    location = "test_location"
    cluster = "test_cluster"
    config = "test_config"

    manager.write_configuration(project, name, location, cluster, config)
    manager.write_ssh_config(name, "test_user", project, cluster, config, location)

    manager.delete_configuration(name)

    yml_file_path = manager.workstation_configs / f"{name}.yml"
    config_file_path = manager.workstation_configs / f"{name}.config"

    assert not yml_file_path.exists()
    assert not config_file_path.exists()
