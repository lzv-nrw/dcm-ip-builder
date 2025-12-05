"""Test-module for validation-endpoint."""

from pathlib import Path
from copy import deepcopy
from shutil import copytree
from uuid import uuid4
from json import dumps

import pytest

from dcm_ip_builder import app_factory
from dcm_ip_builder.components import Bag


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body():
    return {
        "validation": {
            "target": {"path": str("test-bag")},
        }
    }


@pytest.fixture(name="duplicate_bag")
def _duplicate_bag(file_storage, testing_config):
    """Duplicates "test-bag" to another directory."""
    duplicate = testing_config.FS_MOUNT_POINT / str(uuid4())
    copytree(file_storage / "test-bag", duplicate)
    return duplicate


def test_validate_minimal(
    minimal_request_body, testing_config, test_bag_baginfo
):
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
    assert (
        report["data"]["sourceOrganization"]
        == "https://d-nb.info/gnd/2047974-8"
    )
    assert report["data"]["bagInfoMetadata"] == test_bag_baginfo


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
    assert ("sourceOrganization" in report["data"]) is valid
    assert ("bagInfoMetadata" in report["data"]) is valid


@pytest.mark.parametrize(
    ("profile_in_store", "profile_online", "success"),
    [
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, False)
    ]
)
def test_load_bagit_profile_from_bag(
    file_storage, duplicate_bag, testing_config,
    profile_in_store, profile_online, success, run_service, test_profile
):
    """
    Test functionality of /validate-POST endpoint when loading
    the bagit profile from the bag.
    """

    bagit_profile_uri = "http://localhost:5555/bagit_profile.json"
    # manipulate bag to write custom "BagIt-Profile-Identifier"
    input_bag = Bag(duplicate_bag)
    input_bag.set_baginfo(
        input_bag.baginfo
        | {
            "BagIt-Profile-Identifier": [
                bagit_profile_uri
            ]
        }
    )
    # manipulate test_profile to write custom "BagIt-Profile-Identifier"
    test_profile["BagIt-Profile-Info"][
        "BagIt-Profile-Identifier"
    ] = bagit_profile_uri

    if profile_in_store:
        # write test_profile in profiles source
        target = file_storage / "profiles" / "test-profile.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dumps(test_profile), encoding="utf-8")

        class ThisTestingConfig(testing_config):
            FS_MOUNT_POINT = file_storage
            LOAD_BAGIT_PROFILE_FROM_BAG = True
            PROFILES_SRC = f"[{dumps(test_profile)}]"
    else:
        class ThisTestingConfig(testing_config):
            LOAD_BAGIT_PROFILE_FROM_BAG = True

    app = app_factory(ThisTestingConfig())
    client = app.test_client()

    if profile_online:
        # create profile-url server
        run_service(
            routes=[
                ("/bagit_profile.json", lambda: (test_profile, 200), ["GET"])
            ],
            port=5555,
        )

    # submit job
    response = client.post(
        "/validate",
        json={
            "validation": {
                "target": {
                    "path": str(duplicate_bag.relative_to(file_storage))
                }
            },
        },
    )

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    app.extensions["orchestra"].stop(stop_on_idle=True)
    report = client.get(f"/report?token={token}").json

    if success:
        assert report["data"]["success"]
        assert report["data"]["valid"]
        assert report["data"]["bagInfoMetadata"][
            "BagIt-Profile-Identifier"
        ] == [bagit_profile_uri]
    else:
        assert report["data"]["success"] is False
        assert len(report["log"]["ERROR"]) >= 1
        assert any(
            "Unable to load profile"
            in m["body"]
            for m in report["log"]["ERROR"]
        )
