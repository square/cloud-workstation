import getpass
from unittest.mock import patch

from workstation.core import create_workstation


@patch("workstation.core.workstations_v1beta.WorkstationsClient")
@patch("workstation.core.config_manager.write_configuration")
def test_create_workstation_env_dict(mock_write_configuration, mock_workstations_client):
    mock_client_instance = mock_workstations_client.return_value
    mock_operation = mock_client_instance.create_workstation.return_value
    mock_operation.result.return_value = {}

    envs = (("KEY1", "VALUE1"), ("KEY2", "VALUE2"))
    create_workstation(
        project="test-project",
        location="us-central1",
        cluster="default-cluster",
        config="default-config",
        name="test-workstation",
        account="test-account",
        user="test-user",
        envs=envs,
    )

    expected_env = {
        "LDAP": "test-user",
        "ACCOUNT": "test-account",
        "KEY1": "VALUE1",
        "KEY2": "VALUE2",
    }

    assert mock_client_instance.create_workstation.call_count == 1
    _, kwargs = mock_client_instance.create_workstation.call_args
    assert kwargs["request"].workstation.env == expected_env
