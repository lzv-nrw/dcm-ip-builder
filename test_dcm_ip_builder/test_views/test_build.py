"""Test-module for build-endpoint."""

from pathlib import Path
from unittest import mock

import pytest
from flask import jsonify, Response
from bagit import Bag
from lxml import etree as et
from dcm_common import LoggingContext as Context

from dcm_ip_builder import app_factory


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body(minimal_build_config):
    return {
        "build": {
            "target": {
                "path": str("test-ie")
            },
            "configuration": minimal_build_config
        },
        "validation": {"modules": []}
    }


def test_build_minimal(
    client, testing_config, minimal_request_body, wait_for_report
):
    """Test basic functionality of /build-POST endpoint."""

    # submit job
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)

    assert (testing_config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
    assert json["data"]["valid"]

    assert Bag(
        str(testing_config.FS_MOUNT_POINT / json["data"]["path"])
    ).is_valid()


def test_build_failing_get_output_path(
    client, minimal_request_body, wait_for_report
):
    """Test basic functionality of /build-POST endpoint."""
    patcher = mock.patch(
        "dcm_ip_builder.views.build.get_output_path",
        side_effect=lambda *args, **kwargs: None
    )
    patcher.start()

    # submit job
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)

    assert "path" not in json["data"]
    assert not json["data"]["valid"]

    patcher.stop()


def test_build_missing_meta(
    client, testing_config, minimal_request_body, wait_for_report
):
    """Test /build-POST with missing metadata."""

    # submit job
    minimal_request_body["build"]["target"]["path"] = str(
        Path(minimal_request_body["build"]["target"]["path"]).parent
        / "test-ie-missing-meta"
    )
    minimal_request_body["validation"]["modules"] = ["bagit_profile"]

    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)

    # output of attempt should exist (but be invalid)
    assert (testing_config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
    assert not json["data"]["valid"]


@pytest.mark.parametrize(
    ("ie", "dcxml_exists"),
    [
        ("test-ie", True),
        ("test-ie-mets", False)
    ],
    ids=["dc-metadata", "mets-metadata"]
)
def test_build_dc_xml(
    ie, dcxml_exists, testing_config, client, minimal_request_body, wait_for_report
):
    """Test basic functionality of /build-POST endpoint."""
    # submit job
    minimal_request_body["build"]["target"]["path"] = str(
        Path(minimal_request_body["build"]["target"]["path"]).parent / ie
    )

    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)

    # output of attempt should exist (but be invalid)
    assert (testing_config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
    assert json["data"]["valid"]
    dcxml = testing_config.FS_MOUNT_POINT \
        / json["data"]["path"] \
        / testing_config.META_DIRECTORY \
        / testing_config.DC_METADATA
    assert dcxml.is_file() == dcxml_exists
    if dcxml_exists:
        parser = et.XMLParser(remove_blank_text=True)
        src_tree = et.parse(dcxml, parser)
        title = src_tree.find(".//{http://purl.org/dc/elements/1.1/}title")
        creator = src_tree.find(".//{http://purl.org/dc/elements/1.1/}creator")
        assert title.text == "Some title"
        assert creator.text == "Max Muster, et al."


def test_build_with_native_validation(
    client, testing_config, minimal_request_body, wait_for_report
):
    """Test functionality of /build-POST endpoint with validation."""

    # submit job
    minimal_request_body["validation"]["modules"] = ["bagit_profile"]
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert (testing_config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
    assert json["data"]["valid"]

    assert "logId" in json["data"]
    assert len(json["data"]["logId"]) == 1

    logid = json["data"]["logId"][0]
    assert "children" in json
    assert logid in json["children"]

    child = json["children"][logid]
    assert "host" in child
    assert "args" in child
    assert "log" in child
    assert "valid" in child["data"]
    assert "details" in child["data"]
    assert "details" in child["data"]
    assert "bagit_profile" in child["data"]["details"]


@pytest.mark.parametrize(
    "external_valid",
    [True, False],
    ids=["external_valid", "external_invalid"]
)
@pytest.mark.parametrize(
    ("internal_valid", "ie"),
    [
        (True, "test-ie"),
        (False, "test-ie-missing-meta")
    ],
    ids=["internal_valid", "internal_invalid"]
)
def test_build_with_external_validation(
    testing_config, minimal_request_body, wait_for_report, run_service,
    external_valid, internal_valid, ie
):
    """
    Test functionality of /build-POST endpoint with external validation.
    """

    # configure builder app
    class Config(testing_config):
        USE_OBJECT_VALIDATOR = True
    client = app_factory(Config()).test_client()

    # setup fake object validator
    fake_response = {
        "host": "http://localhost:8083",
        "token": {"value": "abcdef", "expires": False},
        "args": {},
        "progress": {"status": "completed", "verbose": "Done", "numeric": 100},
        "log": {},
        "data": {
            "valid": external_valid,
            "details": {
                "file_format": {
                    "valid": False,
                    "log": {
                        "error": [
                            {
                                "datetime": "2024-01-01T00:00:01+00:00",
                                "origin": "Jhove-Plugin",
                                "body": "File '<...>' has a bad file header."
                            }
                        ],
                    }
                }
            }
        }
    }
    run_service(
        routes=[
            ("/validate/ip", lambda: (jsonify(value="abcdef", expires=False), 201), ["POST"]),
            ("/report", lambda: (jsonify(**fake_response), 200), ["GET"]),
        ],
        port=8082
    )

    # submit job
    minimal_request_body["validation"]["modules"] = [
        "bagit_profile", "file_format"
    ]
    minimal_request_body["build"]["target"]["path"] = str(
        Path(minimal_request_body["build"]["target"]["path"]).parent / ie
    )
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert (Config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
    assert len(json["children"]) == 2
    assert len(json["data"]["logId"]) == 2
    assert all(logid in json["children"] for logid in json["data"]["logId"])
    assert json["data"]["valid"] == (external_valid and internal_valid)


def test_build_with_external_validation_timeout(
    testing_config, minimal_request_body, wait_for_report, run_service
):
    """
    Test functionality of /build-POST endpoint with external validation
    + timeout.
    """

    # configure builder app
    class Config(testing_config):
        USE_OBJECT_VALIDATOR = True
        OBJECT_VALIDATOR_VALIDATION_TIMEOUT = 0
    client = app_factory(Config()).test_client()

    run_service(
        routes=[
            ("/validate/ip", lambda: (jsonify(value="abcdef", expires=False), 201), ["POST"]),
            ("/report", lambda: Response(response="busy", status=503, mimetype="text/plain"), ["GET"]),
        ],
        port=8082
    )

    # submit job
    minimal_request_body["validation"]["modules"] = ["file_format"]
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert (Config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
    assert not json["data"]["valid"]
    assert "timed out" in str(json["log"]).lower()


def test_build_with_external_validation_no_connection(
    testing_config, minimal_request_body, wait_for_report
):
    """
    Test functionality of /build-POST endpoint with external validation
    + no service.
    """

    # configure builder app
    class Config(testing_config):
        USE_OBJECT_VALIDATOR = True
    client = app_factory(Config()).test_client()

    # submit job
    minimal_request_body["validation"]["modules"] = ["file_format"]
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert (Config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
    assert not json["data"]["valid"]
    assert "unavailable" in str(json["log"]).lower()


def test_build_with_external_validation_bad_request(
    testing_config, minimal_request_body, wait_for_report, run_service
):
    """
    Test functionality of /build-POST endpoint with external validation
    + bad request body.
    """

    # configure builder app
    class Config(testing_config):
        USE_OBJECT_VALIDATOR = True
    client = app_factory(Config()).test_client()

    run_service(
        routes=[
            (
                "/validate/ip",
                lambda: Response(
                    response="Bad request.", status=400, mimetype="text/plain"
                ),
                ["POST"]
            ),
        ],
        port=8082
    )

    # submit job
    minimal_request_body["validation"]["modules"] = ["file_format"]
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert not json["data"]["valid"]
    assert "Bad request" in str(json["log"][Context.ERROR.name])
    assert "400" in str(json["log"][Context.ERROR.name])


def test_build_with_external_validation_no_validation_block(
    testing_config, minimal_request_body, wait_for_report, run_service
):
    """
    Test functionality of /build-POST endpoint with external validation
    + without validation block in request body.
    """

    # configure builder app
    class Config(testing_config):
        USE_OBJECT_VALIDATOR = True
    client = app_factory(Config()).test_client()

    # setup fake object validator
    fake_response = {
        "host": "http://localhost:8083",
        "token": {"value": "abcdef", "expires": False},
        "args": {},
        "progress": {"status": "completed", "verbose": "Done", "numeric": 100},
        "log": {},
        "data": {
            "valid": True,
            "details": {
                "file_format": {
                    "valid": False,
                    "log": {}
                }
            }
        }
    }
    run_service(
        routes=[
            ("/validate/ip", lambda: (jsonify(value="abcdef", expires=False), 201), ["POST"]),
            ("/report", lambda: (jsonify(**fake_response), 200), ["GET"]),
        ],
        port=8082
    )

    # submit job without validation block
    del minimal_request_body["validation"]
    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert "validation" not in json["args"]
    assert "validation" in json["children"]["0@native"]["args"]
    assert json["children"]["0@native"]["args"]["validation"] == {}
    assert "1@object_validator" in json["children"]
    assert json["children"]["1@object_validator"] == fake_response
    assert "ERROR" not in json["log"]


@pytest.mark.parametrize(
    ("request_body_path", "new_value", "expected_status"),
    [
        (
            [],
            None,
            201
        ),
        (
            ["build", "target", "path2"],
            0,
            400
        ),
        (
            ["build", "configuration"],
            "nonsense",
            400
        ),
        (
            ["validation", "modules"],
            0,
            422
        ),
        (
            ["callbackUrl"],
            "no-url",
            422
        ),
    ],
    ids=[
        "good", "bad_target", "bad_configuration", "bad_modules",
        "bad_calback_url",
    ]
)
def test_build_handlers(
    client, minimal_request_body, request_body_path, new_value,
    expected_status, wait_for_report,
):
    """
    Test correct application of handlers in /build-POST endpoint.
    """

    def set_inner_dict(in_, keys, value):
        if len(keys) == 0:
            return
        if len(keys) == 1:
            in_[keys[0]] = value
            return
        return set_inner_dict(in_[keys[0]], keys[1:], value)
    set_inner_dict(minimal_request_body, request_body_path, new_value)

    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == expected_status
    if response.status_code == 201:
        assert response.mimetype == "application/json"
    else:
        assert response.mimetype == "text/plain"


def test_build_handlers_missing_validation_block(
    client, minimal_request_body
):
    """
    Test correct application of handlers in /build-POST endpoint.
    """

    del minimal_request_body["validation"]

    response = client.post(
        "/build",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
