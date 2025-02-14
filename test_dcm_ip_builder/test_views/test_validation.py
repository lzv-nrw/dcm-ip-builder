"""Test-module for validation-endpoint."""

from pathlib import Path
from copy import deepcopy
from unittest import mock

import pytest


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body():
    return {
        "validation": {
            "target": {"path": str("test-bag")},
        }
    }


def test_validate_minimal(
    client, minimal_request_body, wait_for_report
):
    """Test minimal functionality of /validate-POST endpoint."""

    # submit job
    response = client.post(
        "/validate",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert json["data"]["valid"]


@pytest.mark.parametrize(
    ("ip", "valid"),
    [
        ("test-bag", True),
        ("test-bag_bad", False)
    ],
    ids=["valid-ip", "invalid-ip"]
)
def test_validate(
    client, minimal_request_body, wait_for_report, ip, valid
):
    """Test functionality of /validate-POST endpoint."""

    # submit job
    request_body = deepcopy(minimal_request_body)
    request_body["validation"]["target"]["path"] = str(
        Path(minimal_request_body["validation"]["target"]["path"]).parent / ip
    )
    response = client.post(
        "/validate",
        json=request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert json["data"]["valid"] == valid


@pytest.mark.parametrize(
    ("profile", "valid"),
    [
        ("https://lzv.nrw/test_bagit_profile.json", True),
        ("request_bagit_profile", False)  # expected validation error: 'BagIt-Profile-Identifier' tag does not contain this profile's URI: <https://lzv.nrw/tests_bagit_profile.json> != <request_bagit_profile>"
    ],
    ids=["valid-ip", "invalid-ip"]
)
def test_validate_with_argument(
    client, minimal_request_body, wait_for_report,
    profile, valid, testing_config
):
    """
    Test /validate-POST endpoint with a plugin-argument in the request.
    """

    # submit job
    request_body = deepcopy(minimal_request_body)
    request_body["validation"]["target"]["path"] = str(
        Path(minimal_request_body["validation"]["target"]["path"]).parent
        / "test-bag"
    )
    request_body["validation"]["BagItProfile"] = profile

    # fake get_profile
    patcher_get_profile = mock.patch(
        "bagit_profile.Profile.get_profile",
        side_effect=lambda *args, **kwargs: testing_config.BAGIT_PROFILE
    )
    patcher_get_profile.start()

    response = client.post(
        "/validate",
        json=request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert json["data"]["valid"] == valid

    patcher_get_profile.stop()


@pytest.mark.parametrize(
    ("request_body_path", "new_value", "expected_status"),
    [
        (
            [],
            None,
            201
        ),
        (
            ["validation", "target", "path2"],
            0,
            400
        ),
        (
            ["validation", "plugins"],
            0,
            400
        ),
        (
            ["callbackUrl"],
            "no-url",
            422
        ),
    ],
    ids=[
        "good", "bad_target", "bad_plugins", "bad_callback_url",
    ]
)
def test_validate_ip_handlers(
    client, minimal_request_body, request_body_path, new_value, expected_status
):
    """
    Test correct application of handlers in /validate-POST endpoint.
    """

    def set_inner_dict(in_, keys, value):
        if len(keys) == 0:
            return
        if len(keys) == 1:
            in_[keys[0]] = value
            return
        return set_inner_dict(in_[keys[0]], keys[1:], value)

    request_body = deepcopy(minimal_request_body)
    set_inner_dict(request_body, request_body_path, new_value)

    response = client.post(
        "/validate",
        json=request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == expected_status
    if response.status_code == 201:
        assert response.mimetype == "application/json"
    else:
        assert response.mimetype == "text/plain"


def test_validate_ip_handlers_missing_validation_block(
    client, minimal_request_body
):
    """
    Test correct application of handlers in /validate-POST endpoint.
    """

    request_body = deepcopy(minimal_request_body)
    del request_body["validation"]

    response = client.post(
        "/validate",
        json=request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 400
    assert response.mimetype == "text/plain"
