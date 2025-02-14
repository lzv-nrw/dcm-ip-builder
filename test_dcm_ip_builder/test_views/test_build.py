"""Test-module for build-endpoint."""

from pathlib import Path
from unittest import mock

import pytest
from bagit import Bag
from lxml import etree as et
from dcm_common.util import list_directory_content


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body():
    return {
        "build": {
            "target": {
                "path": str("test-ie")
            },
            "mappingPlugin": {
                "plugin": "demo",
                "args": {}
            }
        }
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
    assert Bag(
        str(testing_config.FS_MOUNT_POINT / json["data"]["path"])
    ).is_valid()
    assert json["data"]["valid"]
    assert json["data"]["success"]


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
    assert not json["data"]["success"]

    patcher.stop()


def test_build_missing_meta(
    client, file_storage, minimal_request_body, wait_for_report
):
    """Test /build-POST with missing metadata."""

    # submit job
    minimal_request_body["build"]["target"]["path"] = str(
        Path(minimal_request_body["build"]["target"]["path"]).parent
        / "test-ie-missing-meta"
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

    # output is invalid
    assert not json["data"]["success"]
    assert len(json["log"]["ERROR"]) == 2
    assert "valid" not in json["data"]

    # directory for fs-hook exists but is empty
    assert "path" in json["data"]
    assert (file_storage / json["data"]["path"]).exists()
    assert (
        len(list_directory_content(file_storage / json["data"]["path"])) == 0
    )


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

    # output of attempt should exist
    assert (testing_config.FS_MOUNT_POINT / json["data"]["path"]).is_dir()
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
        assert json["data"]["success"]
        assert json["data"]["valid"]
    else:
        assert not json["data"]["success"]
        assert not json["data"]["valid"]


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
            ["callbackUrl"],
            "no-url",
            422
        ),
    ],
    ids=[
        "good", "bad_target", "bad_configuration",
        "bad_calback_url",
    ]
)
def test_build_handlers(
    client, minimal_request_body, request_body_path, new_value,
    expected_status,
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
