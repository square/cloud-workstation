import getpass
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from workstation.cli import crud


@patch("workstation.cli.crud.list_workstation_configs")
@patch("workstation.cli.crud.check_gcloud_auth")
@patch("workstation.cli.crud.get_gcloud_config")
def test_list_configs(
    mock_get_gcloud_config, mock_check_gcloud_auth, mock_list_workstation_configs
):
    runner = CliRunner()
    mock_get_gcloud_config.return_value = (
        "test-project",
        "us-central1",
        "test-account",
    )
    mock_check_gcloud_auth.return_value = True
    mock_list_workstation_configs.return_value = [
        {
            "name": "config/config1",
            "image": "img",
            "machine_type": "type_a",
            "machine_specs": "spec_a",
            "idle_timeout": 360,
            "max_runtime": 720,
        }
    ]

    result = runner.invoke(crud.list_configs)
    print(result.output)

    assert result.exit_code == 0
    assert "config1" in result.output


@patch("workstation.cli.crud.list_workstations")
@patch("workstation.cli.crud.check_gcloud_auth")
@patch("workstation.cli.crud.get_gcloud_config")
def test_list(mock_get_gcloud_config, mock_check_gcloud_auth, mock_list_workstations):
    runner = CliRunner()
    mock_get_gcloud_config.return_value = (
        "test-project",
        "us-central1",
        "test-account",
    )
    mock_check_gcloud_auth.return_value = True
    workstation_state = MagicMock()
    workstation_state.name = "STATE_RUNNING"
    mock_list_workstations.return_value = [
        {
            "name": "workstation1",
            "project": "test-project",
            "location": "us-central1",
            "cluster": "cluster-public",
            "state": type('obj', (object,), {'name' : 'STATE_RUNNING'})(),
            "env": {"LDAP": "test-user"},
            "config": {
                "name": "this/config-name",
                "image": "test-image",
                "machine_type": "n1-standard-4",
                "idle_timeout": 3600,
                "max_runtime": 7200,
            },
        },
        {
            "name": "workstation2",
            "project": "test-project",
            "location": "us-central1",
            "cluster": "cluster-public",
            "state": type('obj', (object,), {'name' : 'STATE_STOPPED'})(),
            "env": {"LDAP": "other-user"},
            "config": {
                "name": "this/config-name",
                "image": "test-image",
                "machine_type": "n1-standard-4",
                "idle_timeout": 3600,
                "max_runtime": 7200,
            }
        }
    ]

    result = runner.invoke(crud.list, ["--user", "test-user"])
    assert result.exit_code == 0
    assert "workstation1" in result.output
    assert "User: test-user" in result.output
    assert "User: other-user" not in result.output

    result = runner.invoke(crud.list, ["--user", "test-user", "--json"])
    assert result.exit_code == 0
    assert "workstation1" in result.output
    assert "\"user\": \"test-user\"" in result.output
    assert "\"user\": \"other-user\"" not in result.output
