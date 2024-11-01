import pytest
from pytest_mock import MockerFixture
from workstation.utils import get_instance_assignment, process_entry


def test_process_entry(mocker: MockerFixture):
    # Mocking a log entry object
    entry = mocker.MagicMock()
    entry.resource.labels.get.return_value = "workstation-id"
    entry.labels.get.side_effect = ["instance-name", "instance-id"]

    project = "test-project"

    # Expected URL
    resource_type = "gce_instance"
    base_url = f"https://console.cloud.google.com/logs/query;query=resource.type%3D%22{resource_type}%22%0Aresource.labels.instance_id%3D%22"
    expected_url = f"{base_url}instance-id%22?project={project}"

    # Call the function
    workstation_id, log_entry = process_entry(entry, project)

    # Assertions
    assert workstation_id == "workstation-id"
    assert log_entry == {
        "instance_name": "instance-name",
        "instance_id": "instance-id",
        "logs_url": expected_url,
    }


def test_get_instance_assignment(mocker: MockerFixture):
    # Mock the check_gcloud_auth function
    mocker.patch("workstation.utils.check_gcloud_auth", return_value=True)
    # Mock the Client and its list_entries method
    mock_client = mocker.patch("workstation.utils.cloud_logging.Client")
    mock_instance = mock_client.return_value
    entry_mock = mocker.MagicMock()
    entry_mock.resource.labels.get.return_value = "workstation-id"
    entry_mock.labels.get.side_effect = ["instance-name", "instance-id"]
    mock_instance.list_entries.return_value = [entry_mock]

    project = "test-project"
    name = "workstation-id"

    result = get_instance_assignment(project, name)

    expected_result = {
        "workstation-id": {
            "instance_name": "instance-name",
            "instance_id": "instance-id",
            "logs_url": "https://console.cloud.google.com/logs/query;query=resource.type%3D%22gce_instance%22%0Aresource.labels.instance_id%3D%22instance-id%22?project=test-project",
        }
    }

    assert result == expected_result
