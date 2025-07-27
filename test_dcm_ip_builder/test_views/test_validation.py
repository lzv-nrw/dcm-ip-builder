"""Test-module for validation-endpoint."""

from pathlib import Path
from copy import deepcopy
from uuid import uuid4
from shutil import copytree

import pytest

from dcm_ip_builder import app_factory
from dcm_ip_builder.models import ValidationReport


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body():
    return {
        "validation": {
            "target": {"path": str("test-bag")},
        }
    }


def test_validate_minimal(minimal_request_body, testing_config):
    """Test minimal functionality of /validate-POST endpoint."""

    app = app_factory(testing_config())
    client = app.test_client()

    # submit job
    response = client.post("/validate", json=minimal_request_body)

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    assert report["data"]["valid"]
    assert report["data"]["originSystemId"] == "id"
    assert report["data"]["externalId"] == "0"


@pytest.mark.parametrize(
    ("ip", "valid"),
    [("test-bag", True), ("test-bag_bad", False)],
    ids=["valid-ip", "invalid-ip"],
)
def test_validate(minimal_request_body, testing_config, ip, valid):
    """Test functionality of /validate-POST endpoint."""

    app = app_factory(testing_config())
    client = app.test_client()

    # submit job
    request_body = deepcopy(minimal_request_body)
    request_body["validation"]["target"]["path"] = str(
        Path(minimal_request_body["validation"]["target"]["path"]).parent / ip
    )
    response = client.post("/validate", json=request_body)

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    assert report["data"]["valid"] is valid
    assert ("originSystemId" in report["data"]) is valid
    assert ("externalId" in report["data"]) is valid


def test_validate_with_argument(
    minimal_request_body,
    testing_config,
    fixtures,
    file_storage,
    run_service,
):
    """
    Test /validate-POST endpoint with a plugin-argument in the request.
    """
    # fake profile server
    fake_profile_url = "http://localhost:8081/profile.json"
    fake_profile = deepcopy(testing_config.BAGIT_PROFILE)
    fake_profile["BagIt-Profile-Info"][
        "BagIt-Profile-Identifier"
    ] = fake_profile_url
    fake_payload_profile_url = "http://localhost:8081/payload-profile.json"
    fake_payload_profile = deepcopy(testing_config.PAYLOAD_PROFILE)
    fake_payload_profile["BagIt-Payload-Profile-Info"][
        "BagIt-Payload-Profile-Identifier"
    ] = fake_payload_profile_url
    run_service(
        routes=[
            ("/profile.json", lambda: fake_profile, ["GET"]),
            ("/payload-profile.json", lambda: fake_payload_profile, ["GET"]),
        ],
        port=8081,
    )

    # create fake ip ip
    path = file_storage / str(uuid4())
    copytree(fixtures / "test-bag", path)
    (path / "bag-info.txt").write_text(
        f"""Bag-Software-Agent: dcm-ip-builder v0.0.0
BagIt-Payload-Profile-Identifier: {fake_payload_profile_url}
BagIt-Profile-Identifier: {fake_profile_url}
Bagging-DateTime: 2024-03-27T15:22:38+01:00
DC-Creator: Max Muster, et al.
DC-Rights: https://creativecommons.org/licenses/by-nd/3.0/de/
DC-Title: Some title
External-Identifier: 0
Origin-System-Identifier: id
Payload-Oxum: 2222.2
Source-Organization: https://d-nb.info/gnd/2047974-8
""",
        encoding="utf-8",
    )

    app = app_factory(testing_config())
    client = app.test_client()

    # submit job
    minimal_request_body["validation"]["target"]["path"] = path.name
    minimal_request_body["validation"]["BagItProfile"] = fake_profile_url

    token = client.post("/validate", json=minimal_request_body).json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    print(ValidationReport.from_json(report).log.fancy())

    assert report["data"]["valid"]
    assert "originSystemId" in report["data"]
    assert "externalId" in report["data"]
