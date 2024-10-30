"""Test-module for validation-endpoint."""

from pathlib import Path
from uuid import uuid4
from time import sleep, time

import pytest
from flask import jsonify, Response
from dcm_common import LoggingContext as Context

from dcm_ip_builder import app_factory


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body():
    return {
        "validation": {
            "target": {
                "path": str("test-bag")
            },
            "modules": []
        }
    }


@pytest.mark.parametrize(
    ("ip", "valid"),
    [
        ("test-bag", True),
        ("test-bag_bad", False)
    ],
    ids=["valid-ip", "invalid-ip"]
)
def test_validate_native_minimal(
    client, minimal_request_body, wait_for_report, ip, valid
):
    """Test basic functionality of /validate/ip-POST endpoint."""

    # submit job
    minimal_request_body["validation"]["target"]["path"] = str(
        Path(minimal_request_body["validation"]["target"]["path"]).parent / ip
    )
    minimal_request_body["validation"]["modules"] = ["bagit_profile"]
    response = client.post(
        "/validate/ip",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert json["data"]["valid"] == valid


@pytest.mark.parametrize(
    "external_valid",
    [True, False],
    ids=["external_valid", "external_invalid"]
)
@pytest.mark.parametrize(
    ("internal_valid", "ip"),
    [
        (True, "test-bag"),
        (False, "test-bag_bad")
    ],
    ids=["internal_valid", "internal_invalid"]
)
@pytest.mark.parametrize(
    "use_default_modules",
    [True, False],
    ids=["default_modules", "explicit_modules"]
)
def test_validate_ip_with_external_validation(
    testing_config, minimal_request_body, wait_for_report, run_service,
    external_valid, internal_valid, ip, use_default_modules
):
    """
    Test functionality of /validate/ip-POST endpoint with external validation.
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
        "log": {
            "INFO": [
                {
                    "datetime": "2024-01-01T00:00:01+00:00",
                    "origin": "Object Validator",
                    "body": "Job terminated normally."
                }
            ],
        },
        "data": {
            "valid": external_valid,
            "details": {
                "file_format": {
                    "valid": False,
                    "log": {
                        "ERROR": [
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
    if use_default_modules:
        del minimal_request_body["validation"]["modules"]
    else:
        minimal_request_body["validation"]["modules"] = [
            "bagit_profile", "file_format"
        ]
    minimal_request_body["validation"]["target"]["path"] = str(
        Path(minimal_request_body["validation"]["target"]["path"]).parent / ip
    )
    response = client.post(
        "/validate/ip",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert len(json["children"]) == 1
    assert len(json["data"]["logId"]) == 1
    assert all(logid in json["children"] for logid in json["data"]["logId"])
    assert json["data"]["valid"] == (external_valid and internal_valid)


def test_validate_ip_with_external_validation_timeout(
    testing_config, minimal_request_body, wait_for_report, run_service
):
    """
    Test functionality of /validate/ip-POST endpoint with external validation
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
        "/validate/ip",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert not json["data"]["valid"]
    assert "timed out" in str(json["log"]).lower()


def test_validate_ip_with_external_validation_no_connection(
    testing_config, minimal_request_body, wait_for_report
):
    """
    Test functionality of /validate/ip-POST endpoint with external validation
    + no service.
    """

    # configure builder app
    class Config(testing_config):
        USE_OBJECT_VALIDATOR = True
    client = app_factory(Config()).test_client()

    # submit job
    minimal_request_body["validation"]["modules"] = ["file_format"]
    response = client.post(
        "/validate/ip",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert not json["data"]["valid"]
    assert "unavailable" in str(json["log"]).lower()


def test_validate_ip_with_external_validation_bad_request(
    testing_config, minimal_request_body, wait_for_report, run_service
):
    """
    Test functionality of /validate/ip-POST endpoint with external validation
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
        "/validate/ip",
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
        "good", "bad_target", "bad_modules", "bad_calback_url",
    ]
)
def test_validate_ip_handlers(
    client, minimal_request_body, request_body_path, new_value, expected_status
):
    """
    Test correct application of handlers in /validate/ip-POST endpoint.
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
        "/validate/ip",
        json=minimal_request_body
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
    Test correct application of handlers in /validate/ip-POST endpoint.
    """

    del minimal_request_body["validation"]

    response = client.post(
        "/validate/ip",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 400
    assert response.mimetype == "text/plain"


def test_validate_ip_with_external_validation_abort(
    testing_config, minimal_request_body, run_service, file_storage
):
    """
    Test abort of /validate/ip-POST endpoint with external validation.
    """

    # configure builder app
    class Config(testing_config):
        USE_OBJECT_VALIDATOR = True
    client = app_factory(Config()).test_client()

    report_file = file_storage / str(uuid4())
    delete_file = file_storage / str(uuid4())
    assert not report_file.exists()
    assert not delete_file.exists()

    # use first call for report as marker to abort now
    # (builder is waiting for validator)
    def external_report():
        report_file.touch()
        return jsonify({"intermediate": "data"}), 503

    # use as marker abort request has been made
    def external_abort():
        delete_file.touch()
        return Response("OK", mimetype="text/plain", status=200)

    # setup fake object validator
    run_service(
        routes=[
            ("/validate/ip", lambda: (jsonify(value="abcdef", expires=False), 201), ["POST"]),
            ("/validate", external_abort, ["DELETE"]),
            ("/report", external_report, ["GET"]),
        ],
        port=8082
    )

    # submit job
    minimal_request_body["validation"]["modules"] = ["file_format"]
    minimal_request_body["validation"]["target"]["path"] = str(
        Path(minimal_request_body["validation"]["target"]["path"]).parent / "test-bag"
    )
    token = client.post(
        "/validate/ip",
        json=minimal_request_body
    ).json["value"]
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    # wait until job is completed
    time0 = time()
    while not report_file.exists() and time() - time0 < 2:
        sleep(0.01)
    assert report_file.exists()
    sleep(0.1)

    assert client.delete(
        f"/validate?token={token}",
        json={"reason": "test abort", "origin": "pytest-runner"}
    ).status_code == 200
    assert delete_file.exists()
    report = client.get(f"/report?token={token}").json
    assert report["progress"]["status"] == "aborted"
    assert "Received SIGKILL" in str(report["log"])
    assert "Aborting child" in str(report["log"])
    assert "0@object_validator" in report["children"]
    assert report["children"]["0@object_validator"] == {"intermediate": "data"}
